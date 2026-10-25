#include <crypty/platform/device_inventory.hpp>

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>
#include <system_error>
#include <vector>

#if defined(__linux__)
#include <sys/stat.h>
#include <sys/sysmacros.h>
#endif

namespace crypty::platform {
namespace {

std::string read_trimmed(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input) return {};
    std::string value;
    std::getline(input, value);
    while (!value.empty() && (value.back() == '\r' || value.back() == '\n' || value.back() == ' ')) {
        value.pop_back();
    }
    return value;
}

bool read_bool(const std::filesystem::path& path, bool& value) {
    const auto text = read_trimmed(path);
    if (text != "0" && text != "1") return false;
    value = text == "1";
    return true;
}

std::string infer_bus(const std::filesystem::path& sys_path, const std::string& name) {
    const auto full = sys_path.generic_string();
    if (name.rfind("nvme", 0) == 0) return "NVMe";
    if (name.rfind("mmcblk", 0) == 0) return "MMC";
    if (full.find("/usb") != std::string::npos) return "USB";
    if (full.find("/ata") != std::string::npos) return "ATA/SATA";
    if (full.find("/virtio") != std::string::npos) return "VirtIO";
    if (full.find("/sas") != std::string::npos) return "SAS";
    return "Unknown";
}

std::string find_stable_id(const std::filesystem::path& device_node) {
    const std::filesystem::path by_id("/dev/disk/by-id");
    std::error_code error;
    if (!std::filesystem::is_directory(by_id, error)) return {};

    std::vector<std::string> matches;
    for (std::filesystem::directory_iterator it(by_id, error), end;
         !error && it != end; it.increment(error)) {
        const auto filename = it->path().filename().string();
        if (filename.find("-part") != std::string::npos) continue;
        std::error_code link_error;
        const auto target = std::filesystem::canonical(it->path(), link_error);
        if (link_error) continue;
        const auto canonical_node = std::filesystem::canonical(device_node, link_error);
        if (!link_error && target == canonical_node) matches.push_back(filename);
    }
    if (matches.empty()) return {};

    // Prefer identifiers less likely to be tied to a bus/port, when available.
    for (const auto& match : matches) {
        if (match.rfind("wwn-", 0) == 0 || match.rfind("nvme-eui.", 0) == 0) return match;
    }
    for (const auto& match : matches) {
        if (match.rfind("ata-", 0) == 0 || match.rfind("nvme-", 0) == 0 ||
            match.rfind("scsi-", 0) == 0) return match;
    }
    return matches.front();
}

} // namespace

DeviceInventoryResult enumerate_physical_devices() {
    DeviceInventoryResult result;
#if defined(__linux__)
    const std::filesystem::path sys_block("/sys/block");
    std::error_code error;
    if (!std::filesystem::is_directory(sys_block, error)) {
        result.status = DeviceInventoryStatus::Failed;
        result.diagnostic = "Linux /sys/block is unavailable; physical-device inventory could not be performed.";
        return result;
    }

    result.status = DeviceInventoryStatus::Complete;
    result.diagnostic = "Physical-device inventory uses read-only Linux sysfs metadata.";
    bool partial = false;

    for (std::filesystem::directory_iterator it(sys_block, error), end;
         !error && it != end; it.increment(error)) {
        const auto name = it->path().filename().string();
        const auto sys_path = it->path();
        // These are virtual devices, not physical storage endpoints.
        if (name.rfind("loop", 0) == 0 || name.rfind("ram", 0) == 0 ||
            name.rfind("zram", 0) == 0 || name.rfind("dm-", 0) == 0 ||
            name.rfind("md", 0) == 0 || name.rfind("fd", 0) == 0) {
            continue;
        }
        std::error_code device_error;
        if (!std::filesystem::exists(sys_path / "device", device_error)) continue;

        const auto sectors_text = read_trimmed(sys_path / "size");
        if (sectors_text.empty()) {
            partial = true;
            continue;
        }
        std::uint64_t sectors = 0;
        try {
            sectors = std::stoull(sectors_text);
        } catch (...) {
            partial = true;
            continue;
        }
        // Linux block-layer `size` is measured in 512-byte sectors.
        if (sectors == 0 || sectors > UINT64_MAX / 512U) {
            partial = true;
            continue;
        }

        PhysicalDeviceInfo device;
        device.device_path = "/dev/" + name;
        device.capacity_bytes = sectors * 512U;
        device.model = read_trimmed(sys_path / "device" / "model");
        device.vendor = read_trimmed(sys_path / "device" / "vendor");
        device.serial_number = read_trimmed(sys_path / "device" / "serial");
        device.bus_type = infer_bus(std::filesystem::canonical(sys_path, device_error), name);
        device.stable_id = find_stable_id(device.device_path);
        device.metadata_complete = true;
        device.os_volume_membership_known = false;

        const auto logical_text = read_trimmed(sys_path / "queue" / "logical_block_size");
        const auto physical_text = read_trimmed(sys_path / "queue" / "physical_block_size");
        try {
            if (!logical_text.empty()) device.logical_sector_size = static_cast<std::uint32_t>(std::stoul(logical_text));
            if (!physical_text.empty()) device.physical_sector_size = static_cast<std::uint32_t>(std::stoul(physical_text));
        } catch (...) {
            device.metadata_complete = false;
        }
        if (device.logical_sector_size == 0) device.metadata_complete = false;
        if (device.physical_sector_size == 0) device.metadata_complete = false;

        bool flag = false;
        if (read_bool(sys_path / "removable", flag)) device.removable = flag;
        else device.metadata_complete = false;
        if (read_bool(sys_path / "ro", flag)) {
            device.read_only = flag;
            device.read_only_status_known = true;
        } else {
            device.metadata_complete = false;
        }
        if (!std::filesystem::exists(device.device_path, device_error)) {
            device.metadata_complete = false;
        }

        if (!device.metadata_complete || device.stable_id.empty() ||
            !device.os_volume_membership_known) {
            partial = true;
        }
        result.devices.push_back(std::move(device));
    }
    if (error) partial = true;
    if (partial) {
        result.status = DeviceInventoryStatus::Partial;
        result.diagnostic = "Inventory is partial: some devices lack metadata or a persistent identifier. System-device membership is not yet established, so no device should be considered safe to sanitize.";
    } else {
        result.diagnostic += " System-device membership is not yet established; this inventory alone is not authorization to sanitize.";
    }
#elif defined(__APPLE__)
    result.status = DeviceInventoryStatus::Unsupported;
    result.diagnostic = "macOS physical-device inventory is not implemented yet; no devices were returned.";
#else
    result.status = DeviceInventoryStatus::Unsupported;
    result.diagnostic = "Physical-device inventory is unsupported on this POSIX platform.";
#endif
    return result;
}

} // namespace crypty::platform
