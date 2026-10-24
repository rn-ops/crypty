
#pragma once

#include "../../reader.hpp"
#include "../../types.hpp"
#include "../../src/workflow.hpp"

#include <cstdint>
#include <vector>

namespace crypty::recovery::ntfs {

using crypty::filesystem::ReadAt;
using crypty::FileEntry;

struct NtfsVolumeInfo {
    std::uint64_t volume_offset_bytes = 0;
    std::uint64_t volume_size_bytes = 0;
    std::uint64_t total_sectors = 0;
    std::uint64_t mft_lcn = 0;
    std::uint64_t mft_offset_bytes = 0;
    std::uint64_t cluster_size_bytes = 0;
    std::uint32_t record_size_bytes = 0;
    std::uint32_t bytes_per_sector = 0;
    std::uint32_t sectors_per_cluster = 0;
};

bool locate_ntfs_volume(
    const ReadAt& read_at,
    NtfsVolumeInfo& result
);

std::vector<FileEntry> scan_mft(const ReadAt& read_at);

} // namespace crypty::recovery::ntfs
