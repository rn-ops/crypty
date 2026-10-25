#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace crypty::platform {

enum class DeviceInventoryStatus {
    Complete,
    Partial,
    Unsupported,
    Failed
};

// Read-only inventory metadata. This type does not imply that a device is
// eligible for sanitization or that any sanitization method is supported.
struct PhysicalDeviceInfo {
    // Current OS path used to open the physical device, e.g. \\.\PhysicalDrive0
    // or /dev/nvme0n1. This path may change across boots.
    std::string device_path;

    // Hardware-provided serial or OS-provided persistent identifier, when
    // available. Empty means no trustworthy stable identifier was discovered.
    std::string stable_id;

    std::string model;
    std::string vendor;
    std::string serial_number;
    std::string bus_type;
    std::string partition_style;

    std::uint64_t capacity_bytes = 0;
    std::uint32_t logical_sector_size = 0;
    std::uint32_t physical_sector_size = 0;
    std::uint32_t device_number = 0;

    bool removable = false;
    bool hotplug = false;
    bool read_only = false;
    bool read_only_status_known = false;

    // Identifies the device hosting the OS directory/root volume only. This
    // does not prove that EFI, recovery, pagefile, or other boot-critical
    // volumes are absent from another device.
    bool contains_os_volume = false;
    bool os_volume_membership_known = false;

    // False when some metadata could not be queried for this device.
    bool metadata_complete = false;
};

struct DeviceInventoryResult {
    DeviceInventoryStatus status = DeviceInventoryStatus::Failed;
    std::string diagnostic;
    std::vector<PhysicalDeviceInfo> devices;
};

// Enumerates physical block devices using read-only metadata queries only.
// It does not open a device for writing or perform sanitization.
DeviceInventoryResult enumerate_physical_devices();

} // namespace crypty::platform
