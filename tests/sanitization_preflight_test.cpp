#include "preflight.hpp"

#include <algorithm>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

using namespace crypty::sanitization;

namespace {

void put_u16(std::vector<std::uint8_t>& bytes, std::size_t offset, std::uint16_t value) {
    bytes[offset] = static_cast<std::uint8_t>(value & 0xff);
    bytes[offset + 1] = static_cast<std::uint8_t>((value >> 8) & 0xff);
}
void put_u32(std::vector<std::uint8_t>& bytes, std::size_t offset, std::uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) bytes[offset + i] = static_cast<std::uint8_t>((value >> (8 * i)) & 0xff);
}
void put_u64(std::vector<std::uint8_t>& bytes, std::size_t offset, std::uint64_t value) {
    for (unsigned i = 0; i < 8; ++i) bytes[offset + i] = static_cast<std::uint8_t>((value >> (8 * i)) & 0xff);
}
std::uint32_t crc32(const std::uint8_t* data, std::size_t size) {
    std::uint32_t crc = 0xffffffffU;
    for (std::size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for (unsigned bit = 0; bit < 8; ++bit) {
            const std::uint32_t mask = 0U - (crc & 1U);
            crc = (crc >> 1) ^ (0xedb88320U & mask);
        }
    }
    return ~crc;
}

crypty::filesystem::ReadAt memory_reader(const std::vector<std::uint8_t>& bytes) {
    return [&bytes](std::uint64_t offset, std::uint8_t* output, std::size_t size) -> std::size_t {
        if (output == nullptr || offset > bytes.size() || size > bytes.size() - static_cast<std::size_t>(offset)) return 0;
        std::copy_n(bytes.data() + static_cast<std::size_t>(offset), size, output);
        return size;
    };
}

std::vector<std::uint8_t> make_mbr_ntfs_disk() {
    constexpr std::uint32_t sector_size = 512;
    constexpr std::uint64_t total_sectors = 80000;
    constexpr std::uint32_t partition_start = 2048;
    constexpr std::uint32_t partition_sectors = 60000;
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(total_sectors * sector_size), 0);
    bytes[510] = 0x55;
    bytes[511] = 0xAA;
    const std::size_t entry = 446;
    bytes[entry + 4] = 0x07;
    put_u32(bytes, entry + 8, partition_start);
    put_u32(bytes, entry + 12, partition_sectors);

    const std::size_t boot = static_cast<std::size_t>(partition_start) * sector_size;
    bytes[boot + 3] = 'N'; bytes[boot + 4] = 'T'; bytes[boot + 5] = 'F';
    bytes[boot + 6] = 'S'; bytes[boot + 7] = ' '; bytes[boot + 8] = ' '; 
    bytes[boot + 9] = ' '; bytes[boot + 10] = ' ';
    put_u16(bytes, boot + 11, 512);
    bytes[boot + 13] = 8;
    put_u64(bytes, boot + 40, 60000);
    put_u64(bytes, boot + 48, 4);
    bytes[boot + 64] = static_cast<std::uint8_t>(-10);
    bytes[boot + 510] = 0x55;
    bytes[boot + 511] = 0xAA;
    return bytes;
}

