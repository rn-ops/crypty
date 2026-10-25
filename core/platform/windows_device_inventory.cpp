#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif

#include <crypty/platform/device_inventory.hpp>

#include <windows.h>
#include <winioctl.h>
#include <ntddstor.h>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <iterator>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace crypty::platform {
namespace {

class Handle final {
public:
    explicit Handle(HANDLE value) noexcept : value_(value) {}
    ~Handle() {
        if (value_ != INVALID_HANDLE_VALUE) CloseHandle(value_);
    }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
    HANDLE get() const noexcept { return value_; }
    bool valid() const noexcept { return value_ != INVALID_HANDLE_VALUE; }
private:
    HANDLE value_;
};

std::wstring physical_path(unsigned index) {
    return L"\\\\.\\PhysicalDrive" + std::to_wstring(index);
}

std::string utf8_from_wide(const std::wstring& value) {
    if (value.empty()) return {};
    const int required = WideCharToMultiByte(
        CP_UTF8, 0, value.data(), static_cast<int>(value.size()),
        nullptr, 0, nullptr, nullptr);
    if (required <= 0) return {};
    std::string output(static_cast<std::size_t>(required), '\0');
    if (WideCharToMultiByte(
            CP_UTF8, 0, value.data(), static_cast<int>(value.size()),
            output.data(), required, nullptr, nullptr) != required) {
        return {};
    }
    return output;
}

std::string descriptor_string(
    const std::vector<unsigned char>& buffer,
    DWORD offset
) {
    if (offset == 0 || offset >= buffer.size()) return {};
    const char* start = reinterpret_cast<const char*>(buffer.data() + offset);
    const std::size_t remaining = buffer.size() - offset;
    std::size_t length = 0;
    while (length < remaining && start[length] != '\0') ++length;
    return std::string(start, length);
}

std::string bus_name(STORAGE_BUS_TYPE bus) {
    switch (bus) {
    case BusTypeAta: return "ATA";
    case BusTypeSata: return "SATA";
    case BusTypeUsb: return "USB";
    case BusTypeNvme: return "NVMe";
    case BusTypeScsi: return "SCSI";
    case BusTypeSas: return "SAS";
    case BusTypeRAID: return "RAID";
    case BusTypeSd: return "SD";
    case BusTypeMmc: return "MMC";
    case BusTypeVirtual: return "Virtual";
    case BusTypeFileBackedVirtual: return "File-backed virtual";
    case BusTypeSpaces: return "Storage Spaces";
    default: return "Unknown (" + std::to_string(static_cast<unsigned>(bus)) + ")";
    }
}

struct SystemVolumeDisks {
    bool known = false;
    std::set<DWORD> numbers;
};

SystemVolumeDisks find_windows_directory_disks() {
    SystemVolumeDisks result;
    wchar_t windows_directory[MAX_PATH + 1]{};
    const UINT length = GetWindowsDirectoryW(
        windows_directory, static_cast<UINT>(std::size(windows_directory)));
    if (length == 0 || length >= std::size(windows_directory)) return result;

    wchar_t volume_root[MAX_PATH + 1]{};
    if (!GetVolumePathNameW(
            windows_directory, volume_root,
            static_cast<DWORD>(std::size(volume_root)))) {
        return result;
    }
    if (volume_root[0] == L'\0' || volume_root[1] != L':') return result;

    std::wstring volume_path = L"\\\\.\\";
    volume_path.push_back(volume_root[0]);
    volume_path.push_back(L':');
    Handle volume(CreateFileW(
        volume_path.c_str(), 0, FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr, OPEN_EXISTING, 0, nullptr));
    if (!volume.valid()) return result;

    // Extent count is variable. This bounded query is read-only; if the
    // returned list doesn't fit, membership remains unknown rather than guessed.
    std::vector<unsigned char> buffer(64 * 1024);
    DWORD bytes_returned = 0;
    if (!DeviceIoControl(
            volume.get(), IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
            nullptr, 0, buffer.data(), static_cast<DWORD>(buffer.size()),
            &bytes_returned, nullptr)) {
        return result;
    }
    if (bytes_returned < sizeof(VOLUME_DISK_EXTENTS)) return result;

    const auto* extents = reinterpret_cast<const VOLUME_DISK_EXTENTS*>(buffer.data());
    const std::size_t required = offsetof(VOLUME_DISK_EXTENTS, Extents) +
        static_cast<std::size_t>(extents->NumberOfDiskExtents) * sizeof(DISK_EXTENT);
    if (required > bytes_returned) return result;

    for (DWORD index = 0; index < extents->NumberOfDiskExtents; ++index) {
        result.numbers.insert(extents->Extents[index].DiskNumber);
    }
    result.known = true;
    return result;
}

bool query_storage_descriptor(
    HANDLE handle,
    PhysicalDeviceInfo& device,
    bool& metadata_complete
) {
    STORAGE_PROPERTY_QUERY query{};
    query.PropertyId = StorageDeviceProperty;
    query.QueryType = PropertyStandardQuery;

    STORAGE_DESCRIPTOR_HEADER header{};
    DWORD returned = 0;
    if (!DeviceIoControl(
            handle, IOCTL_STORAGE_QUERY_PROPERTY,
            &query, sizeof(query), &header, sizeof(header),
            &returned, nullptr) ||
        header.Size < sizeof(STORAGE_DEVICE_DESCRIPTOR) ||
        header.Size > 1024 * 1024) {
        metadata_complete = false;
        return false;
    }

    std::vector<unsigned char> buffer(header.Size);
    if (!DeviceIoControl(
            handle, IOCTL_STORAGE_QUERY_PROPERTY,
            &query, sizeof(query), buffer.data(), header.Size,
            &returned, nullptr) || returned < sizeof(STORAGE_DEVICE_DESCRIPTOR)) {
        metadata_complete = false;
        return false;
    }

    const auto* descriptor = reinterpret_cast<const STORAGE_DEVICE_DESCRIPTOR*>(buffer.data());
    device.vendor = descriptor_string(buffer, descriptor->VendorIdOffset);
    device.model = descriptor_string(buffer, descriptor->ProductIdOffset);
    device.serial_number = descriptor_string(buffer, descriptor->SerialNumberOffset);
    device.bus_type = bus_name(descriptor->BusType);
    device.removable = descriptor->RemovableMedia != FALSE;
    if (!device.serial_number.empty()) {
        device.stable_id = "serial:" + device.serial_number;
    }
    return true;
}

} // namespace

