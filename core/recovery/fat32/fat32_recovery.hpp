
#pragma once

#include "../../reader.hpp"
#include "../../src/workflow.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace crypty::recovery::fat32 {

using crypty::filesystem::ReadAt;
using crypty::FileEntry;

class Fat32Recovery {
public:
    static std::vector<FileEntry> find_deleted_entries(
        const ReadAt& read_at
    );

    static std::uintmax_t recover_to(
        const ReadAt& read_at,
        const FileEntry& entry,
        const std::string& destination,
        bool& complete
    );
};

} // namespace crypty::recovery::fat32
