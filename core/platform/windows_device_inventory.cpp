#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif

#include <crypty/platform/device_inventory.hpp>

#include <windows.h>
#include <winioctl.h>
#include <ntddstor.h>
#include <cwchar>

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

struct ProtectedVolumeDiscovery {
    bool complete = false;
    std::set<DWORD> protected_disk_numbers;
    std::vector<std::pair<DWORD, std::string>> mounted_paths_by_disk;
    std::set<DWORD> crypty_disk_numbers;
};

bool query_volume_disk_numbers(const std::wstring& volume_guid_path,
                               std::set<DWORD>& disk_numbers) {
    std::wstring open_path = volume_guid_path;
    while (!open_path.empty() && (open_path.back() == L'\\' || open_path.back() == L'/')) {
        open_path.pop_back();
    }
    Handle volume(CreateFileW(open_path.c_str(), 0,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr, OPEN_EXISTING, 0, nullptr));
    if (!volume.valid()) return false;

    std::vector<unsigned char> buffer(64 * 1024);
    DWORD returned = 0;
    if (!DeviceIoControl(volume.get(), IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
        nullptr, 0, buffer.data(), static_cast<DWORD>(buffer.size()),
        &returned, nullptr) || returned < sizeof(VOLUME_DISK_EXTENTS)) {
        return false;
    }
    const auto* extents = reinterpret_cast<const VOLUME_DISK_EXTENTS*>(buffer.data());
    const std::size_t required = offsetof(VOLUME_DISK_EXTENTS, Extents) +
        static_cast<std::size_t>(extents->NumberOfDiskExtents) * sizeof(DISK_EXTENT);
    if (required > returned || extents->NumberOfDiskExtents == 0) return false;
    for (DWORD i = 0; i < extents->NumberOfDiskExtents; ++i) {
        disk_numbers.insert(extents->Extents[i].DiskNumber);
    }
    return true;
}

std::wstring get_executable_volume_root() {
    std::vector<wchar_t> path(32768, L'\0');
    const DWORD length = GetModuleFileNameW(nullptr, path.data(),
        static_cast<DWORD>(path.size()));
    if (length == 0 || length >= path.size()) return {};
    std::vector<wchar_t> root(32768, L'\0');
    if (!GetVolumePathNameW(path.data(), root.data(), static_cast<DWORD>(root.size()))) {
        return {};
    }
    return std::wstring(root.data());
}

bool volume_has_mount_path(const std::wstring& volume_name,
                           const std::wstring& target_root) {
    DWORD required = 0;
    GetVolumePathNamesForVolumeNameW(volume_name.c_str(), nullptr, 0, &required);
    if (required == 0) return false;
    std::vector<wchar_t> paths(required + 1, L'\0');
    if (!GetVolumePathNamesForVolumeNameW(volume_name.c_str(), paths.data(),
        static_cast<DWORD>(paths.size()), &required)) return false;
    for (const wchar_t* current = paths.data(); *current != L'\0';
         current += std::wcslen(current) + 1) {
        if (_wcsicmp(current, target_root.c_str()) == 0) return true;
    }
    return false;
}