DeviceInventoryResult enumerate_physical_devices() {
    DeviceInventoryResult result;
    result.status = DeviceInventoryStatus::Complete;
    result.diagnostic = "Physical-device inventory uses read-only Windows storage queries.";

    const auto system_disks = find_windows_directory_disks();
    bool partial = false;
    constexpr unsigned kMaximumPhysicalDriveIndex = 128;

    for (unsigned index = 0; index < kMaximumPhysicalDriveIndex; ++index) {
        const auto path = physical_path(index);
        Handle handle(CreateFileW(
            path.c_str(), GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr));

        if (!handle.valid()) {
            const DWORD error = GetLastError();
            if (error == ERROR_FILE_NOT_FOUND ||
                error == ERROR_PATH_NOT_FOUND ||
                error == ERROR_INVALID_NAME ||
                error == ERROR_NO_MEDIA_IN_DRIVE) {
                continue;
            }
            // Access denied and unexpected OS errors make the inventory partial.
            partial = true;
            continue;
        }

        DISK_GEOMETRY_EX geometry{};
        DWORD returned = 0;
        if (!DeviceIoControl(
                handle.get(), IOCTL_DISK_GET_DRIVE_GEOMETRY_EX,
                nullptr, 0, &geometry, sizeof(geometry), &returned, nullptr) ||
            geometry.DiskSize.QuadPart <= 0 ||
            geometry.Geometry.BytesPerSector == 0) {
            partial = true;
            continue;
        }

        PhysicalDeviceInfo device;
        device.device_path = utf8_from_wide(path);
        device.device_number = index;
        device.capacity_bytes = static_cast<std::uint64_t>(geometry.DiskSize.QuadPart);
        device.logical_sector_size = geometry.Geometry.BytesPerSector;
        device.os_volume_membership_known = system_disks.known;
        device.contains_os_volume = system_disks.known && system_disks.numbers.count(index) != 0;
        bool metadata_complete = true;
        query_storage_descriptor(handle.get(), device, metadata_complete);

        STORAGE_DEVICE_NUMBER storage_number{};
        if (DeviceIoControl(
                handle.get(), IOCTL_STORAGE_GET_DEVICE_NUMBER,
                nullptr, 0, &storage_number, sizeof(storage_number),
                &returned, nullptr) && returned >= sizeof(storage_number) &&
            storage_number.DeviceType == FILE_DEVICE_DISK) {
            device.device_number = storage_number.DeviceNumber;
        } else {
            metadata_complete = false;
        }

        DWORD writable_error = ERROR_SUCCESS;
        if (DeviceIoControl(
                handle.get(), IOCTL_DISK_IS_WRITABLE,
                nullptr, 0, nullptr, 0, &returned, nullptr)) {
            device.read_only = false;
            device.read_only_status_known = true;
        } else {
            writable_error = GetLastError();
            if (writable_error == ERROR_WRITE_PROTECT) {
                device.read_only = true;
                device.read_only_status_known = true;
            } else {
                metadata_complete = false;
            }
        }

        STORAGE_ACCESS_ALIGNMENT_DESCRIPTOR alignment{};
        alignment.Version = sizeof(alignment);
        alignment.Size = sizeof(alignment);
        STORAGE_PROPERTY_QUERY alignment_query{};
        alignment_query.PropertyId = StorageAccessAlignmentProperty;
        alignment_query.QueryType = PropertyStandardQuery;
        if (DeviceIoControl(
                handle.get(), IOCTL_STORAGE_QUERY_PROPERTY,
                &alignment_query, sizeof(alignment_query),
                &alignment, sizeof(alignment), &returned, nullptr) &&
            returned >= sizeof(alignment) && alignment.BytesPerPhysicalSector != 0) {
            device.physical_sector_size = alignment.BytesPerPhysicalSector;
        } else {
            metadata_complete = false;
        }

        STORAGE_HOTPLUG_INFO hotplug{};
        if (DeviceIoControl(
                handle.get(), IOCTL_STORAGE_GET_HOTPLUG_INFO,
                nullptr, 0, &hotplug, sizeof(hotplug), &returned, nullptr) &&
            returned >= sizeof(hotplug)) {
            device.hotplug = hotplug.MediaHotplug || hotplug.DeviceHotplug;
            device.removable = device.removable || hotplug.MediaRemovable;
        } else {
            metadata_complete = false;
        }

        std::vector<unsigned char> layout_buffer(64 * 1024);
        if (DeviceIoControl(
                handle.get(), IOCTL_DISK_GET_DRIVE_LAYOUT_EX,
                nullptr, 0, layout_buffer.data(),
                static_cast<DWORD>(layout_buffer.size()), &returned, nullptr) &&
            returned >= offsetof(DRIVE_LAYOUT_INFORMATION_EX, PartitionEntry)) {
            const auto* layout = reinterpret_cast<const DRIVE_LAYOUT_INFORMATION_EX*>(
                layout_buffer.data());
            const std::size_t layout_required =
                offsetof(DRIVE_LAYOUT_INFORMATION_EX, PartitionEntry) +
                static_cast<std::size_t>(layout->PartitionCount) * sizeof(PARTITION_INFORMATION_EX);
            if (layout_required > returned) {
                metadata_complete = false;
            } else switch (layout->PartitionStyle) {
            case PARTITION_STYLE_MBR: device.partition_style = "MBR"; break;
            case PARTITION_STYLE_GPT: device.partition_style = "GPT"; break;
            case PARTITION_STYLE_RAW: device.partition_style = "RAW"; break;
            default: device.partition_style = "Unknown"; break;
            }
        } else {
            metadata_complete = false;
        }

        device.metadata_complete = metadata_complete;
        if (!device.metadata_complete || !system_disks.known ||
            !device.read_only_status_known || device.stable_id.empty()) {
            partial = true;
        }
        result.devices.push_back(std::move(device));
    }

    if (!system_disks.known) partial = true;
    if (partial) {
        result.status = DeviceInventoryStatus::Partial;
        result.diagnostic = "Inventory is partial: one or more devices or metadata fields could not be queried. OS-volume membership does not identify every boot-critical volume; do not treat this inventory as sanitization authorization.";
    }
    return result;
}

} // namespace crypty::platform
#endif // _WIN32
