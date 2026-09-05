#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace crypty {
enum class Operation { Recovery, Erasure };
enum class State { Ready, Inspected, Running, Complete };
struct TargetProfile { std::string path = "D:\\Evidence\\Case-0248"; std::string medium = "External SSD / NTFS"; std::string strategy = "Filesystem + carving"; std::string risk = "Read-only analysis"; };
struct FileEntry { std::string name; std::string type; std::string path; std::uintmax_t size = 0; std::uintmax_t recoverable = 0; std::vector<FileEntry> children; };
struct AuditEvent { std::string code; std::string message; };
struct WorkflowSnapshot { Operation operation = Operation::Recovery; State state = State::Ready; TargetProfile target; int progress = 0; int evidence_items = 0; std::uintmax_t total_bytes = 0; std::vector<FileEntry> files; std::string integrity = "Pending"; std::vector<AuditEvent> audit; };
class Workflow {
public:
    Workflow();
    void select_operation(Operation operation);
    void inspect_target(const std::string& path);
    void start();
    void advance(int step = 20);
    WorkflowSnapshot snapshot() const;
private:
    WorkflowSnapshot data_;
    void add_event(const std::string& code, const std::string& message);
};
std::string operation_name(Operation operation);
}