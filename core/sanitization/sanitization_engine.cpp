#include "sanitization_engine.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace crypty::sanitization {
  namespace {

    constexpr char kImageMarker[] = "CRYPTY_DISPOSABLE_IMAGE_V1\n";
    constexpr std::size_t kChunkSize = 1024 * 1024;

    bool same_file_identity(
      const FileIdentity & expected,
        const FileIdentity & actual
    ) {
      return expected.valid &&
        actual.valid &&
        expected.volume_or_device_id == actual.volume_or_device_id &&
        expected.file_id_high == actual.file_id_high &&
        expected.file_id_low == actual.file_id_low;
    }

    #ifdef _WIN32

    class FileHandle {
      public: explicit FileHandle(HANDLE handle): handle_(handle) {}
        ~FileHandle() {
          if (handle_ != INVALID_HANDLE_VALUE) {
            CloseHandle(handle_);
          }
        }

      FileHandle(const FileHandle & ) = delete;
      FileHandle & operator = (const FileHandle & ) = delete;

      HANDLE get() const {
        return handle_;
      }

      private: HANDLE handle_;
    };

    bool seek_to(HANDLE file, std::uint64_t offset) {
      LARGE_INTEGER position {};
      position.QuadPart = static_cast < LONGLONG > (offset);
      return SetFilePointerEx(file, position, nullptr, FILE_BEGIN) != 0;
    }

    bool read_exact(HANDLE file, void * data, std::size_t size) {
      auto * bytes = static_cast < unsigned char * > (data);
      std::size_t done = 0;

      while (done < size) {
        const DWORD request = static_cast < DWORD > (
          (std::min)(size - done,
            static_cast < std::size_t > (MAXDWORD))
        );

        DWORD transferred = 0;
        if (!ReadFile(file, bytes + done, request, & transferred, nullptr) ||
          transferred == 0) {
          return false;
        }

        done += transferred;
      }

      return true;
    }

    bool write_exact(HANDLE file,
      const void * data, std::size_t size) {
      const auto * bytes = static_cast <
        const unsigned char * > (data);
      std::size_t done = 0;

      while (done < size) {
        const DWORD request = static_cast < DWORD > (
          (std::min)(size - done,
            static_cast < std::size_t > (MAXDWORD))
        );

        DWORD transferred = 0;
        if (!WriteFile(file, bytes + done, request, & transferred, nullptr) ||
          transferred == 0) {
          return false;
        }

        done += transferred;
      }

      return true;
    }

    #else

    class FileHandle {
      public: explicit FileHandle(int fd): fd_(fd) {}
        ~FileHandle() {
          if (fd_ >= 0) {
            ::close(fd_);
          }
        }

      FileHandle(const FileHandle & ) = delete;
      FileHandle & operator = (const FileHandle & ) = delete;

      int get() const {
        return fd_;
      }

      private: int fd_;
    };

    bool read_exact(int fd, void * data, std::size_t size, std::uint64_t offset) {
      auto * bytes = static_cast < unsigned char * > (data);
      std::size_t done = 0;

      while (done < size) {
        const ssize_t count = ::pread(
          fd, bytes + done, size - done,
          static_cast < off_t > (offset + done)
        );

        if (count < 0 && errno == EINTR) {
          continue;
        }
        if (count <= 0) {
          return false;
        }

        done += static_cast < std::size_t > (count);
      }

      return true;
    }

    bool write_exact(
      int fd,
      const void * data,
        std::size_t size,
        std::uint64_t offset
    ) {
      const auto * bytes = static_cast <
        const unsigned char * > (data);
      std::size_t done = 0;

      while (done < size) {
        const ssize_t count = ::pwrite(
          fd, bytes + done, size - done,
          static_cast < off_t > (offset + done)
        );

        if (count < 0 && errno == EINTR) {
          continue;
        }
        if (count <= 0) {
          return false;
        }

        done += static_cast < std::size_t > (count);
      }

      return true;
    }

    #endif

    SanitizationResult failure(
      const SanitizationPlan & plan,
        const char * code,
          const std::string & message,
            std::uint64_t bytes_written = 0
    ) {
      SanitizationResult result;
      result.plan_id = plan.plan_id;
      result.device_id = plan.device_id;
      result.required_level = plan.required_level;
      result.target_capacity_bytes = plan.target_capacity_bytes;
      result.method_used = Method::ImageFileOverwrite;
      result.execution_status = ExecutionStatus::Failed;
      result.validation_status = ValidationStatus::NotPerformed;
      result.bytes_processed = bytes_written;
      result.successful = false;
      result.error_code = code;
      result.error_message = message;

      if (bytes_written != 0) {
        result.warnings.push_back(
          "The file may have been partially overwritten. "
          "Do not treat it as an intact image."
        );
      }

      return result;
    }

    bool valid_plan(const SanitizationPlan & plan, std::string & reason) {
      if (plan.status != PlanStatus::Ready) {
        reason = "The sanitization plan is not Ready.";
        return false;
      }

      if (plan.target_kind != TargetKind::DiskImageFile) {
        reason = "Only explicitly identified disk-image files are supported.";
        return false;
      }

      if (plan.target_path.empty()) {
        reason = "The target path is empty.";
        return false;
      }

      if (plan.required_level != AssuranceLevel::Clear) {
        reason = "File overwrite cannot establish Purge or Destroy assurance.";
        return false;
      }

      if (plan.steps.size() != 1 ||
        plan.steps.front().method != Method::ImageFileOverwrite) {
        reason = "The plan must contain exactly one ImageFileOverwrite step.";
        return false;
      }

      if (plan.target_capacity_bytes == 0) {
        reason = "The planned target size must be non-zero.";
        return false;
      }

      return true;
    }

  } // namespace

  SanitizationResult SanitizationEngine::execute(
    const SanitizationPlan & plan,
      const ExecutionAuthorization & authorization
  ) {
    std::string reason;

    // Require explicit authorization before touching the target.
    if (!authorization.confirmed) {
      return failure(
        plan,
        "AUTHORIZATION_REQUIRED",
        "Explicit user authorization is required."
      );
    }

    if (authorization.confirmed_target_path.empty() ||
      authorization.confirmed_target_path != plan.target_path) {
      return failure(
        plan,
        "AUTHORIZATION_TARGET_MISMATCH",
        "The authorized path does not match the planned target."
      );
    }

    if (authorization.confirmed_target_capacity_bytes == 0 ||
      authorization.confirmed_target_capacity_bytes !=
      plan.target_capacity_bytes) {
      return failure(
        plan,
        "AUTHORIZATION_CAPACITY_MISMATCH",
        "The authorized capacity does not match the planned target."
      );
    }

    if (authorization.confirmation_phrase !=
      kSanitizationConfirmationPhrase) {
      return failure(
        plan,
        "CONFIRMATION_PHRASE_INVALID",
        "The destructive-action confirmation phrase is invalid."
      );
    }

    if (!valid_plan(plan, reason)) {
      return failure(plan, "INVALID_PLAN", reason);
    }

    const std::filesystem::path path = std::filesystem::u8path(plan.target_path);

    #ifdef _WIN32
    // Open an existing file without allowing other handles to access it
    // concurrently. OPEN_EXISTING prevents accidental file creation.
    FileHandle file(CreateFileW(
      path.c_str(),
      GENERIC_READ | GENERIC_WRITE,
      0,
      nullptr,
      OPEN_EXISTING,
      FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT,
      nullptr
    ));

    if (file.get() == INVALID_HANDLE_VALUE) {
      return failure(
        plan, "OPEN_FAILED",
        "Could not open the target exclusively. Win32 error: " +
        std::to_string(GetLastError())
      );
    }

    BY_HANDLE_FILE_INFORMATION info {};
    LARGE_INTEGER file_size {};

    if (!GetFileInformationByHandle(file.get(), & info) ||
      !GetFileSizeEx(file.get(), & file_size)) {
      return failure(plan, "METADATA_FAILED",
        "Could not inspect the target file.");
    }

    FileIdentity actual_identity;
    actual_identity.valid = true;
    actual_identity.volume_or_device_id = info.dwVolumeSerialNumber;
    actual_identity.file_id_high = info.nFileIndexHigh;
    actual_identity.file_id_low = info.nFileIndexLow;

    if (!same_file_identity(plan.target_identity, actual_identity)) {
      return failure(
        plan,
        "TARGET_IDENTITY_MISMATCH",
        "The opened file does not match the identity recorded in the plan."
      );
    }

    if ((info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0 ||
      (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0) {
      return failure(plan, "UNSAFE_TARGET",
        "Directories and reparse points are not allowed.");
    }

    if (file_size.QuadPart < 0 ||
      static_cast < std::uint64_t > (file_size.QuadPart) !=
      plan.target_capacity_bytes) {
      return failure(plan, "SIZE_MISMATCH",
        "The file size differs from the planned target size.");
    }

    const auto size = static_cast < std::uint64_t > (file_size.QuadPart);

    if (!seek_to(file.get(), 0)) {
      return failure(plan, "SEEK_FAILED",
        "Could not seek to the start of the file.");
    }

    std::array < char, sizeof(kImageMarker) - 1 > marker {};
    if (!read_exact(file.get(), marker.data(), marker.size()) ||
      !std::equal(marker.begin(), marker.end(), kImageMarker)) {
      return failure(plan, "MARKER_MISMATCH",
        "The target does not contain the Crypty disposable-image marker.");
    }

    std::vector < unsigned char > zeros(kChunkSize, 0);
    std::uint64_t written = 0;

    while (written < size) {
        const auto count = static_cast<std::size_t>(
            (std::min)(static_cast<std::uint64_t>(zeros.size()),
                    size - written)
        );
        if (!seek_to(file.get(), written) ||
        !write_exact(file.get(), zeros.data(), count)) {
        return failure(plan, "WRITE_FAILED",
          "A write failed; the file may be partially overwritten.",
          written);
      }
      written += count;
    }
    if (!FlushFileBuffers(file.get())) {
      return failure(plan, "FLUSH_FAILED",
        "The file flush failed after writing.",
        written);
    }
    if (!seek_to(file.get(), 0)) {
      return failure(plan, "VERIFY_SEEK_FAILED",
        "Could not seek to the start for verification.",
        written);
    }
    std::vector<unsigned char> readback(kChunkSize);
    for (std::uint64_t offset = 0; offset < size;) {
      const auto count = static_cast<std::size_t>(
            (std::min)(static_cast<std::uint64_t>(readback.size()),
                    size - offset)
        );
      if (!read_exact(file.get(), readback.data(), count)) {
        return failure(plan, "READBACK_FAILED",
          "Could not read back the overwritten file.",
          written);
      }
      if (std::any_of(readback.begin(), readback.begin() + count,
          [](unsigned char byte) {
            return byte != 0;
          })) {
        return failure(plan, "VERIFICATION_FAILED",
          "Read-back found non-zero bytes.",
          written);
      }
      offset += count;
    }
    #else
    const int fd = ::open(
      path.c_str(),
      O_RDWR | O_CLOEXEC | O_NOFOLLOW
    );
    FileHandle file(fd);
    if (file.get() < 0) {
      return failure(plan, "OPEN_FAILED",
        "Could not open the target without following symlinks.");
    }
    struct stat info {};
    if (::fstat(file.get(), & info) != 0 || !S_ISREG(info.st_mode)) {
      return failure(plan, "UNSAFE_TARGET",
        "The target must be an existing regular file.");
    }
    FileIdentity actual_identity;
    actual_identity.valid = true;
    actual_identity.volume_or_device_id =
      static_cast<std::uint64_t>(info.st_dev);
    actual_identity.file_id_high = 0;
    actual_identity.file_id_low =
      static_cast<std::uint64_t>(info.st_ino);
    if (!same_file_identity(plan.target_identity, actual_identity)) {
      return failure(
        plan,
        "TARGET_IDENTITY_MISMATCH",
        "The opened file does not match the identity recorded in the plan."
      );
    }
    if (info.st_size < 0 ||
      static_cast<std::uint64_t>(info.st_size) !=
      plan.target_capacity_bytes) {
      return failure(plan, "SIZE_MISMATCH",
        "The file size differs from the planned target size.");
    }
    const auto size = static_cast<std::uint64_t>(info.st_size);
    std::array < char, sizeof(kImageMarker) - 1 > marker {};
    if (!read_exact(file.get(), marker.data(), marker.size(), 0) ||
      !std::equal(marker.begin(), marker.end(), kImageMarker)) {
      return failure(plan, "MARKER_MISMATCH",
        "The target does not contain the Crypty disposable-image marker.");
    }
    std::vector<unsigned char> zeros(kChunkSize, 0);
    std::uint64_t written = 0;
    while (written < size) {
      const auto count = static_cast<std::size_t>(
        (std::min)(static_cast<std::uint64_t>(zeros.size()),
          size - written)
      );
      if (!write_exact(file.get(), zeros.data(), count, written)) {
        return failure(plan, "WRITE_FAILED",
          "A write failed; the file may be partially overwritten.",
          written);
      }
      written += count;
    }
    if (::fsync(file.get()) != 0) {
      return failure(plan, "FLUSH_FAILED",
        "The file sync operation failed after writing.",
        written);
    }
    std::vector<unsigned char> readback(kChunkSize);
    for (std::uint64_t offset = 0; offset < size;) {
      const auto count = static_cast<std::size_t>(
        (std::min)(static_cast<std::uint64_t>(readback.size()),
          size - offset)
      );
      if (!read_exact(file.get(), readback.data(), count, offset)) {
        return failure(plan, "READBACK_FAILED",
          "Could not read back the overwritten file.",
          written);
      }
      if (std::any_of(readback.begin(), readback.begin() + count,
          [](unsigned char byte) {
            return byte != 0;
          })) {
        return failure(plan, "VERIFICATION_FAILED",
          "Read-back found non-zero bytes.",
          written);
      }
      offset += count;
    }
    #endif
    SanitizationResult result;
    result.plan_id = plan.plan_id;
    result.device_id = plan.device_id;
    result.method_used = Method::ImageFileOverwrite;
    result.required_level = plan.required_level;
    result.target_capacity_bytes = plan.target_capacity_bytes;
    result.bytes_processed = plan.target_capacity_bytes;
    result.execution_status = ExecutionStatus::Completed;
    result.validation_status = ValidationStatus::Passed;
    result.successful = true;
    result.warnings.push_back(
      "File contents were zero-filled and read-back verified. "
      "This does not prove physical-media sanitization."
    );
    return result;
  }
} // namespace crypty::sanitization