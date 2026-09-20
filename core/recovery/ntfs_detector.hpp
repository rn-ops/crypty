#pragma once

#include "fat32_detector.hpp"

#include <string>
#include <cstdint>
#include <vector>

namespace crypty::recovery {

class NtfsDetector {
public:
    static std::vector<FileEntry> find_entries(
        const ReadAt& read_at
    );

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

}