
#pragma once

#include <cstdint>

namespace crypty::filesystem {

enum class FilesystemType {
    Unknown,
    NTFS,
    FAT32,
    exFAT
};

enum class DetectionStatus {
    Detected,
    Unknown,
    Unsupported,
    InvalidMetadata,
    IoError
};

struct FilesystemInfo {
    FilesystemType type = FilesystemType::Unknown;
    DetectionStatus status = DetectionStatus::Unknown;

    // Validated geometry. Zero means unavailable.
    std::uint64_t volume_size_bytes = 0;
    std::uint64_t total_sectors = 0;
    std::uint64_t cluster_size_bytes = 0;

    std::uint32_t sector_size_bytes = 0;
    std::uint32_t sectors_per_cluster = 0;
};

} // namespace crypty::filesystem
