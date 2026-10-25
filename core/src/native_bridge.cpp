#include <crypty/workflow.hpp>
#include <crypty/platform/device_access.hpp>
#include "../reporting/report.hpp"
#include "../recovery/recovery_engine.hpp"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>
#include <algorithm>

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
