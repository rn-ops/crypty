#pragma once

#include "fat32_detector.hpp"

#include <vector>

namespace crypty::recovery {

class ExFatDetector {
public:
    static std::vector<FileEntry> find_deleted_entries(
        const ReadAt& read_at
    );
};

}