ProtectedVolumeDiscovery discover_protected_volumes() {
    ProtectedVolumeDiscovery result;
    const UINT windows_length = GetWindowsDirectoryW(nullptr, 0);
    std::vector<wchar_t> windows_path(windows_length ? windows_length + 2 : 0, L'\0');
    bool windows_root_known = windows_length != 0 &&
        GetWindowsDirectoryW(windows_path.data(), static_cast<UINT>(windows_path.size())) != 0;
    std::wstring windows_root;
    if (windows_root_known) {
        std::vector<wchar_t> root(32768, L'\0');
        windows_root_known = GetVolumePathNameW(windows_path.data(), root.data(),
            static_cast<DWORD>(root.size())) != FALSE;
        if (windows_root_known) windows_root = root.data();
    }
    const std::wstring executable_root = get_executable_volume_root();
    bool executable_root_known = !executable_root.empty();

    // FindFirstVolume requires a writable buffer; use a generous bounded buffer.
    std::vector<wchar_t> volume_name(1024, L'\0');
    HANDLE find = FindFirstVolumeW(volume_name.data(), static_cast<DWORD>(volume_name.size()));
    if (find == INVALID_HANDLE_VALUE) return result;

    bool all_queries_succeeded = windows_root_known && executable_root_known;
    do {
        const std::wstring name(volume_name.data());
        std::set<DWORD> disk_numbers;
        if (!query_volume_disk_numbers(name, disk_numbers)) {
            // Some volume types legitimately do not expose disk extents. We cannot
            // claim complete host-storage discovery when that happens.
            all_queries_succeeded = false;
        } else {
            bool windows_volume = !windows_root.empty() && volume_has_mount_path(name, windows_root);
            bool executable_volume = !executable_root.empty() && volume_has_mount_path(name, executable_root);
            DWORD needed = 0;
            GetVolumePathNamesForVolumeNameW(name.c_str(), nullptr, 0, &needed);
            std::vector<wchar_t> mount_paths(needed ? needed + 1 : 1, L'\0');
            bool mounts_known = needed != 0 && GetVolumePathNamesForVolumeNameW(
                name.c_str(), mount_paths.data(), static_cast<DWORD>(mount_paths.size()), &needed);
            if (!mounts_known) all_queries_succeeded = false;
            for (DWORD disk : disk_numbers) {
                if (windows_volume || executable_volume) result.protected_disk_numbers.insert(disk);
                if (executable_volume) result.crypty_disk_numbers.insert(disk);
                if (mounts_known) {
                    for (const wchar_t* current = mount_paths.data(); *current != L'\0';
                         current += std::wcslen(current) + 1) {
                        result.mounted_paths_by_disk.emplace_back(disk, utf8_from_wide(current));
                    }
                }
            }
        }
    } while (FindNextVolumeW(find, volume_name.data(), static_cast<DWORD>(volume_name.size())));
    const DWORD find_error = GetLastError();
    FindVolumeClose(find);
    if (find_error != ERROR_NO_MORE_FILES) all_queries_succeeded = false;
    result.complete = all_queries_succeeded;
    return result;
}

struct BootCriticalDiskDiscovery {
    bool complete = false;
    std::set<DWORD> protected_disk_numbers;
};

struct HostDependencyDiscovery {
    bool complete = false;
    std::set<DWORD> protected_disk_numbers;
    std::vector<std::string> diagnostics;
};

bool query_registry_string_value(HKEY key, const wchar_t* name,
                                 std::vector<std::wstring>& values) {
    DWORD type = 0;
    DWORD bytes = 0;
    LONG status = RegQueryValueExW(key, name, nullptr, &type, nullptr, &bytes);
    if (status == ERROR_FILE_NOT_FOUND) return true; // optional value
    if (status != ERROR_SUCCESS || bytes == 0 || bytes > 1024 * 1024) return false;
    if (type != REG_SZ && type != REG_EXPAND_SZ && type != REG_MULTI_SZ) return false;
    std::vector<wchar_t> buffer(bytes / sizeof(wchar_t) + 2, L'\0');
    status = RegQueryValueExW(key, name, nullptr, &type,
        reinterpret_cast<BYTE*>(buffer.data()), &bytes);
    if (status != ERROR_SUCCESS) return false;

    if (type == REG_MULTI_SZ) {
        for (const wchar_t* current = buffer.data(); *current != L'\0';
             current += std::wcslen(current) + 1) {
            values.emplace_back(current);
        }
    } else {
        std::wstring value(buffer.data());
        if (type == REG_EXPAND_SZ && !value.empty()) {
            DWORD needed = ExpandEnvironmentStringsW(value.c_str(), nullptr, 0);
            if (needed == 0 || needed > 32768) return false;
            std::vector<wchar_t> expanded(needed, L'\0');
            if (ExpandEnvironmentStringsW(value.c_str(), expanded.data(), needed) == 0) return false;
            value = expanded.data();
        }
        if (!value.empty()) values.push_back(std::move(value));
    }
    return true;
}

