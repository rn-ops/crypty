
#include "detector.hpp"

#include <cstring>
#include <cstdint>
#include <limits>
#include <vector>

namespace crypty::filesystem {
namespace {

constexpr std::size_t BOOT_SIZE = 512;
constexpr std::uint64_t FAT32_MIN_CLUSTERS = 65525;

std::uint16_t u16(const std::uint8_t* p) {
    return static_cast<std::uint16_t>(p[0]) |
           (static_cast<std::uint16_t>(p[1]) << 8);
}

std::uint32_t u32(const std::uint8_t* p) {
    return static_cast<std::uint32_t>(u16(p)) |
           (static_cast<std::uint32_t>(u16(p + 2)) << 16);
}

std::uint64_t u64(const std::uint8_t* p) {
    return static_cast<std::uint64_t>(u32(p)) |
           (static_cast<std::uint64_t>(u32(p + 4)) << 32);
}

bool power_of_two(std::uint32_t value) {
    return value != 0 && (value & (value - 1)) == 0;
}

bool boot_signature(const std::uint8_t* b) {
    return b[510] == 0x55 && b[511] == 0xAA;
}

bool checked_add(
    std::uint64_t a,
    std::uint64_t b,
    std::uint64_t& result
) {
    if (a > std::numeric_limits<std::uint64_t>::max() - b)
        return false;

    result = a + b;
    return true;
}

bool checked_mul(
    std::uint64_t a,
    std::uint64_t b,
    std::uint64_t& result
) {
    if (b != 0 &&
        a > std::numeric_limits<std::uint64_t>::max() / b)
        return false;

    result = a * b;
    return true;
}

FilesystemInfo result(
    FilesystemType type,
    DetectionStatus status
) {
    FilesystemInfo info;
    info.type = type;
    info.status = status;
    return info;
}

FilesystemInfo invalid() {
    return result(
        FilesystemType::Unknown,
        DetectionStatus::InvalidMetadata
    );
}

FilesystemInfo unknown() {
    return result(
        FilesystemType::Unknown,
        DetectionStatus::Unknown
    );
}

FilesystemInfo io_error() {
    return result(
        FilesystemType::Unknown,
        DetectionStatus::IoError
    );
}

bool valid_sector_size(std::uint32_t size) {
    return size >= 512 && size <= 4096 && power_of_two(size);
}

FilesystemInfo detect_ntfs(const std::uint8_t* b) {
    if (std::memcmp(b + 3, "NTFS    ", 8) != 0)
        return unknown();

    const std::uint32_t sector_size = u16(b + 11);
    const std::uint32_t sectors_per_cluster = b[13];
    const std::uint64_t total_sectors = u64(b + 40);
    const std::uint64_t mft_lcn = u64(b + 48);
    const std::int8_t record_encoding =
        static_cast<std::int8_t>(b[64]);

    if (!boot_signature(b) ||
        !valid_sector_size(sector_size) ||
        !power_of_two(sectors_per_cluster) ||
        sectors_per_cluster > 128 ||
        total_sectors == 0 ||
        record_encoding == 0) {
        return invalid();
    }

    const std::uint64_t cluster_count =
        total_sectors / sectors_per_cluster;

    if (mft_lcn >= cluster_count)
        return invalid();

    // NTFS encodes a positive record size as clusters per record,
    // or a negative value as log2(record size) in bytes.
    std::uint64_t record_size = 0;

    if (record_encoding > 0) {
        if (!checked_mul(
                static_cast<std::uint64_t>(record_encoding),
                static_cast<std::uint64_t>(sector_size) *
                    sectors_per_cluster,
                record_size)) {
            return invalid();
        }
    } else {
        const unsigned exponent =
            static_cast<unsigned>(-static_cast<int>(record_encoding));

        if (exponent < 9 || exponent > 20)
            return invalid();

        record_size = std::uint64_t{1} << exponent;
    }

    if (record_size < 512 || record_size > 1024 * 1024)
        return invalid();

    std::uint64_t volume_size = 0;

    if (!checked_mul(total_sectors, sector_size, volume_size))
        return invalid();

    auto info = result(
        FilesystemType::NTFS,
        DetectionStatus::Detected
    );

    info.sector_size_bytes = sector_size;
    info.volume_size_bytes = volume_size;
    return info;
}

FilesystemInfo detect_fat32(const std::uint8_t* b) {
    const std::uint32_t sector_size = u16(b + 11);
    const std::uint32_t sectors_per_cluster = b[13];
    const std::uint32_t reserved = u16(b + 14);
    const std::uint32_t fats = b[16];
    const std::uint32_t root_entries = u16(b + 17);
    const std::uint32_t total16 = u16(b + 19);
    const std::uint32_t fat16 = u16(b + 22);
    const std::uint64_t total32 = u32(b + 32);
    const std::uint64_t fat32 = u32(b + 36);
    const std::uint32_t root_cluster = u32(b + 44);
    const std::uint16_t fs_version = u16(b + 42);

    if (!boot_signature(b) ||
        !valid_sector_size(sector_size) ||
        !power_of_two(sectors_per_cluster) ||
        sectors_per_cluster > 128 ||
        reserved == 0 ||
        (fats != 1 && fats != 2) ||
        root_entries != 0 ||
        total16 != 0 ||
        fat16 != 0 ||
        total32 == 0 ||
        fat32 == 0 ||
        fs_version != 0) {
        return invalid();
    }

    std::uint64_t fat_area = 0;
    std::uint64_t first_data_sector = 0;

    if (!checked_mul(fats, fat32, fat_area) ||
        !checked_add(reserved, fat_area, first_data_sector) ||
        first_data_sector >= total32) {
        return invalid();
    }

    const std::uint64_t cluster_count =
        (total32 - first_data_sector) / sectors_per_cluster;

    // FAT12/FAT16 must not be accepted as FAT32.
    if (cluster_count < FAT32_MIN_CLUSTERS ||
        root_cluster < 2 ||
        root_cluster >= cluster_count + 2) {
        return invalid();
    }

    std::uint64_t fat_capacity = 0;

    if (!checked_mul(fat32, sector_size, fat_capacity))
        return invalid();

    // Each FAT entry occupies four bytes in FAT32.
    if (fat_capacity / 4 < cluster_count + 2)
        return invalid();

    std::uint64_t volume_size = 0;

    if (!checked_mul(total32, sector_size, volume_size))
        return invalid();

    auto info = result(
        FilesystemType::FAT32,
        DetectionStatus::Detected
    );

    info.sector_size_bytes = sector_size;
    info.volume_size_bytes = volume_size;
    return info;
}


FilesystemInfo detect_exfat(
    const ReadAt& read_at,
    const std::uint8_t* boot
) {
    if (std::memcmp(boot + 3, "EXFAT   ", 8) != 0)
        return unknown();

    const unsigned sector_shift = boot[108];
    const unsigned cluster_shift = boot[109];

    if (sector_shift < 9 || sector_shift > 12 ||
        cluster_shift > 25 ||
        sector_shift + cluster_shift > 25) {
        return invalid();
    }

    const std::size_t sector_size =
        std::size_t{1} << sector_shift;

    constexpr std::size_t BOOT_SECTORS = 12;

    if (sector_size >
        std::numeric_limits<std::size_t>::max() / BOOT_SECTORS) {
        return invalid();
    }

    const std::size_t region_size = sector_size * BOOT_SECTORS;
    std::vector<std::uint8_t> region(region_size);

    if (read_at(0, region.data(), region.size()) != region.size())
        return io_error();

    const auto* b = region.data();

    if (std::memcmp(b + 3, "EXFAT   ", 8) != 0 ||
        !boot_signature(b)) {
        return invalid();
    }

    // Extended boot sectors 1 through 8 have the
    // exFAT extended boot signature at bytes 508-511.
    for (std::size_t i = 1; i <= 8; ++i) {
        const auto* sector = b + i * sector_size;

        if (sector[508] != 0x00 ||
            sector[509] != 0x00 ||
            sector[510] != 0x55 ||
            sector[511] != 0xAA) {
            return invalid();
        }
    }

    // Calculate the exFAT boot checksum over sectors 0-10.
    // Three bytes in sector 0 are excluded by the specification.
    std::uint32_t checksum = 0;

    for (std::size_t i = 0; i < sector_size * 11; ++i) {
        if (i == 106 || i == 107 || i == 112)
            continue;

        checksum =
            ((checksum & 1U) ? 0x80000000U : 0U) |
            (checksum >> 1);

        checksum += b[i];
    }

    const auto* checksum_sector = b + sector_size * 11;

    for (std::size_t i = 0; i < sector_size; i += 4) {
        if (u32(checksum_sector + i) != checksum)
            return invalid();
    }

    const std::uint64_t volume_sectors = u64(b + 72);
    const std::uint64_t fat_offset     = u32(b + 80);
    const std::uint64_t fat_length     = u32(b + 84);
    const std::uint64_t heap_offset    = u32(b + 88);
    const std::uint64_t cluster_count  = u32(b + 92);
    const std::uint64_t root_cluster   = u32(b + 96);
    const unsigned fat_count = b[110];

    if (volume_sectors == 0 ||
        fat_offset == 0 ||
        fat_length == 0 ||
        cluster_count == 0 ||
        (fat_count != 1 && fat_count != 2) ||
        root_cluster < 2 ||
        root_cluster >= cluster_count + 2) {
        return invalid();
    }

    std::uint64_t fats_size = 0;
    std::uint64_t fats_end = 0;
    std::uint64_t heap_size = 0;
    std::uint64_t heap_end = 0;
    std::uint64_t fat_bytes = 0;
    std::uint64_t volume_size = 0;

    if (!checked_mul(fat_count, fat_length, fats_size) ||
        !checked_add(fat_offset, fats_size, fats_end) ||
        fats_end > heap_offset ||
        heap_offset >= volume_sectors ||
        !checked_mul(
            cluster_count,
            std::uint64_t{1} << cluster_shift,
            heap_size) ||
        !checked_add(heap_offset, heap_size, heap_end) ||
        heap_end > volume_sectors ||
        !checked_mul(fat_length, sector_size, fat_bytes) ||
        fat_bytes / 4 < cluster_count + 2 ||
        !checked_mul(volume_sectors, sector_size, volume_size)) {
        return invalid();
    }

    auto info = result(
        FilesystemType::exFAT,
        DetectionStatus::Detected
    );

    info.sector_size_bytes = static_cast<std::uint32_t>(sector_size);
    info.volume_size_bytes = volume_size;
    return info;
}


} // namespace

FilesystemInfo detect_filesystem(const ReadAt& read_at) {
    if (!read_at)
        return io_error();

    std::uint8_t boot[BOOT_SIZE]{};

    if (read_at(0, boot, sizeof(boot)) != sizeof(boot))
        return io_error();

    if (std::memcmp(boot + 3, "NTFS    ", 8) == 0)
        return detect_ntfs(boot);

    if (std::memcmp(boot + 3, "EXFAT   ", 8) == 0)
        return detect_exfat(read_at, boot);

    // FAT32 has no unique, reliable OEM identifier.
    // Only accept it when its BPB geometry passes validation.
    // No boot signature means there is insufficient evidence
    // to classify this as a malformed FAT32 boot sector.
    if (!boot_signature(boot))
        return unknown();

    // FAT32 has no unique, reliable OEM identifier.
    return detect_fat32(boot);
}

} // namespace crypty::filesystem
