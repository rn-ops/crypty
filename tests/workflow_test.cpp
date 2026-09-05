#include "crypty/workflow.hpp"
#include <cassert>
#include <filesystem>
#include <fstream>

int main() {
    crypty::Workflow workflow;
    workflow.select_operation(crypty::Operation::Recovery);
    const auto fixture = std::filesystem::temp_directory_path() / "crypty-fixture";
    std::filesystem::create_directories(fixture);
    std::ofstream(fixture / "evidence.txt") << "fixture";
    workflow.inspect_target(fixture.string());
    assert(workflow.snapshot().files.size() == 1);
    assert(workflow.snapshot().files.front().name == "evidence.txt");
    assert(workflow.snapshot().evidence_items == 1);
    workflow.start();
    for (int step = 0; step < 5; ++step) workflow.advance();
    const auto result = workflow.snapshot();
    assert(result.state == crypty::State::Complete);
    assert(result.progress == 100);
    assert(result.evidence_items == 128);
    assert(result.integrity == "100% verified");
    std::filesystem::remove_all(fixture);
    return 0;
}