bool disk_numbers_for_file_path(std::wstring path, std::set<DWORD>& disks) {
    if (path.empty()) return true;
    // Windows stores page-file and dump paths in several equivalent forms.
    if (path.rfind(L"\\??\\", 0) == 0) path.erase(0, 4);
    if (path.rfind(L"\\SystemRoot\\", 0) == 0) {
        wchar_t windows_directory[MAX_PATH + 1]{};
        UINT length = GetWindowsDirectoryW(windows_directory,
            static_cast<UINT>(std::size(windows_directory)));
        if (length == 0 || length >= std::size(windows_directory)) return false;
        path = std::wstring(windows_directory) + path.substr(11);
    }
    // Pagefile configuration can append size arguments after the path.
    const std::size_t comma = path.find(L',');
    if (comma != std::wstring::npos) path.resize(comma);
    const std::size_t sys_suffix = path.find(L".sys");
    if (sys_suffix != std::wstring::npos) path.resize(sys_suffix + 4);

    // Native volume paths (especially SYSTEM\Setup\SystemPartition) often
    // refer to an unmounted volume such as \Device\HarddiskVolume1. Such a
    // volume has no drive-letter mapping, so try opening the volume device
    // directly and query its extents before attempting DOS-drive translation.
    if (path.rfind(L"\\Device\\HarddiskVolume", 0) == 0) {
        const std::wstring native_name = path.substr(std::wstring(L"\\Device\\").size());
        if (native_name.find_first_of(L"\\/") == std::wstring::npos) {
            const std::wstring volume_device = L"\\.\\" + native_name;
            Handle native_volume(CreateFileW(volume_device.c_str(), 0,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                nullptr, OPEN_EXISTING, 0, nullptr));
            if (native_volume.valid()) {
                std::vector<unsigned char> extent_buffer(64 * 1024);
                DWORD extent_bytes = 0;
                if (DeviceIoControl(native_volume.get(), IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
                        nullptr, 0, extent_buffer.data(),
                        static_cast<DWORD>(extent_buffer.size()), &extent_bytes, nullptr) &&
                    extent_bytes >= sizeof(VOLUME_DISK_EXTENTS)) {
                    const auto* extents = reinterpret_cast<const VOLUME_DISK_EXTENTS*>(extent_buffer.data());
                    const std::size_t extent_required = offsetof(VOLUME_DISK_EXTENTS, Extents) +
                        static_cast<std::size_t>(extents->NumberOfDiskExtents) * sizeof(DISK_EXTENT);
                    if (extents->NumberOfDiskExtents != 0 && extent_required <= extent_bytes) {
                        for (DWORD i = 0; i < extents->NumberOfDiskExtents; ++i)
                            disks.insert(extents->Extents[i].DiskNumber);
                        return true;
                    }
                }
            }
        }
    }

    // ExistingPageFiles is commonly reported as a native device path rather
    // than a drive-letter path. Translate it through DOS-device mappings.
    if (path.rfind(L"\\Device\\", 0) == 0) {
        bool translated = false;
        for (wchar_t drive = L'A'; drive <= L'Z'; ++drive) {
            wchar_t drive_name[] = {drive, L':', L'\0'};
            std::vector<wchar_t> target(32768, L'\0');
            const DWORD count = QueryDosDeviceW(drive_name, target.data(),
                static_cast<DWORD>(target.size()));
            if (count == 0) continue;
            const std::wstring device_target(target.data());
            if (path.size() >= device_target.size() &&
                _wcsnicmp(path.c_str(), device_target.c_str(), device_target.size()) == 0 &&
                (path.size() == device_target.size() || path[device_target.size()] == L'\\')) {
                const std::wstring suffix = path.substr(device_target.size());
                path = std::wstring(1, drive) + L":" +
                    (suffix.empty() ? std::wstring(L"\\") : suffix);
                translated = true;
                break;
            }
        }
        if (!translated) return false;
    }
    while (!path.empty() && (path.front() == L' ' || path.front() == L'\t')) path.erase(path.begin());
    while (!path.empty() && (path.back() == L' ' || path.back() == L'\t')) path.pop_back();
    if (path.empty()) return true;

    std::vector<wchar_t> root(32768, L'\0');
    if (!GetVolumePathNameW(path.c_str(), root.data(), static_cast<DWORD>(root.size()))) {
        // A registry path can refer to a non-mounted device. We cannot prove its
        // disk membership, so the caller must keep discovery incomplete.
        return false;
    }
    std::wstring volume_path = L"\\\\.\\";
    if (root[0] && root[1] == L':') {
        volume_path.push_back(root[0]);
        volume_path.push_back(L':');
    } else {
        // Volume-GUID mount roots need the trailing slash removed for CreateFile.
        volume_path = root.data();
        while (!volume_path.empty() && volume_path.back() == L'\\') volume_path.pop_back();
    }
    Handle volume(CreateFileW(volume_path.c_str(), 0,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr, OPEN_EXISTING, 0, nullptr));
    if (!volume.valid()) return false;
    std::vector<unsigned char> buffer(64 * 1024);
    DWORD returned = 0;
    if (!DeviceIoControl(volume.get(), IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
            nullptr, 0, buffer.data(), static_cast<DWORD>(buffer.size()), &returned, nullptr) ||
        returned < sizeof(VOLUME_DISK_EXTENTS)) return false;
    const auto* extents = reinterpret_cast<const VOLUME_DISK_EXTENTS*>(buffer.data());
    const std::size_t required = offsetof(VOLUME_DISK_EXTENTS, Extents) +
        static_cast<std::size_t>(extents->NumberOfDiskExtents) * sizeof(DISK_EXTENT);
    if (required > returned || extents->NumberOfDiskExtents == 0) return false;
    for (DWORD i = 0; i < extents->NumberOfDiskExtents; ++i)
        disks.insert(extents->Extents[i].DiskNumber);
    return true;
}

