#include "crypty/workflow.hpp"
#include "report.hpp"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

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

const std::vector<Device>& devices() {
    static const std::vector<Device> value = detect_devices();
    return value;
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
}