
#include "filesystem/detector.hpp"

#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <vector>

using crypty::filesystem::DetectionStatus;
using crypty::filesystem::FilesystemInfo;
using crypty::filesystem::FilesystemType;
using crypty::filesystem::ReadAt;
using crypty::filesystem::detect_filesystem;

using Image = std::vector<std::uint8_t>;

constexpr std::size_t SECTOR_SIZE = 512;
constexpr std::size_t EXFAT_BOOT_SECTORS = 12;

void set_u16(Image& b, std::size_t offset, std::uint16_t value) {
    b[offset] = static_cast<std::uint8_t>(value);
    b[offset + 1] = static_cast<std::uint8_t>(value >> 8);
}

void set_u32(Image& b, std::size_t offset, std::uint32_t value) {
    set_u16(b, offset, static_cast<std::uint16_t>(value));
    set_u16(b, offset + 2, static_cast<std::uint16_t>(value >> 16));
}

void set_u64(Image& b, std::size_t offset, std::uint64_t value) {
    set_u32(b, offset, static_cast<std::uint32_t>(value));
    set_u32(b, offset + 4, static_cast<std::uint32_t>(value >> 32));
}

void set_signature(Image& b) {
    b[510] = 0x55;
    b[511] = 0xAA;
}

std::uint32_t exfat_boot_checksum(const Image& b) {
    std::uint32_t checksum = 0;
    const std::size_t checksum_length = SECTOR_SIZE * 11;

    for (std::size_t i = 0; i < checksum_length; ++i) {
        if (i == 106 || i == 107 || i == 112)
            continue;

        checksum =
            ((checksum & 1U) ? 0x80000000U : 0U) |
            (checksum >> 1);

        checksum += b[i];
    }

    return checksum;
}

void finalize_exfat_boot_region(Image& b) {
    // Extended boot sectors 1 through 8.
    for (std::size_t sector = 1; sector <= 8; ++sector) {
        const std::size_t offset = sector * SECTOR_SIZE;

        b[offset + 508] = 0x00;
        b[offset + 509] = 0x00;
        b[offset + 510] = 0x55;
        b[offset + 511] = 0xAA;
    }

    // Sector 11 contains the checksum repeated as 32-bit words.
    const std::uint32_t checksum = exfat_boot_checksum(b);
    const std::size_t checksum_offset = SECTOR_SIZE * 11;

    for (std::size_t i = 0; i < SECTOR_SIZE; i += 4)
        set_u32(b, checksum_offset + i, checksum);
}

Image make_ntfs() {
    Image b(SECTOR_SIZE, 0);

    std::memcpy(b.data() + 3, "NTFS    ", 8);
    set_u16(b, 11, 512);
    b[13] = 8;
    set_u64(b, 40, 100000);
    set_u64(b, 48, 4);
    b[64] = 0xF6; // -10: file record size = 2^10 = 1024 bytes.
    set_signature(b);

    return b;
}

Image make_fat32() {
    Image b(SECTOR_SIZE, 0);

    set_u16(b, 11, 512);
    b[13] = 1;
    set_u16(b, 14, 32);
    b[16] = 2;
    set_u16(b, 17, 0);
    set_u16(b, 19, 0);
    set_u16(b, 22, 0);
    set_u32(b, 32, 70000);
    set_u32(b, 36, 600);
    set_u32(b, 44, 2);
    set_signature(b);

    return b;
}

Image make_exfat() {
    Image b(SECTOR_SIZE * EXFAT_BOOT_SECTORS, 0);

    std::memcpy(b.data() + 3, "EXFAT   ", 8);

    set_u64(b, 64, 0);       // Partition offset.
    set_u64(b, 72, 100000);  // Volume length in sectors.
    set_u32(b, 80, 24);      // FAT offset.
    set_u32(b, 84, 100);     // FAT length.
    set_u32(b, 88, 224);     // Cluster heap offset.
    set_u32(b, 92, 1000);    // Cluster count.
    set_u32(b, 96, 2);       // Root directory cluster.

    b[108] = 9;  // 512 bytes per sector.
    b[109] = 0;  // One sector per cluster.
    b[110] = 1;  // One FAT.

    set_signature(b);
    finalize_exfat_boot_region(b);

    return b;
}