HostDependencyDiscovery discover_host_storage_dependencies() {
    HostDependencyDiscovery result;
    bool complete = true;
    HKEY memory_key = nullptr;
    LONG status = RegOpenKeyExW(HKEY_LOCAL_MACHINE,
        L"SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Memory Management",
        0, KEY_QUERY_VALUE, &memory_key);
    if (status != ERROR_SUCCESS) {
        result.diagnostics.emplace_back("Could not read Windows paging-file configuration.");
        return result;
    }
    std::vector<std::wstring> pagefiles;
    if (!query_registry_string_value(memory_key, L"PagingFiles", pagefiles) ||
        !query_registry_string_value(memory_key, L"ExistingPageFiles", pagefiles)) complete = false;
    RegCloseKey(memory_key);

    HKEY crash_key = nullptr;
    status = RegOpenKeyExW(HKEY_LOCAL_MACHINE,
        L"SYSTEM\\CurrentControlSet\\Control\\CrashControl",
        0, KEY_QUERY_VALUE, &crash_key);
    if (status != ERROR_SUCCESS) {
        complete = false;
        result.diagnostics.emplace_back("Could not read Windows crash-dump configuration.");
    } else {
        if (!query_registry_string_value(crash_key, L"DumpFile", pagefiles) ||
            !query_registry_string_value(crash_key, L"DedicatedDumpFile", pagefiles) ||
            !query_registry_string_value(crash_key, L"MinidumpDir", pagefiles)) complete = false;
        RegCloseKey(crash_key);
    }

    for (const auto& configured_path : pagefiles) {
        if (!disk_numbers_for_file_path(configured_path, result.protected_disk_numbers)) {
            complete = false;
            result.diagnostics.emplace_back("Could not map a configured paging or crash-dump path to a physical disk.");
        }
    }
    // hiberfil.sys resides on the Windows directory volume, which is already
    // mapped by find_windows_directory_disks(). Hibernation configuration itself
    // does not move this file to another volume.
    result.complete = complete;
    return result;
}