std::vector<std::uint8_t> make_gpt_disk() {
    constexpr std::uint32_t sector_size = 512;
    constexpr std::uint64_t total_sectors = 100000;
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(total_sectors * sector_size), 0);
    // Protective MBR.
    bytes[510] = 0x55; bytes[511] = 0xAA;
    bytes[446 + 4] = 0xEE;
    put_u32(bytes, 446 + 8, 1);
    put_u32(bytes, 446 + 12, static_cast<std::uint32_t>(total_sectors - 1));

    // One GPT entry in the standard 128-entry array at LBA 2.
    const std::size_t entries_offset = 2 * sector_size;
    bytes[entries_offset] = 0x28; // Non-zero type GUID means entry is occupied.
    bytes[entries_offset + 16] = 0x42; // Unique GUID nonzero as well.
    put_u64(bytes, entries_offset + 32, 2048);
    put_u64(bytes, entries_offset + 40, 62047);
    constexpr std::size_t entries_bytes = 128 * 128;
    const auto entries_crc = crc32(bytes.data() + entries_offset, entries_bytes);

    const std::size_t header_offset = sector_size;
    std::copy_n("EFI PART", 8, bytes.data() + header_offset);
    put_u32(bytes, header_offset + 8, 0x00010000);
    put_u32(bytes, header_offset + 12, 92);
    put_u64(bytes, header_offset + 24, 1);
    put_u64(bytes, header_offset + 32, total_sectors - 1);
    put_u64(bytes, header_offset + 40, 34);
    put_u64(bytes, header_offset + 48, total_sectors - 34);
    bytes[header_offset + 56] = 0x11; // Disk GUID is nonzero.
    put_u64(bytes, header_offset + 72, 2);
    put_u32(bytes, header_offset + 80, 128);
    put_u32(bytes, header_offset + 84, 128);
    put_u32(bytes, header_offset + 88, entries_crc);
    put_u32(bytes, header_offset + 16, 0);
    const auto header_crc = crc32(bytes.data() + header_offset, 92);
    put_u32(bytes, header_offset + 16, header_crc);
    return bytes;
}

bool test_mbr_filesystem_inspection() {
    const auto bytes = make_mbr_ntfs_disk();
    crypty::platform::PhysicalDeviceInfo device;
    device.device_path = "memory://mbr-test";
    device.stable_id = "test:disk-1";
    device.capacity_bytes = bytes.size();
    device.logical_sector_size = 512;
    device.physical_sector_size = 4096;
    device.read_only_status_known = true;
    device.os_volume_membership_known = true;
    device.contains_os_volume = false;
    device.metadata_complete = true;

    const auto result = inspect_physical_device(device, memory_reader(bytes));
    return result.status == InspectionStatus::Inspected &&
           result.partition_table == PartitionTableType::MBR &&
           result.partitions.size() == 1 &&
           result.partitions[0].partition.offset_bytes == 2048ULL * 512 &&
           result.partitions[0].filesystem.type == crypty::filesystem::FilesystemType::NTFS &&
           result.partitions[0].filesystem.status == crypty::filesystem::DetectionStatus::Detected &&
           !result.execution_allowed;
}

bool test_gpt_crc_and_partition_bounds() {
    const auto bytes = make_gpt_disk();
    const auto scan = scan_partition_table(memory_reader(bytes), 512, bytes.size());
    return scan.status == InspectionStatus::Inspected &&
           scan.table_type == PartitionTableType::GPT &&
           scan.partitions.size() == 1 &&
           scan.partitions[0].start_lba == 2048 &&
           scan.partitions[0].sector_count == 60000;
}

bool test_invalid_mbr_range_rejected() {
    auto bytes = make_mbr_ntfs_disk();
    put_u32(bytes, 446 + 8, 79000);
    put_u32(bytes, 446 + 12, 5000);
    const auto scan = scan_partition_table(memory_reader(bytes), 512, bytes.size());
    return scan.status == InspectionStatus::Failed && scan.partitions.empty();
}

bool test_bad_gpt_crc_rejected() {
    auto bytes = make_gpt_disk();
    bytes[512 + 20] ^= 0x80;
    const auto scan = scan_partition_table(memory_reader(bytes), 512, bytes.size());
    return scan.status == InspectionStatus::Failed && scan.partitions.empty();
}

} // namespace

int main() {
    if (!test_mbr_filesystem_inspection()) {
        std::cerr << "MBR/filesystem inspection test failed.\n";
        return 1;
    }
    if (!test_gpt_crc_and_partition_bounds()) {
        std::cerr << "GPT CRC/partition test failed.\n";
        return 1;
    }
    if (!test_invalid_mbr_range_rejected()) {
        std::cerr << "Invalid MBR range test failed.\n";
        return 1;
    }
    if (!test_bad_gpt_crc_rejected()) {
        std::cerr << "Bad GPT CRC test failed.\n";
        return 1;
    }
    std::cout << "All sanitization preflight tests passed.\n";
    return 0;
}
