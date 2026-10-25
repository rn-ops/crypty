#include <crypty/workflow.hpp>
#include <crypty/platform/device_access.hpp>
#include "../reporting/report.hpp"
#include "../recovery/recovery_engine.hpp"
#include "../sanitization/sanitization_engine.hpp"
#include <crypty/sanitization/policy_engine.hpp>
#include <crypty/sanitization/execution_authorization.hpp>

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#include <algorithm>
#include <atomic>
#include <filesystem>
#include <limits>
#include <iterator>

#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

#if defined(_WIN32)
#define CRYPTY_API __declspec(dllexport)
#else
#define CRYPTY_API
#endif

namespace {
crypty::Workflow* workflow(void* handle) {
    return static_cast<crypty::Workflow*>(handle);
}

const std::string& empty_string() {
    static const std::string value;
    return value;
}

const char* copy_string(const std::string& value) {
    thread_local std::string result;
    result = value;
    return result.c_str();
}

using Device = crypty::platform::StorageDevice;

std::vector<Device> detect_devices() {
    return crypty::platform::enumerate_devices();
}

std::vector<Device>& devices() {
    static std::vector<Device> value = detect_devices();
    return value;
}

std::size_t read_media(const std::string& path, std::uint64_t offset,
                       std::uint8_t* output, std::size_t capacity) {
    return crypty::platform::read_media(path, offset, output, capacity);
}

using crypty::sanitization::FileIdentity;
using crypty::sanitization::SanitizationPlan;
using crypty::sanitization::SanitizationResult;

constexpr char kDisposableImageMarker[] = "CRYPTY_DISPOSABLE_IMAGE_V1\n";

struct SanitizationOperation {
    SanitizationPlan plan;
    SanitizationResult result;
    bool executed = false;
};

std::atomic<std::uint64_t> next_sanitization_plan_id{1};

bool inspect_disposable_image(
    const std::filesystem::path& path,
    std::uint64_t& size,
    FileIdentity& identity,
    std::string& reason
) {
#if defined(_WIN32)
    HANDLE file = CreateFileW(
        path.c_str(),
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr,
        OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT,
        nullptr
    );
    if (file == INVALID_HANDLE_VALUE) {
        reason = "Could not open the selected image for read-only inspection. Win32 error: " +
            std::to_string(GetLastError());
        return false;
    }

    BY_HANDLE_FILE_INFORMATION info{};
    LARGE_INTEGER file_size{};
    const bool metadata_ok =
        GetFileInformationByHandle(file, &info) != 0 &&
        GetFileSizeEx(file, &file_size) != 0;
    if (!metadata_ok) {
        reason = "Could not inspect the selected image metadata.";
        CloseHandle(file);
        return false;
    }

    if ((info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0 ||
        (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0) {
        reason = "Directories and reparse points are not valid disposable-image targets.";
        CloseHandle(file);
        return false;
    }
    if (file_size.QuadPart <= 0) {
        reason = "The selected image must be a non-empty file.";
        CloseHandle(file);
        return false;
    }

    char marker[sizeof(kDisposableImageMarker) - 1]{};
    DWORD bytes_read = 0;
    const bool marker_ok = ReadFile(
        file, marker, static_cast<DWORD>(sizeof(marker)), &bytes_read, nullptr
    ) != 0 && bytes_read == sizeof(marker) &&
        std::equal(std::begin(marker), std::end(marker), kDisposableImageMarker);
    CloseHandle(file);
    if (!marker_ok) {
        reason = "The file does not contain the Crypty disposable-image marker; it was not modified.";
        return false;
    }

    size = static_cast<std::uint64_t>(file_size.QuadPart);
    identity.valid = true;
    identity.volume_or_device_id = info.dwVolumeSerialNumber;
    identity.file_id_high = info.nFileIndexHigh;
    identity.file_id_low = info.nFileIndexLow;
    return true;
#else
    const int fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) {
        reason = "Could not open the selected image for read-only inspection: " +
            std::string(std::strerror(errno));
        return false;
    }

    struct stat info{};
    if (::fstat(fd, &info) != 0 || !S_ISREG(info.st_mode)) {
        reason = "The target must be a regular file, not a directory or device.";
        ::close(fd);
        return false;
    }
    if (info.st_size <= 0) {
        reason = "The selected image must be a non-empty file.";
        ::close(fd);
        return false;
    }

    char marker[sizeof(kDisposableImageMarker) - 1]{};
    const auto bytes_read = ::pread(fd, marker, sizeof(marker), 0);
    ::close(fd);
    if (bytes_read != static_cast<ssize_t>(sizeof(marker)) ||
        !std::equal(std::begin(marker), std::end(marker), kDisposableImageMarker)) {
        reason = "The file does not contain the Crypty disposable-image marker; it was not modified.";
        return false;
    }

    size = static_cast<std::uint64_t>(info.st_size);
    identity.valid = true;
    identity.volume_or_device_id = static_cast<std::uint64_t>(info.st_dev);
    identity.file_id_high = 0;
    identity.file_id_low = static_cast<std::uint64_t>(info.st_ino);
    return true;
#endif
}

SanitizationOperation* sanitization_operation(void* handle) {
    return static_cast<SanitizationOperation*>(handle);
}

}

extern "C" {
CRYPTY_API void* crypty_sanitization_plan_image_file(const char* raw_path) {
    auto* operation = new SanitizationOperation{};
    auto& plan = operation->plan;
    const std::string plan_id = "IMAGE-CLEAR-" +
        std::to_string(next_sanitization_plan_id.fetch_add(1));
    plan.plan_id = plan_id;
    plan.policy_id = "CRYPTY-IMAGE-CLEAR";
    plan.target_kind = crypty::sanitization::TargetKind::DiskImageFile;
    plan.required_level = crypty::sanitization::AssuranceLevel::Clear;
    plan.requires_post_sanitization_validation = true;
    plan.requires_audit_evidence = true;

    if (raw_path == nullptr || *raw_path == '\0') {
        plan.status = crypty::sanitization::PlanStatus::Blocked;
        plan.status_reason = "An explicit image-file path is required.";
        return operation;
    }

    std::error_code ec;
    const auto canonical_path = std::filesystem::canonical(
        std::filesystem::u8path(raw_path), ec
    );
    if (ec) {
        plan.target_path = raw_path;
        plan.status = crypty::sanitization::PlanStatus::Blocked;
        plan.status_reason = "The selected path does not resolve to an existing file: " + ec.message();
        return operation;
    }

    plan.target_path = canonical_path.u8string();
    plan.device_id = "IMAGE:" + plan.target_path;

    std::uint64_t size = 0;
    FileIdentity identity{};
    std::string inspection_reason;
    if (!inspect_disposable_image(canonical_path, size, identity, inspection_reason)) {
        plan.status = crypty::sanitization::PlanStatus::Blocked;
        plan.status_reason = std::move(inspection_reason);
        return operation;
    }

    crypty::sanitization::SanitizationPolicy policy;
    policy.policy_id = "CRYPTY-IMAGE-CLEAR";
    policy.policy_version = "1.0";
    policy.required_level = crypty::sanitization::AssuranceLevel::Clear;
    policy.require_validation = true;
    policy.require_audit_evidence = true;
    policy.allow_fallback = false;
    policy.permitted_methods = {
        crypty::sanitization::Method::ImageFileOverwrite
    };

    crypty::sanitization::SanitizationTarget target;
    target.device_id = plan.device_id;
    target.media_type = crypty::sanitization::MediaType::Unknown;
    target.capacity_bytes = size;
    target.kind = crypty::sanitization::TargetKind::DiskImageFile;
    target.target_path = plan.target_path;
    target.available_methods = {
        crypty::sanitization::Method::ImageFileOverwrite
    };
    target.target_identity = identity;

    crypty::sanitization::PolicyEngine policy_engine;
    plan = policy_engine.create_plan(policy, target);
    plan.plan_id = plan_id;
    return operation;
}

CRYPTY_API void crypty_sanitization_plan_destroy(void* handle) {
    delete sanitization_operation(handle);
}

CRYPTY_API int crypty_sanitization_plan_status(void* handle) {
    if (handle == nullptr) return static_cast<int>(crypty::sanitization::PlanStatus::Blocked);
    return static_cast<int>(sanitization_operation(handle)->plan.status);
}

CRYPTY_API const char* crypty_sanitization_plan_reason(void* handle) {
    if (handle == nullptr) return copy_string("Invalid sanitization plan handle.");
    return copy_string(sanitization_operation(handle)->plan.status_reason);
}

CRYPTY_API const char* crypty_sanitization_plan_path(void* handle) {
    if (handle == nullptr) return copy_string("");
    return copy_string(sanitization_operation(handle)->plan.target_path);
}

CRYPTY_API std::uint64_t crypty_sanitization_plan_capacity(void* handle) {
    if (handle == nullptr) return 0;
    return sanitization_operation(handle)->plan.target_capacity_bytes;
}

CRYPTY_API int crypty_sanitization_execute_image_file(
    void* handle,
    int confirmed,
    const char* confirmed_path,
    std::uint64_t confirmed_capacity,
    const char* confirmation_phrase
) {
    if (handle == nullptr) return 0;
    auto* operation = sanitization_operation(handle);
    if (operation->executed || operation->plan.status != crypty::sanitization::PlanStatus::Ready) {
        return 0;
    }

    crypty::sanitization::ExecutionAuthorization authorization;
    authorization.confirmed = confirmed != 0;
    authorization.confirmed_target_path = confirmed_path == nullptr ? "" : confirmed_path;
    authorization.confirmed_target_capacity_bytes = confirmed_capacity;
    authorization.confirmation_phrase = confirmation_phrase == nullptr ? "" : confirmation_phrase;

    crypty::sanitization::SanitizationEngine engine;
    operation->result = engine.execute(operation->plan, authorization);
    operation->executed = true;
    return operation->result.successful ? 1 : 0;
}

CRYPTY_API int crypty_sanitization_result_executed(void* handle) {
    return handle != nullptr && sanitization_operation(handle)->executed ? 1 : 0;
}

CRYPTY_API int crypty_sanitization_result_successful(void* handle) {
    return handle != nullptr && sanitization_operation(handle)->result.successful ? 1 : 0;
}

CRYPTY_API int crypty_sanitization_result_execution_status(void* handle) {
    if (handle == nullptr) return static_cast<int>(crypty::sanitization::ExecutionStatus::Failed);
    return static_cast<int>(sanitization_operation(handle)->result.execution_status);
}

CRYPTY_API int crypty_sanitization_result_validation_status(void* handle) {
    if (handle == nullptr) return static_cast<int>(crypty::sanitization::ValidationStatus::NotPerformed);
    return static_cast<int>(sanitization_operation(handle)->result.validation_status);
}

CRYPTY_API std::uint64_t crypty_sanitization_result_bytes_processed(void* handle) {
    if (handle == nullptr) return 0;
    return sanitization_operation(handle)->result.bytes_processed;
}

CRYPTY_API const char* crypty_sanitization_result_error_code(void* handle) {
    if (handle == nullptr) return copy_string("INVALID_HANDLE");
    return copy_string(sanitization_operation(handle)->result.error_code);
}

CRYPTY_API const char* crypty_sanitization_result_error_message(void* handle) {
    if (handle == nullptr) return copy_string("Invalid sanitization operation handle.");
    return copy_string(sanitization_operation(handle)->result.error_message);
}

CRYPTY_API void* crypty_workflow_create() { return new crypty::Workflow(); }

CRYPTY_API void crypty_workflow_destroy(void* handle) {
    delete workflow(handle);
}

CRYPTY_API void crypty_workflow_select_operation(void* handle, int operation) {
    workflow(handle)->select_operation(operation == 1 ? crypty::Operation::Erasure : crypty::Operation::Recovery);
}

CRYPTY_API void crypty_workflow_inspect_target(void* handle, const char* path) {
    workflow(handle)->inspect_target(path == nullptr ? "." : path);
}

CRYPTY_API void crypty_workflow_start(void* handle) { workflow(handle)->start(); }

CRYPTY_API void crypty_workflow_advance(void* handle, int step) {
    workflow(handle)->advance(step);
}

CRYPTY_API int crypty_workflow_state(void* handle) {
    return static_cast<int>(workflow(handle)->snapshot().state);
}

CRYPTY_API int crypty_workflow_progress(void* handle) {
    return workflow(handle)->snapshot().progress;
}

CRYPTY_API int crypty_workflow_evidence_items(void* handle) {
    return workflow(handle)->snapshot().evidence_items;
}

CRYPTY_API std::uintmax_t crypty_workflow_total_bytes(void* handle) {
    return workflow(handle)->snapshot().total_bytes;
}

CRYPTY_API const char* crypty_workflow_integrity(void* handle) {
    return copy_string(workflow(handle)->snapshot().integrity);
}

CRYPTY_API const char* crypty_workflow_target_path(void* handle) {
    return copy_string(workflow(handle)->snapshot().target.path);
}

CRYPTY_API std::size_t crypty_workflow_file_count(void* handle) {
    return workflow(handle)->snapshot().files.size();
}

CRYPTY_API const char* crypty_workflow_file_name(void* handle, std::size_t index) {
    const auto snapshot = workflow(handle)->snapshot();
    return index >= snapshot.files.size() ? empty_string().c_str() : copy_string(snapshot.files[index].name);
}

CRYPTY_API const char* crypty_workflow_file_path(
    void* handle,
    size_t index
) {
    static thread_local std::string value;

    value.clear();

    if (!handle) {
        return "";
    }

    auto* workflow =
        static_cast<crypty::Workflow*>(handle);

    const auto snapshot = workflow->snapshot();

    if (index >= snapshot.files.size()) {
        return "";
    }

    value = snapshot.files[index].path;

    return value.c_str();
}

CRYPTY_API const char* crypty_workflow_file_type(void* handle, std::size_t index) {
    const auto snapshot = workflow(handle)->snapshot();
    return index >= snapshot.files.size() ? empty_string().c_str() : copy_string(snapshot.files[index].type);
}

CRYPTY_API std::uintmax_t crypty_workflow_file_size(void* handle, std::size_t index) {
    const auto snapshot = workflow(handle)->snapshot();
    return index >= snapshot.files.size() ? 0 : snapshot.files[index].size;
}

CRYPTY_API std::size_t crypty_workflow_audit_count(void* handle) {
    return workflow(handle)->snapshot().audit.size();
}

CRYPTY_API const char* crypty_workflow_audit_code(void* handle, std::size_t index) {
    const auto snapshot = workflow(handle)->snapshot();
    return index >= snapshot.audit.size() ? empty_string().c_str() : copy_string(snapshot.audit[index].code);
}

CRYPTY_API const char* crypty_workflow_audit_message(void* handle, std::size_t index) {
    const auto snapshot = workflow(handle)->snapshot();
    return index >= snapshot.audit.size() ? empty_string().c_str() : copy_string(snapshot.audit[index].message);
}

CRYPTY_API int crypty_workflow_write_report(void* handle, const char* filename) {
    if (filename == nullptr) return 0;
    return crypty::write_report(workflow(handle)->snapshot(), filename) ? 1 : 0;
}

CRYPTY_API std::size_t crypty_device_count() { return devices().size(); }

CRYPTY_API void crypty_devices_refresh() { devices() = detect_devices(); }

CRYPTY_API const char* crypty_device_path(std::size_t index) {
    return index >= devices().size() ? empty_string().c_str() : copy_string(devices()[index].path);
}

CRYPTY_API const char* crypty_device_name(std::size_t index) {
    return index >= devices().size() ? empty_string().c_str() : copy_string(devices()[index].name);
}

CRYPTY_API const char* crypty_device_filesystem(std::size_t index) {
    return index >= devices().size() ? empty_string().c_str() : copy_string(devices()[index].filesystem);
}

CRYPTY_API const char* crypty_device_media_type(std::size_t index) {
    return index >= devices().size() ? empty_string().c_str() : copy_string(devices()[index].media_type);
}

CRYPTY_API const char* crypty_device_interface(std::size_t index) {
    return index >= devices().size() ? empty_string().c_str() : copy_string(devices()[index].interface_name);
}

CRYPTY_API const char* crypty_device_status(std::size_t index) {
    return index >= devices().size() ? empty_string().c_str() : copy_string(devices()[index].status);
}

CRYPTY_API std::uint64_t crypty_device_capacity(std::size_t index) {
    return index >= devices().size() ? 0 : devices()[index].capacity;
}

CRYPTY_API std::uint64_t crypty_workflow_file_offset(void* handle, std::size_t index) {
    const auto snapshot = workflow(handle)->snapshot();
    return index >= snapshot.files.size() ? 0 : snapshot.files[index].source_offset;
}

CRYPTY_API int crypty_workflow_file_confidence(void* handle, std::size_t index) {
    const auto snapshot = workflow(handle)->snapshot();
    return index >= snapshot.files.size() ? 0 : snapshot.files[index].confidence;
}

CRYPTY_API int crypty_workflow_file_deleted(void* handle, std::size_t index) {
    const auto snapshot = workflow(handle)->snapshot();
    return index < snapshot.files.size() && snapshot.files[index].deleted ? 1 : 0;
}

CRYPTY_API const char* crypty_workflow_file_method(void* handle, std::size_t index) {
    const auto snapshot = workflow(handle)->snapshot();
    return index >= snapshot.files.size() ? empty_string().c_str() : copy_string(snapshot.files[index].recovery_method);
}


CRYPTY_API std::size_t crypty_workflow_scan_fat32_deleted(void* handle) {
    if (handle == nullptr) return 0;

    const auto snapshot = workflow(handle)->snapshot();
    const auto path = snapshot.target.path;

    const crypty::filesystem::ReadAt read_at =
        [&path](std::uint64_t offset,
                std::uint8_t* output,
                std::size_t capacity) {
            return read_media(path, offset, output, capacity);
        };

    crypty::recovery::RecoveryEngine engine;
    const auto results = engine.scan(read_at);

    workflow(handle)->set_recovery_candidates(results);
    return results.size();
}

CRYPTY_API std::uintmax_t crypty_workflow_recover_fat32_file(
    void* handle,
    std::size_t index,
    const char* destination,
    int* complete
) {
    if (complete != nullptr) *complete = 0;
    if (handle == nullptr || destination == nullptr) return 0;

    const auto snapshot = workflow(handle)->snapshot();
    if (index >= snapshot.files.size()) return 0;

    const auto path = snapshot.target.path;

    const crypty::filesystem::ReadAt read_at =
        [&path](std::uint64_t offset,
                std::uint8_t* output,
                std::size_t capacity) {
            return read_media(path, offset, output, capacity);
        };

    crypty::recovery::RecoveryEngine engine;
    const auto result = engine.recover(
        read_at, snapshot.files[index], destination
    );

    if (complete != nullptr) *complete = result.success ? 1 : 0;
    return static_cast<std::uintmax_t>(result.bytes_recovered);
}

CRYPTY_API std::size_t crypty_workflow_scan_ntfs(void* handle) {
    if (handle == nullptr) return 0;

    const auto snapshot = workflow(handle)->snapshot();
    const auto path = snapshot.target.path;

    const crypty::filesystem::ReadAt read_at =
        [&path](std::uint64_t offset,
                std::uint8_t* output,
                std::size_t capacity) {
            return read_media(path, offset, output, capacity);
        };

    crypty::recovery::RecoveryEngine engine;
    const auto results = engine.scan(read_at);

    workflow(handle)->set_recovery_candidates(results);
    return results.size();
}

CRYPTY_API std::uintmax_t crypty_workflow_recover_ntfs_file(
    void* handle,
    std::size_t index,
    const char* destination,
    int* complete
) {
    if (complete != nullptr) *complete = 0;
    if (handle == nullptr || destination == nullptr) return 0;

    const auto snapshot = workflow(handle)->snapshot();
    if (index >= snapshot.files.size()) return 0;

    const auto path = snapshot.target.path;

    const crypty::filesystem::ReadAt read_at =
        [&path](std::uint64_t offset,
                std::uint8_t* output,
                std::size_t capacity) {
            return read_media(path, offset, output, capacity);
        };

    crypty::recovery::RecoveryEngine engine;
    const auto result = engine.recover(
        read_at, snapshot.files[index], destination
    );

    if (complete != nullptr) *complete = result.success ? 1 : 0;
    return static_cast<std::uintmax_t>(result.bytes_recovered);
}


// Bounded read-only byte access for the evidence hex viewer.
CRYPTY_API std::size_t crypty_workflow_read_media(void* handle, std::uint64_t offset,
                                                   std::uint8_t* output, std::size_t capacity) {
    if (handle == nullptr) return 0;
    return read_media(workflow(handle)->snapshot().target.path, offset, output, capacity);
}


// Recovery timestamps C++ to Python native bridge
CRYPTY_API const char* crypty_workflow_file_created(
    void* handle,
    std::size_t index
) {
    if (handle == nullptr) {
        return "";
    }

    const auto& files =
        workflow(handle)->snapshot().files;

    if (index >= files.size()) {
        return "";
    }

    return files[index].created.c_str();
}

CRYPTY_API const char* crypty_workflow_file_modified(
    void* handle,
    std::size_t index
) {
    if (handle == nullptr) {
        return "";
    }

    const auto& files =
        workflow(handle)->snapshot().files;

    if (index >= files.size()) {
        return "";
    }

    return files[index].modified.c_str();
}

CRYPTY_API const char* crypty_workflow_file_accessed(
    void* handle,
    std::size_t index
) {
    if (handle == nullptr) {
        return "";
    }

    const auto& files =
        workflow(handle)->snapshot().files;

    if (index >= files.size()) {
        return "";
    }

    return files[index].accessed.c_str();
}

}