// Conservative partition-level detection for EFI System and Windows Recovery
// partitions. Active MBR flags are not treated as proof that Windows boots from
// a disk; current host dependencies are mapped separately.
BootCriticalDiskDiscovery discover_boot_critical_disks() {
    BootCriticalDiskDiscovery result;
    bool all_queries_succeeded = true;
    constexpr unsigned kMaximumPhysicalDriveIndex = 128;
    const GUID kEfiSystemPartition = {
        0xC12A7328, 0xF81F, 0x11D2, {0xBA, 0x4B, 0x00, 0xA0, 0xC9, 0x3E, 0xC9, 0x3B}
    };
    const GUID kMicrosoftRecoveryPartition = {
        0xDE94BBA4, 0x06D1, 0x4D40, {0xA1, 0x6A, 0xBF, 0xD5, 0x01, 0x79, 0xD6, 0xAC}
    };

    // Windows records the active system partition as a native device path.
    // Resolve it explicitly so a separate BIOS/MBR boot disk is still protected
    // without treating every removable disk's active flag as host-critical.
    HKEY setup_key = nullptr;
    if (RegOpenKeyExW(HKEY_LOCAL_MACHINE, L"SYSTEM\Setup", 0,
            KEY_QUERY_VALUE, &setup_key) != ERROR_SUCCESS) {
        all_queries_succeeded = false;
    } else {
        std::vector<std::wstring> system_partition_values;
        if (!query_registry_string_value(setup_key, L"SystemPartition", system_partition_values) ||
            system_partition_values.empty()) {
            all_queries_succeeded = false;
        } else {
            for (const auto& system_partition : system_partition_values) {
                if (!disk_numbers_for_file_path(system_partition, result.protected_disk_numbers))
                    all_queries_succeeded = false;
            }
        }
        RegCloseKey(setup_key);
    }

    for (unsigned index = 0; index < kMaximumPhysicalDriveIndex; ++index) {
        const std::wstring path = physical_path(index);
        Handle disk(CreateFileW(path.c_str(), 0,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            nullptr, OPEN_EXISTING, 0, nullptr));
        if (!disk.valid()) {
            const DWORD error = GetLastError();
            if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND ||
                error == ERROR_INVALID_NAME || error == ERROR_NO_MEDIA_IN_DRIVE) {
                continue;
            }
            all_queries_succeeded = false;
            continue;
        }

        std::vector<unsigned char> layout_buffer(64 * 1024);
        DWORD returned = 0;
        if (!DeviceIoControl(disk.get(), IOCTL_DISK_GET_DRIVE_LAYOUT_EX,
                nullptr, 0, layout_buffer.data(),
                static_cast<DWORD>(layout_buffer.size()), &returned, nullptr) ||
            returned < offsetof(DRIVE_LAYOUT_INFORMATION_EX, PartitionEntry)) {
            all_queries_succeeded = false;
            continue;
        }

        const auto* layout = reinterpret_cast<const DRIVE_LAYOUT_INFORMATION_EX*>(layout_buffer.data());
        const std::size_t required = offsetof(DRIVE_LAYOUT_INFORMATION_EX, PartitionEntry) +
            static_cast<std::size_t>(layout->PartitionCount) * sizeof(PARTITION_INFORMATION_EX);
        if (required > returned) {
            all_queries_succeeded = false;
            continue;
        }

        bool critical = false;
        for (DWORD partition_index = 0; partition_index < layout->PartitionCount; ++partition_index) {
            const PARTITION_INFORMATION_EX& partition = layout->PartitionEntry[partition_index];
            if (partition.PartitionStyle == PARTITION_STYLE_GPT &&
                (IsEqualGUID(partition.Gpt.PartitionType, kEfiSystemPartition) ||
                 IsEqualGUID(partition.Gpt.PartitionType, kMicrosoftRecoveryPartition))) {
                critical = true;
                break;
            }
            // An active MBR flag only means a partition is marked bootable; it
            // does not prove that the running Windows installation boots from it.
            // Actual Windows and configured host-storage dependencies are mapped
            // separately below, avoiding false positives on ordinary USB media.
        }
        if (critical) result.protected_disk_numbers.insert(index);
    }

    result.complete = all_queries_succeeded;
    return result;
}

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
    const auto protected_volumes = discover_protected_volumes();
    const auto boot_critical_disks = discover_boot_critical_disks();
    const auto host_dependencies = discover_host_storage_dependencies();
    const bool protection_discovery_complete = system_disks.known &&
        protected_volumes.complete && boot_critical_disks.complete && host_dependencies.complete;
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
        device.protection_discovery_complete = protection_discovery_complete;
        for (const auto& entry : protected_volumes.mounted_paths_by_disk) {
            if (entry.first == index && !entry.second.empty()) {
                device.mounted_volume_paths.push_back(entry.second);
            }
        }
        if (device.contains_os_volume ||
            protected_volumes.protected_disk_numbers.count(index) != 0 ||
            boot_critical_disks.protected_disk_numbers.count(index) != 0 ||
            host_dependencies.protected_disk_numbers.count(index) != 0) {
            device.protection_status = DeviceProtectionStatus::Protected;
            if (device.contains_os_volume) {
                device.protection_reasons.emplace_back("Hosts the Windows directory volume.");
            }
            if (protected_volumes.crypty_disk_numbers.count(index) != 0) {
                device.protection_reasons.emplace_back("Hosts the volume containing the running Crypty executable.");
            }
            if (boot_critical_disks.protected_disk_numbers.count(index) != 0) {
                device.protection_reasons.emplace_back("Contains an EFI System or Windows Recovery partition.");
            }
            if (host_dependencies.protected_disk_numbers.count(index) != 0) {
                device.protection_reasons.emplace_back("Hosts a configured Windows paging or crash-dump file.");
            }
            if (!protection_discovery_complete) {
                device.protection_reasons.emplace_back("Additional host-storage dependencies could not all be checked.");
            }
        } else if (device.protection_discovery_complete) {
            device.protection_status = DeviceProtectionStatus::Eligible;
        } else {
            device.protection_status = DeviceProtectionStatus::Unknown;
            device.protection_reasons.emplace_back("Host-storage dependency discovery is incomplete; physical sanitization remains blocked.");
        }
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

    if (!protection_discovery_complete) partial = true;
    if (partial) {
        result.status = DeviceInventoryStatus::Partial;
        result.diagnostic = "Inventory is partial: host-storage dependency discovery or device metadata could not be completed. Physical-device sanitization remains blocked until the inventory reports complete protection discovery.";
        for (const auto& diagnostic : host_dependencies.diagnostics) {
            result.diagnostic += " Detail: " + diagnostic;
        }
        if (!system_disks.known)
            result.diagnostic += " Detail: Could not map the Windows directory volume to physical disk extents.";
        if (!protected_volumes.complete)
            result.diagnostic += " Detail: One or more mounted-volume dependency queries failed.";
        if (!boot_critical_disks.complete)
            result.diagnostic += " Detail: Boot-critical partition/system-partition discovery was incomplete.";
    }
    return result;
}

} // namespace crypty::platform
#endif // _WIN32
