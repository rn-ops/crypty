#include "crypty/workflow.hpp"
#include <filesystem>
namespace crypty {
Workflow::Workflow() { data_.target.path = "."; add_event("SESSION_OPENED", "Operator workspace initialized"); add_event("AUTH_BYPASSED", "Demo placeholder acknowledged"); add_event("ENGINE_READY", "Native demo engine ready"); }
void Workflow::add_event(const std::string& code, const std::string& message) { data_.audit.push_back({code, message}); }
void Workflow::select_operation(Operation operation) { data_.operation = operation; data_.target.strategy = operation == Operation::Erasure ? "Cryptographic erase + verify" : "Filesystem + carving"; data_.target.risk = operation == Operation::Erasure ? "Destructive operation" : "Read-only analysis"; data_.state = State::Ready; data_.progress = 0; data_.integrity = "Pending"; add_event("MODE_SELECTED", operation == Operation::Erasure ? "Sanitization workflow selected" : "Recovery workflow selected"); }
namespace {
crypty::FileEntry scan_entry(const std::filesystem::directory_entry& entry, std::uintmax_t& total_bytes, std::error_code& error) {
	crypty::FileEntry item;
	item.name = entry.path().filename().string();
	item.path = entry.path().string();
	if (entry.is_directory(error)) {
		item.type = "Folder";
		for (const auto& child : std::filesystem::directory_iterator(entry.path(), std::filesystem::directory_options::skip_permission_denied, error)) {
			if (error) break;
			item.children.push_back(scan_entry(child, total_bytes, error));
		}
		for (const auto& child : item.children) item.size += child.size;
	} else if (entry.is_regular_file(error)) {
		item.type = "File";
		item.size = entry.file_size(error);
		item.recoverable = item.size;
		total_bytes += item.size;
	} else item.type = "Other";
	return item;
}
}

void Workflow::inspect_target(const std::string& path) {
	data_.target.path = path;
	data_.files.clear();
	data_.total_bytes = 0;
	std::error_code error;
	const std::filesystem::path root(path);
	if (std::filesystem::is_directory(root, error)) {
		for (const auto& entry : std::filesystem::directory_iterator(root, std::filesystem::directory_options::skip_permission_denied, error)) {
			if (error) break;
			data_.files.push_back(scan_entry(entry, data_.total_bytes, error));
		}
	}
	data_.evidence_items = static_cast<int>(data_.files.size());
	data_.state = State::Inspected;
	add_event("TARGET_INSPECTED", data_.files.empty() ? "Target is empty or unavailable" : "Directory contents indexed read-only");
}
void Workflow::start() { data_.state = State::Running; data_.progress = 0; data_.integrity = "Pending"; add_event("OPERATION_STARTED", operation_name(data_.operation) + " preview started"); }
void Workflow::advance(int step) { if (data_.state != State::Running) return; data_.progress += step; if (data_.progress >= 100) { data_.progress = 100; data_.state = State::Complete; data_.integrity = "100% verified"; data_.evidence_items = data_.operation == Operation::Erasure ? 0 : 128; add_event("VERIFICATION_PASS", "Preview passed verification gate"); } }
WorkflowSnapshot Workflow::snapshot() const { return data_; }
std::string operation_name(Operation operation) { return operation == Operation::Erasure ? "Sanitization" : "Recovery"; }
}