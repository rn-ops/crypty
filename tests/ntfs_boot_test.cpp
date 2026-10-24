#include "recovery/ntfs/ntfs_recovery.hpp"

#include <array>
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <vector>

namespace {

template <typename Integer>
void write_le(
    std::array<std::uint8_t, 512>& sector,
    std::size_t offset,
    Integer value
) {
    for (std::size_t index = 0; index < sizeof(Integer); ++index) {
        sector[offset + index] =
            static_cast<std::uint8_t>(value >> (index * 8));
    }
}

} // namespace

int main() {
    std::array<std::uint8_t, 512> sector{};
    std::memcpy(sector.data() + 3, "NTFS    ", 8);
    write_le<std::uint16_t>(sector, 11, 512);
    sector[13] = 8;
    write_le<std::uint64_t>(sector, 40, 4096);
    write_le<std::uint64_t>(sector, 48, 4);
    sector[64] = 0xF6;

    const crypty::filesystem::ReadAt read_at =
        [&sector](
            std::uint64_t offset,
            std::uint8_t* output,
            std::size_t capacity
        ) {
            if (offset != 0 || capacity > sector.size()) return std::size_t{0};
            std::copy_n(sector.data(), capacity, output);
            return capacity;
        };

    crypty::recovery::ntfs::NtfsVolumeInfo result;
    assert(crypty::recovery::ntfs::locate_ntfs_volume(read_at, result));
    assert(result.bytes_per_sector == 512);
    assert(result.sectors_per_cluster == 8);
    assert(result.cluster_size_bytes == 4096);
    assert(result.volume_size_bytes == 2 * 1024 * 1024);
    assert(result.mft_offset_bytes == 16 * 1024);
    assert(result.record_size_bytes == 1024);

    sector[3] = 'X';
    assert(!crypty::recovery::ntfs::locate_ntfs_volume(read_at, result));
    assert(result.volume_size_bytes == 0);

    return 0;
}
