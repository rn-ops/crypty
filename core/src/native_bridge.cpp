#include "crypty/workflow.hpp"

#include <cstddef>

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
}