
#pragma once

#include "types.hpp"
#include <cstdint>

namespace crypty::filesystem {

struct VolumeInfo {
    FilesystemInfo filesystem;

    // Offset of this volume within the source device or image.
    std::uint64_t volume_offset_bytes = 0;

    bool valid() const noexcept;

    bool contains(
        std::uint64_t relative_offset,
        std::uint64_t length
    ) const noexcept;

    bool absolute_offset(
        std::uint64_t relative_offset,
        std::uint64_t& result
    ) const noexcept;

    bool cluster_index_offset(
        std::uint64_t cluster_index,
        std::uint64_t& result
    ) const noexcept;
};

} // namespace crypty::filesystem