FilesystemInfo detect(const Image& image) {
    return detect_filesystem(
        [&image](std::uint64_t offset,
                 std::uint8_t* buffer,
                 std::size_t size) -> std::size_t {
            if (offset > image.size())
                return 0;

            const auto start = static_cast<std::size_t>(offset);

            if (size > image.size() - start)
                return 0;

            std::memcpy(buffer, image.data() + start, size);
            return size;
        }
    );
}

void test_ntfs() {
    const auto result = detect(make_ntfs());

    assert(result.status == DetectionStatus::Detected);
    assert(result.type == FilesystemType::NTFS);
    assert(result.sector_size_bytes == 512);
    assert(result.volume_size_bytes == 512ULL * 100000);
}

void test_ntfs_invalid_cluster_size() {
    auto boot = make_ntfs();
    boot[13] = 3; // Not a power of two.

    assert(detect(boot).status == DetectionStatus::InvalidMetadata);
}

void test_ntfs_invalid_record_encoding() {
    auto boot = make_ntfs();
    boot[64] = 0;

    assert(detect(boot).status == DetectionStatus::InvalidMetadata);
}

void test_fat32() {
    const auto result = detect(make_fat32());

    assert(result.status == DetectionStatus::Detected);
    assert(result.type == FilesystemType::FAT32);
    assert(result.sector_size_bytes == 512);
    assert(result.volume_size_bytes == 512ULL * 70000);
}

void test_fat32_invalid_fat_capacity() {
    auto boot = make_fat32();

    // FAT is too small for the required cluster entries.
    set_u32(boot, 36, 1);

    assert(detect(boot).status == DetectionStatus::InvalidMetadata);
}

void test_exfat() {
    const auto result = detect(make_exfat());

    assert(result.status == DetectionStatus::Detected);
    assert(result.type == FilesystemType::exFAT);
    assert(result.sector_size_bytes == 512);
    assert(result.volume_size_bytes == 512ULL * 100000);
}

void test_exfat_invalid_cluster_geometry() {
    auto boot = make_exfat();
    boot[109] = 30;

    assert(detect(boot).status == DetectionStatus::InvalidMetadata);
}

void test_exfat_invalid_checksum() {
    auto boot = make_exfat();

    // Corrupt the stored checksum without updating the boot region.
    boot[SECTOR_SIZE * 11] ^= 0x01;

    assert(detect(boot).status == DetectionStatus::InvalidMetadata);
}

void test_exfat_truncated_boot_region() {
    auto boot = make_exfat();
    boot.resize(SECTOR_SIZE);

    // The first sector is readable, but the complete exFAT boot
    // region is not available.
    assert(detect(boot).status == DetectionStatus::IoError);
}

void test_invalid_ntfs() {
    auto boot = make_ntfs();
    set_u16(boot, 11, 0);

    assert(detect(boot).status == DetectionStatus::InvalidMetadata);
}

void test_unknown_filesystem() {
    Image boot(SECTOR_SIZE, 0);

    assert(detect(boot).status == DetectionStatus::Unknown);
}

void test_short_read() {
    const auto result = detect_filesystem(
        [](std::uint64_t, std::uint8_t*, std::size_t) {
            return std::size_t{128};
        }
    );

    assert(result.status == DetectionStatus::IoError);
}

void test_empty_reader() {
    assert(detect_filesystem(ReadAt{}).status == DetectionStatus::IoError);
}

int main() {
    test_ntfs();
    test_ntfs_invalid_cluster_size();
    test_ntfs_invalid_record_encoding();

    test_fat32();
    test_fat32_invalid_fat_capacity();

    test_exfat();
    test_exfat_invalid_cluster_geometry();
    test_exfat_invalid_checksum();
    test_exfat_truncated_boot_region();

    test_invalid_ntfs();
    test_unknown_filesystem();
    test_short_read();
    test_empty_reader();

    std::cout << "Filesystem detector tests passed.\n";
    return 0;
}
