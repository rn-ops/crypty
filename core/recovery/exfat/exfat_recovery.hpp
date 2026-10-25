
#pragma once

#include <crypty/filesystem/reader.hpp>
#include <crypty/workflow.hpp>

#include <vector>

namespace crypty::recovery::exfat {

using crypty::filesystem::ReadAt;
using crypty::FileEntry;

class ExFatRecovery {
public:
    static std::vector<FileEntry> find_deleted_entries(
        const ReadAt& read_at
    );
};

} // namespace crypty::recovery::exfat
