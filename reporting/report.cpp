#include "report.hpp"
#include <fstream>
namespace crypty {
bool write_report(const WorkflowSnapshot& snapshot, const std::string& filename) { std::ofstream report(filename); if (!report) return false; report << "{\n  \"product\": \"Crypty\",\n  \"caseId\": \"CASE-0248\",\n  \"operation\": \"" << (snapshot.operation == Operation::Erasure ? "erasure-preview" : "recovery-preview") << "\",\n  \"target\": \"" << snapshot.target.path << "\",\n  \"verification\": \"" << (snapshot.state == State::Complete ? "verified-simulated" : "not-run") << "\",\n  \"reference\": \"NIST SP 800-88 Rev. 2 (reference only)\",\n  \"demo\": true\n}\n"; return true; }
}