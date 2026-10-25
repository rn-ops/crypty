#include "preflight.hpp"

#include "detector.hpp"
#include "volume_info.hpp"
#include <crypty/platform/device_access.hpp>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <utility>
#include <vector>

namespace crypty::sanitization {
namespace {

constexpr std::size_t kMbrSize = 512;
constexpr std::size_t kMbrPartitionTableOffset = 446;
constexpr std::size_t kMbrEntrySize = 16;
constexpr std::size_t kGptHeaderMinimumSize = 92;
constexpr std::size_t kGptEntryMinimumSize = 128;
constexpr std::uint32_t kMaximumGptEntryCount = 16384;
constexpr std::uint32_t kMaximumGptEntrySize = 4096;
constexpr std::uint64_t kMaximumGptTableBytes = 16ULL * 1024 * 1024;

std::uint16_t read_u16(const std::uint8_t* p) {
    return static_cast<std::uint16_t>(p[0]) |
           static_cast<std::uint16_t>(static_cast<std::uint16_t>(p[1]) << 8);
}

std::uint32_t read_u32(const std::uint8_t* p) {
    return static_cast<std::uint32_t>(p[0]) |
           (static_cast<std::uint32_t>(p[1]) << 8) |
           (static_cast<std::uint32_t>(p[2]) << 16) |
           (static_cast<std::uint32_t>(p[3]) << 24);
}

std::uint64_t read_u64(const std::uint8_t* p) {
    return static_cast<std::uint64_t>(read_u32(p)) |
           (static_cast<std::uint64_t>(read_u32(p + 4)) << 32);
}

std::string hex_byte(std::uint8_t value) {
    constexpr char digits[] = "0123456789ABCDEF";
    std::string out;
    out.push_back(digits[(value >> 4) & 0x0f]);
    out.push_back(digits[value & 0x0f]);
    return out;
}

std::string mbr_type_id(std::uint8_t type) {
    return "MBR:0x" + hex_byte(type);
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

bool read_exact(
    const crypty::filesystem::ReadAt& read_at,
    std::uint64_t offset,
    std::uint8_t* output,
    std::size_t size
) {
    if (!read_at || output == nullptr || size == 0) return false;

    // Keep individual platform reads within the existing Windows reader's
    // 1 MiB limit while still supporting larger GPT entry arrays.
    constexpr std::size_t kReadChunk = 1024 * 1024;
    std::size_t done = 0;
    while (done < size) {
        if (done > (std::numeric_limits<std::uint64_t>::max)() - offset) {
            return false;
        }
        const auto request = (std::min)(kReadChunk, size - done);
        const auto received = read_at(offset + done, output + done, request);
        if (received == 0 || received > request) return false;
        done += received;
    }
    return true;
}

bool checked_mul(
    std::uint64_t a,
    std::uint64_t b,
    std::uint64_t& result
) {
    if (b != 0 && a > (std::numeric_limits<std::uint64_t>::max)() / b) {
        return false;
    }
    result = a * b;
    return true;
}

bool checked_add(
    std::uint64_t a,
    std::uint64_t b,
    std::uint64_t& result
) {
    if (a > (std::numeric_limits<std::uint64_t>::max)() - b) return false;
    result = a + b;
    return true;
}

bool all_zero(const std::uint8_t* bytes, std::size_t size) {
    return std::all_of(bytes, bytes + size,
        [](std::uint8_t byte) { return byte == 0; });
}

PartitionScanResult scan_gpt(
    const crypty::filesystem::ReadAt& read_at,
    std::uint32_t sector_size,
    std::uint64_t capacity_bytes
) {
    PartitionScanResult result;
    result.table_type = PartitionTableType::GPT;

    std::vector<std::uint8_t> sector(sector_size);
    if (!read_exact(read_at, sector_size, sector.data(), sector.size())) {
        result.status = InspectionStatus::Failed;
        result.diagnostic = "Could not read the primary GPT header.";
        return result;
    }
    if (sector.size() < kGptHeaderMinimumSize ||
        std::string(reinterpret_cast<const char*>(sector.data()), 8) != "EFI PART") {
        result.status = InspectionStatus::Failed;
        result.diagnostic = "The protective MBR is present but the GPT signature is invalid.";
        return result;
    }

    const std::uint32_t header_size = read_u32(sector.data() + 12);
    const std::uint32_t expected_header_crc = read_u32(sector.data() + 16);
    const std::uint64_t current_lba = read_u64(sector.data() + 24);
    const std::uint64_t backup_lba = read_u64(sector.data() + 32);
    const std::uint64_t first_usable_lba = read_u64(sector.data() + 40);
    const std::uint64_t last_usable_lba = read_u64(sector.data() + 48);
    const std::uint64_t entries_lba = read_u64(sector.data() + 72);
    const std::uint32_t entry_count = read_u32(sector.data() + 80);
    const std::uint32_t entry_size = read_u32(sector.data() + 84);
    const std::uint32_t expected_entries_crc = read_u32(sector.data() + 88);

    if (header_size < kGptHeaderMinimumSize || header_size > sector_size ||
        current_lba != 1 || backup_lba >= capacity_bytes / sector_size ||
        first_usable_lba < 2 || first_usable_lba > last_usable_lba ||
        last_usable_lba >= capacity_bytes / sector_size ||
        entries_lba < 2 || entries_lba >= first_usable_lba ||
        entry_count == 0 || entry_count > kMaximumGptEntryCount ||
        entry_size < kGptEntryMinimumSize || entry_size > kMaximumGptEntrySize ||
        (entry_size % 8) != 0) {
        result.status = InspectionStatus::Failed;
        result.diagnostic = "GPT header fields are out of bounds or unsupported.";
        return result;
    }

    std::vector<std::uint8_t> header(sector.begin(), sector.begin() + header_size);
    std::fill(header.begin() + 16, header.begin() + 20, 0);
    if (crc32(header.data(), header.size()) != expected_header_crc) {
        result.status = InspectionStatus::Failed;
        result.diagnostic = "GPT header CRC validation failed.";
        return result;
    }

    std::uint64_t table_bytes_u64 = 0;
    std::uint64_t table_offset = 0;
    if (!checked_mul(entry_count, entry_size, table_bytes_u64) ||
        table_bytes_u64 > kMaximumGptTableBytes ||
        !checked_mul(entries_lba, sector_size, table_offset) ||
        table_offset > capacity_bytes ||
        table_bytes_u64 > capacity_bytes - table_offset) {
        result.status = InspectionStatus::Failed;
        result.diagnostic = "GPT partition-entry array exceeds supported or device bounds.";
        return result;
    }

    const std::uint64_t table_sectors =
        (table_bytes_u64 + sector_size - 1) / sector_size;
    std::uint64_t table_end_lba = 0;
    if (!checked_add(entries_lba, table_sectors, table_end_lba) ||
        table_end_lba > first_usable_lba) {
        result.status = InspectionStatus::Failed;
        result.diagnostic = "GPT partition-entry array overlaps the usable partition region.";
        return result;
    }

    std::vector<std::uint8_t> entries(static_cast<std::size_t>(table_bytes_u64));
    if (!read_exact(read_at, table_offset, entries.data(), entries.size())) {
        result.status = InspectionStatus::Failed;
        result.diagnostic = "Could not read the GPT partition-entry array.";
        return result;
    }
    if (crc32(entries.data(), entries.size()) != expected_entries_crc) {
        result.status = InspectionStatus::Failed;
        result.diagnostic = "GPT partition-entry CRC validation failed.";
        return result;
    }

    for (std::uint32_t i = 0; i < entry_count; ++i) {
        const auto* entry = entries.data() + static_cast<std::size_t>(i) * entry_size;
        if (all_zero(entry, 16)) continue;
        const std::uint64_t first_lba = read_u64(entry + 32);
        const std::uint64_t last_lba = read_u64(entry + 40);
        if (first_lba < first_usable_lba || last_lba > last_usable_lba ||
            first_lba > last_lba) {
            result.status = InspectionStatus::Failed;
            result.diagnostic = "A GPT partition has invalid LBA bounds.";
            result.partitions.clear();
            return result;
        }
        std::uint64_t offset = 0;
        std::uint64_t count = 0;
        std::uint64_t size = 0;
        if (!checked_mul(first_lba, sector_size, offset) ||
            !checked_add(last_lba - first_lba, 1, count) ||
            !checked_mul(count, sector_size, size) ||
            offset > capacity_bytes || size > capacity_bytes - offset) {
            result.status = InspectionStatus::Failed;
            result.diagnostic = "A GPT partition byte range overflows device bounds.";
            result.partitions.clear();
            return result;
        }
        if (all_zero(entry + 16, 16)) {
            result.status = InspectionStatus::Failed;
            result.diagnostic = "A GPT partition has an empty unique partition GUID.";
            result.partitions.clear();
            return result;
        }
        std::string type = "GPT:";
        for (std::size_t j = 0; j < 16; ++j) type += hex_byte(entry[j]);
        result.partitions.push_back({
            i + 1, first_lba, count, offset, size, std::move(type)
        });
        if (result.partitions.size() > 1) {
            const auto& current = result.partitions.back();
            for (std::size_t j = 0; j + 1 < result.partitions.size(); ++j) {
                const auto& previous = result.partitions[j];
                if (current.offset_bytes < previous.offset_bytes + previous.size_bytes &&
                    previous.offset_bytes < current.offset_bytes + current.size_bytes) {
                    result.status = InspectionStatus::Failed;
                    result.diagnostic = "GPT partitions overlap; layout is not trusted.";
                    result.partitions.clear();
                    return result;
                }
            }
        }
    }

    result.status = InspectionStatus::Inspected;
    result.diagnostic = "GPT header and partition-entry CRCs validated; partition ranges are bounded.";
    return result;
}

} // namespace

PartitionScanResult scan_partition_table(
    const crypty::filesystem::ReadAt& read_at,
    std::uint32_t logical_sector_size,
    std::uint64_t capacity_bytes
) {
    PartitionScanResult result;
    if (!read_at || capacity_bytes < kMbrSize ||
        (logical_sector_size != 512 && logical_sector_size != 1024 &&
         logical_sector_size != 2048 && logical_sector_size != 4096) ||
        capacity_bytes < logical_sector_size) {
        result.status = InspectionStatus::Unsupported;
        result.diagnostic = "Reader, capacity, or logical sector size is unsupported.";
        return result;
    }

    std::array<std::uint8_t, kMbrSize> mbr{};
    if (!read_exact(read_at, 0, mbr.data(), mbr.size())) {
        result.status = InspectionStatus::Failed;
        result.diagnostic = "Could not read the master boot record.";
        return result;
    }
    if (mbr[510] != 0x55 || mbr[511] != 0xAA) {
        result.status = InspectionStatus::Unsupported;
        result.diagnostic = "No valid MBR signature; this may be an unpartitioned device or unsupported layout.";
        return result;
    }

    bool protective_gpt = false;
    bool extended_partition = false;
    for (std::uint32_t i = 0; i < 4; ++i) {
        const auto* entry = mbr.data() + kMbrPartitionTableOffset + i * kMbrEntrySize;
        const std::uint8_t type = entry[4];
        const std::uint64_t count = read_u32(entry + 12);
        if (type == 0 || count == 0) continue;
        if (type == 0xEE) protective_gpt = true;
        if (type == 0x05 || type == 0x0F || type == 0x85) {
            extended_partition = true;
            continue;
        }
    }
    if (protective_gpt) {
        return scan_gpt(read_at, logical_sector_size, capacity_bytes);
    }

    result.table_type = PartitionTableType::MBR;
    for (std::uint32_t i = 0; i < 4; ++i) {
        const auto* entry = mbr.data() + kMbrPartitionTableOffset + i * kMbrEntrySize;
        const std::uint8_t type = entry[4];
        const std::uint64_t start = read_u32(entry + 8);
        const std::uint64_t count = read_u32(entry + 12);
        if (type == 0 || count == 0 || type == 0xEE) continue;

        std::uint64_t offset = 0;
        std::uint64_t size = 0;
        if (!checked_mul(start, logical_sector_size, offset) ||
            !checked_mul(count, logical_sector_size, size) ||
            offset > capacity_bytes || size > capacity_bytes - offset) {
            result.status = InspectionStatus::Failed;
            result.diagnostic = "An MBR partition range exceeds device bounds.";
            result.partitions.clear();
            return result;
        }
        result.partitions.push_back({
            i + 1, start, count, offset, size, mbr_type_id(type)
        });
    }
    for (std::size_t i = 0; i < result.partitions.size(); ++i) {
        for (std::size_t j = i + 1; j < result.partitions.size(); ++j) {
            const auto& a = result.partitions[i];
            const auto& b = result.partitions[j];
            if (a.offset_bytes < b.offset_bytes + b.size_bytes &&
                b.offset_bytes < a.offset_bytes + a.size_bytes) {
                result.status = InspectionStatus::Failed;
                result.diagnostic = "MBR partitions overlap; layout is not trusted.";
                result.partitions.clear();
                return result;
            }
        }
    }
    if (extended_partition) {
        result.status = InspectionStatus::Partial;
        result.diagnostic = "MBR primary partitions were read, but extended/logical partitions are not enumerated.";
    } else {
        result.status = InspectionStatus::Inspected;
        result.diagnostic = "MBR partition ranges are bounded; no extended partitions were found.";
    }
    return result;
}

PhysicalDeviceInspection inspect_physical_device(
    const crypty::platform::PhysicalDeviceInfo& device,
    const crypty::filesystem::ReadAt& read_at
) {
    PhysicalDeviceInspection result;
    result.device_path = device.device_path;
    result.stable_id = device.stable_id;
    result.capacity_bytes = device.capacity_bytes;
    result.execution_allowed = false;
    result.blockers.push_back("This inspection is read-only and never authorizes physical-device sanitization.");

    if (device.device_path.empty() || device.capacity_bytes == 0 ||
        device.logical_sector_size == 0 || !read_at) {
        result.status = InspectionStatus::Failed;
        result.diagnostic = "Device path, capacity, logical sector size, or reader is unavailable.";
        result.blockers.push_back("Required device metadata is missing.");
        return result;
    }

    if (device.stable_id.empty())
        result.blockers.push_back("No stable device identifier was discovered.");
    if (!device.os_volume_membership_known)
        result.blockers.push_back("Operating-system volume membership is unknown.");
    else if (device.contains_os_volume)
        result.blockers.push_back("The device contains the operating-system volume.");
    if (!device.read_only_status_known)
        result.blockers.push_back("Device read-only status is unknown.");
    if (!device.metadata_complete)
        result.blockers.push_back("Device metadata is incomplete.");

    const auto scan = scan_partition_table(
        read_at, device.logical_sector_size, device.capacity_bytes);
    result.partition_table = scan.table_type;
    result.status = scan.status;
    result.diagnostic = scan.diagnostic;
    if (scan.status == InspectionStatus::Failed ||
        scan.status == InspectionStatus::Unsupported) {
        result.blockers.push_back("Partition layout could not be fully validated.");
        return result;
    }

    for (const auto& partition : scan.partitions) {
        InspectedPartition inspected;
        inspected.partition = partition;
        const auto partition_reader = [read_at, base = partition.offset_bytes,
                                       length = partition.size_bytes]
            (std::uint64_t relative, std::uint8_t* output, std::size_t size) -> std::size_t {
                if (output == nullptr || relative > length || size > length - relative ||
                    base > (std::numeric_limits<std::uint64_t>::max)() - relative) {
                    return 0;
                }
                return read_at(base + relative, output, size);
            };
        inspected.filesystem = crypty::filesystem::detect_filesystem(partition_reader);
        bool filesystem_valid =
            inspected.filesystem.status == crypty::filesystem::DetectionStatus::Detected;
        if (filesystem_valid) {
            crypty::filesystem::VolumeInfo volume;
            volume.filesystem = inspected.filesystem;
            volume.volume_offset_bytes = partition.offset_bytes;
            filesystem_valid = volume.valid() &&
                volume.filesystem.volume_size_bytes <= partition.size_bytes;
        }
        if (!filesystem_valid) {
            result.blockers.push_back("Filesystem type or geometry is unknown, invalid, or exceeds partition " +
                                       std::to_string(partition.index) + ".");
            if (result.status == InspectionStatus::Inspected) {
                result.status = InspectionStatus::Partial;
            }
        }
        result.partitions.push_back(std::move(inspected));
    }

    if (scan.status == InspectionStatus::Partial) {
        result.blockers.push_back("Partition enumeration is partial.");
    }
    result.blockers.push_back("Mounted-volume and boot-critical-volume checks are not implemented in this stage.");
    if (scan.status == InspectionStatus::Partial) {
        result.status = InspectionStatus::Partial;
    }
    return result;
}

PhysicalDeviceInspection inspect_physical_device(
    const crypty::platform::PhysicalDeviceInfo& device
) {
    const auto reader = [path = device.device_path]
        (std::uint64_t offset, std::uint8_t* output, std::size_t size) -> std::size_t {
            return crypty::platform::read_media(path, offset, output, size);
        };
    return inspect_physical_device(device, reader);
}

} // namespace crypty::sanitization
