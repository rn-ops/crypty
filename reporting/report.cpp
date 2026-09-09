#include "report.hpp"
#include <fstream>
#include <iomanip>
#include <sstream>

namespace crypty {

namespace {
std::string json_string(const std::string& value) {
	std::ostringstream escaped;
	for (const char character : value) {
		switch (character) {
		case '\\': escaped << "\\\\"; break;
		case '"': escaped << "\\\""; break;
		case '\n': escaped << "\\n"; break;
		case '\r': escaped << "\\r"; break;
		case '\t': escaped << "\\t"; break;
		default: escaped << character; break;
		}
	}
	return escaped.str();
}

void write_file(std::ostream& output, const FileEntry& file, int indent) {
	const std::string padding(static_cast<std::size_t>(indent), ' ');
	output << padding << "{\"name\":\"" << json_string(file.name)
		   << "\",\"type\":\"" << json_string(file.type)
		   << "\",\"path\":\"" << json_string(file.path)
		   << "\",\"size\":" << file.size
		   << ",\"recoverable\":" << file.recoverable << "}";
}
}

bool write_report(const WorkflowSnapshot& snapshot, const std::string& filename) {
	std::ofstream report(filename);
	if (!report) return false;

	report << "{\n"
		   << "  \"product\": \"Crypty\",\n"
		   << "  \"caseId\": \"CASE-0248\",\n"
		   << "  \"operation\": \""
		   << (snapshot.operation == Operation::Erasure ? "sanitization" : "recovery")
		   << "\",\n"
		   << "  \"target\": \"" << json_string(snapshot.target.path) << "\",\n"
		   << "  \"state\": " << static_cast<int>(snapshot.state) << ",\n"
		   << "  \"progress\": " << snapshot.progress << ",\n"
		   << "  \"evidenceItems\": " << snapshot.evidence_items << ",\n"
		   << "  \"totalBytes\": " << snapshot.total_bytes << ",\n"
		   << "  \"integrity\": \"" << json_string(snapshot.integrity) << "\",\n"
		   << "  \"files\": [";
	for (std::size_t index = 0; index < snapshot.files.size(); ++index) {
		if (index != 0) report << ',';
		report << '\n';
		write_file(report, snapshot.files[index], 4);
	}
	if (!snapshot.files.empty()) report << '\n';
	report << "  ],\n  \"audit\": [";
	for (std::size_t index = 0; index < snapshot.audit.size(); ++index) {
		if (index != 0) report << ',';
		report << "{\"code\":\"" << json_string(snapshot.audit[index].code)
			   << "\",\"message\":\"" << json_string(snapshot.audit[index].message)
			   << "\"}";
	}
	report << "]\n}\n";
	return true;
}
}