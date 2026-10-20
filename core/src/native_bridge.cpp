#include "crypty/workflow.hpp"
#include "report.hpp"
#include "../recovery/recovery_engine.hpp"
#include "../filesystem/reader.hpp"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>
#include <algorithm>

#ifdef _WIN32
#include <windows.h>
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

struct Device {
    std::string path;
    std::string name;
    std::string filesystem;
    std::string media_type;
    std::string interface_name;
    std::uint64_t capacity = 0;
    std::string status;
};

std::vector<Device> detect_devices() {
    std::vector<Device> devices;
#ifdef _WIN32
    const DWORD drives = GetLogicalDrives();
    for (int index = 0; index < 26; ++index) {
        if ((drives & (1u << index)) == 0) continue;
        const std::string root = std::string(1, static_cast<char>('A' + index)) + ":\\";
        char volume_name[MAX_PATH]{};
        char filesystem_name[MAX_PATH]{};
        DWORD serial = 0;
        DWORD max_component = 0;
        DWORD flags = 0;
        if (!GetVolumeInformationA(root.c_str(), volume_name, MAX_PATH, &serial,
                                   &max_component, &flags, filesystem_name,
                                   MAX_PATH)) {
            continue;
        }
        ULARGE_INTEGER available{};
        ULARGE_INTEGER total{};
        ULARGE_INTEGER free_bytes{};
        if (!GetDiskFreeSpaceExA(root.c_str(), &available, &total, &free_bytes)) {
            continue;
        }
        const UINT drive_type = GetDriveTypeA(root.c_str());
        const bool removable = drive_type == DRIVE_REMOVABLE;
        devices.push_back({
            root,
            volume_name[0] == '\0' ? root : volume_name,
            filesystem_name,
            removable ? "Removable" : "Local volume",
            removable ? "USB / removable" : "Windows volume",
            total.QuadPart,
            "CONNECTED",
        });
    }
#else
    devices.push_back({"/", "Root filesystem", "native", "Local volume",
                       "POSIX volume", 0, "CONNECTED"});
#endif
    return devices;
}

std::vector<Device>& devices() {
    static std::vector<Device> value = detect_devices();
    return value;
}

std::string raw_media_path(const std::string& path) {
#ifdef _WIN32
    if (path.size() >= 2 && path[1] == ':') return "\\\\.\\" + path.substr(0, 2);
#endif
    return path;
}

std::size_t read_media(const std::string& path, std::uint64_t offset,
                       std::uint8_t* output, std::size_t capacity) {
    if (output == nullptr || capacity == 0) return 0;
#ifdef _WIN32

    const auto media = raw_media_path(path);

    HANDLE handle = CreateFileA(
        media.c_str(),
        GENERIC_READ,
        FILE_SHARE_READ |
        FILE_SHARE_WRITE |
        FILE_SHARE_DELETE,
        nullptr,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        nullptr
    );

    if (handle == INVALID_HANDLE_VALUE) {
        return 0;
    }

    constexpr std::uint64_t SECTOR_SIZE = 512;

    const std::uint64_t aligned_offset =
        offset -
        (offset % SECTOR_SIZE);

    const std::uint64_t offset_delta =
        offset -
        aligned_offset;

    const std::uint64_t aligned_size =
        ((offset_delta + capacity + SECTOR_SIZE - 1) /
            SECTOR_SIZE) *
        SECTOR_SIZE;

    if (aligned_size > 1024ULL * 1024ULL) {
        CloseHandle(handle);
        return 0;
    }

    std::vector<std::uint8_t> aligned_buffer(
        static_cast<std::size_t>(aligned_size)
    );

    LARGE_INTEGER position{};
    position.QuadPart =
        static_cast<LONGLONG>(aligned_offset);

    DWORD bytes_read = 0;

    const bool seek_ok =
        SetFilePointerEx(
            handle,
            position,
            nullptr,
            FILE_BEGIN
        );

    const bool read_ok =
        seek_ok &&
        ReadFile(
            handle,
            aligned_buffer.data(),
            static_cast<DWORD>(aligned_size),
            &bytes_read,
            nullptr
        );

    if (!read_ok) {

        std::printf(
            "RAW READ FAILED: offset=%llu aligned=%llu "
            "requested=%zu aligned_size=%llu error=%lu\n",
            static_cast<unsigned long long>(offset),
            static_cast<unsigned long long>(aligned_offset),
            capacity,
            static_cast<unsigned long long>(aligned_size),
            static_cast<unsigned long>(GetLastError())
        );

        CloseHandle(handle);
        return 0;
    }

    if (
        bytes_read <
        offset_delta + capacity
    ) {
        CloseHandle(handle);
        return 0;
    }

    memcpy(
        output,
        aligned_buffer.data() + offset_delta,
        capacity
    );

    std::printf(
        "RAW READ: offset=%llu requested=%zu "
        "aligned=%llu read=%lu\n",
        static_cast<unsigned long long>(offset),
        capacity,
        static_cast<unsigned long long>(aligned_offset),
        static_cast<unsigned long>(bytes_read)
    );

    CloseHandle(handle);

    return capacity;

#else

    (void)path;
    (void)offset;
    (void)output;
    (void)capacity;
    return 0;

#endif
}


}

extern "C" {
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
