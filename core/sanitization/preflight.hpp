#pragma once

#include <crypty/filesystem/reader.hpp>
#include <crypty/filesystem/types.hpp>
#include <crypty/platform/device_inventory.hpp>

#include <cstdint>
#include <string>
#include <vector>

namespace crypty::sanitization {

enum class PartitionTableType {
    Unknown,
    MBR,
    GPT
};

enum class InspectionStatus {
    Inspected,
    Partial,
    Unsupported,
    Failed
};

struct PartitionRecord {
    std::uint32_t index = 0;
    std::uint64_t start_lba = 0;
    std::uint64_t sector_count = 0;
    std::uint64_t offset_bytes = 0;
    std::uint64_t size_bytes = 0;
    std::string type_id;
};

struct PartitionScanResult {
    PartitionTableType table_type = PartitionTableType::Unknown;
    InspectionStatus status = InspectionStatus::Failed;
    std::string diagnostic;
    std::vector<PartitionRecord> partitions;
};

struct InspectedPartition {
    PartitionRecord partition;
    crypty::filesystem::FilesystemInfo filesystem;
};

struct PhysicalDeviceInspection {
    InspectionStatus status = InspectionStatus::Failed;
    std::string device_path;
    std::string stable_id;
    std::uint64_t capacity_bytes = 0;
    PartitionTableType partition_table = PartitionTableType::Unknown;
    std::string diagnostic;
    std::vector<std::string> blockers;
    std::vector<InspectedPartition> partitions;

    // This stage is strictly read-only. A successful inspection never
    // authorizes destructive execution.
    bool execution_allowed = false;
};

// Parses an MBR or GPT partition table through a read-only byte reader.
// The reader offsets are absolute offsets from the beginning of the device.
PartitionScanResult scan_partition_table(
    const crypty::filesystem::ReadAt& read_at,
    std::uint32_t logical_sector_size,
    std::uint64_t capacity_bytes
);

// Runs the partition scanner and existing filesystem detector against the
// supplied reader. This overload is deterministic and can be tested without
// opening a real device.
PhysicalDeviceInspection inspect_physical_device(
    const crypty::platform::PhysicalDeviceInfo& device,
    const crypty::filesystem::ReadAt& read_at
);

// Opens the discovered device only through the existing read-only platform
// read_media() API. It does not issue writes or authorize sanitization.
PhysicalDeviceInspection inspect_physical_device(
    const crypty::platform::PhysicalDeviceInfo& device
);

} // namespace crypty::sanitization
