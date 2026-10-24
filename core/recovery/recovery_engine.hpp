#pragma once

#include "../reader.hpp"
#include "../src/workflow.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace crypty::recovery {

using crypty::filesystem::ReadAt;
using crypty::FileEntry;

struct RecoveryResult {
    bool success = false;
    std::string message;
    std::uint64_t bytes_recovered = 0;
};

class RecoveryEngine {
public:
    std::vector<FileEntry> scan(const ReadAt& read_at);

    RecoveryResult recover(
        const ReadAt& read_at,
        const FileEntry& entry,
        const std::string& destination
    );
};

} // namespace crypty::recovery