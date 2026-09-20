#pragma once

#include "crypty/workflow.hpp"

#include <cstdint>
#include <functional>
#include <vector>

namespace crypty::recovery {
using ReadAt = std::function<std::size_t(std::uint64_t, std::uint8_t*, std::size_t)>;

// First pipeline stage: validates FAT32 and reports root-directory deleted entries.
// It never writes through ReadAt and does not reconstruct cluster chains yet.
class Fat32Detector {
public:
    static std::vector<FileEntry> find_deleted_entries(const ReadAt& read_at);
    // Writes only to destination. Returns bytes recovered; complete is false for a broken chain.
    static std::uintmax_t recover_to(const ReadAt& read_at, const FileEntry& entry,
                                     const std::string& destination, bool& complete);
};
}
