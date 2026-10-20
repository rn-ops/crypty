
#include "volume_info.hpp"

#include <limits>

namespace crypty::filesystem {

bool VolumeInfo::valid() const noexcept {
    const auto& fs = filesystem;

    return fs.status == DetectionStatus::Detected &&
           fs.type != FilesystemType::Unknown &&
           fs.sector_size_bytes != 0 &&
           fs.volume_size_bytes != 0;
}

bool VolumeInfo::contains(
    std::uint64_t relative_offset,
    std::uint64_t length
) const noexcept {
    if (!valid())
        return false;

    if (relative_offset > filesystem.volume_size_bytes)
        return false;

    return length <=
        filesystem.volume_size_bytes - relative_offset;
}

bool VolumeInfo::absolute_offset(
    std::uint64_t relative_offset,
    std::uint64_t& result
) const noexcept {
    if (!contains(relative_offset, 0))
        return false;

    if (volume_offset_bytes >
        std::numeric_limits<std::uint64_t>::max() -
            relative_offset) {
        return false;
    }

    result = volume_offset_bytes + relative_offset;
    return true;
}

bool VolumeInfo::cluster_index_offset(
    std::uint64_t cluster_index,
    std::uint64_t& result
) const noexcept {
    if (!valid() || filesystem.cluster_size_bytes == 0)
        return false;

    const auto cluster_size = filesystem.cluster_size_bytes;

    if (cluster_index >
        std::numeric_limits<std::uint64_t>::max() / cluster_size) {
        return false;
    }

    const auto relative_offset = cluster_index * cluster_size;

    if (!contains(relative_offset, cluster_size))
        return false;

    return absolute_offset(relative_offset, result);
}

} // namespace crypty::filesystem
