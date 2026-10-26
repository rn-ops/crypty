#include "device_native_executor.hpp"

#include <crypty/platform/device_inventory.hpp>
#include <algorithm>
#include <array>
#include <string>
#include <vector>
#include <cwchar>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <winioctl.h>
#endif

namespace crypty::sanitization {
namespace {
SanitizationResult failed(const SanitizationPlan& p, const char* code,
                          const std::string& message) {
    SanitizationResult r;
    r.plan_id = p.plan_id; r.device_id = p.device_id;
    r.method_used = Method::Overwrite; r.required_level = p.required_level;
    r.target_capacity_bytes = p.target_capacity_bytes;
    r.execution_status = ExecutionStatus::Failed;
    r.validation_status = ValidationStatus::NotPerformed;
    r.error_code = code; r.error_message = message; r.successful = false;
    return r;
}

#ifdef _WIN32
// Holds locks on every mounted volume backed by the target physical disk.
// The handles stay alive for the entire raw overwrite so the filesystem cannot
// continue serving cached writes against sectors being erased.
class LockedTargetVolumes final {
public:
    LockedTargetVolumes() = default;
    ~LockedTargetVolumes() {
        for (HANDLE handle : handles_) {
            DWORD ignored = 0;
            DeviceIoControl(handle, FSCTL_UNLOCK_VOLUME, nullptr, 0,
                            nullptr, 0, &ignored, nullptr);
            CloseHandle(handle);
        }
    }
    LockedTargetVolumes(const LockedTargetVolumes&) = delete;
    LockedTargetVolumes& operator=(const LockedTargetVolumes&) = delete;

    bool acquire(DWORD target_disk, std::string& error) {
        std::vector<wchar_t> volume_name(1024, L'\0');
        HANDLE find = FindFirstVolumeW(volume_name.data(),
                                       static_cast<DWORD>(volume_name.size()));
        if (find == INVALID_HANDLE_VALUE) {
            error = "FindFirstVolumeW failed: " + std::to_string(GetLastError());
            return false;
        }
        bool ok = true;
        do {
            const std::wstring name(volume_name.data());
            DWORD chars_needed = 0;
            SetLastError(ERROR_SUCCESS);
            GetVolumePathNamesForVolumeNameW(name.c_str(), nullptr, 0, &chars_needed);
            const DWORD paths_error = GetLastError();
            if (chars_needed == 0 && paths_error != ERROR_MORE_DATA && paths_error != ERROR_SUCCESS) {
                // No mount paths are expected for hidden/system partitions; they
                // cannot be actively used as mounted filesystems through a path.
                continue;
            }
            if (chars_needed == 0) continue;
            std::vector<wchar_t> paths(static_cast<std::size_t>(chars_needed) + 1, L'\0');
            if (!GetVolumePathNamesForVolumeNameW(name.c_str(), paths.data(),
                    static_cast<DWORD>(paths.size()), &chars_needed)) {
                error = "Could not enumerate mount paths for a volume: " + std::to_string(GetLastError());
                ok = false; break;
            }

            std::wstring open_name = name;
            while (!open_name.empty() && (open_name.back() == L'\\' || open_name.back() == L'/'))
                open_name.pop_back();
            HANDLE volume = CreateFileW(open_name.c_str(), GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                OPEN_EXISTING, 0, nullptr);
            if (volume == INVALID_HANDLE_VALUE) {
                error = "Could not open a mounted volume for locking: " + std::to_string(GetLastError());
                ok = false; break;
            }

            std::vector<unsigned char> extents_buffer(64 * 1024);
            DWORD returned = 0;
            if (!DeviceIoControl(volume, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
                    nullptr, 0, extents_buffer.data(),
                    static_cast<DWORD>(extents_buffer.size()), &returned, nullptr) ||
                returned < sizeof(VOLUME_DISK_EXTENTS)) {
                const DWORD e = GetLastError();
                CloseHandle(volume);
                error = "Could not map a mounted volume to physical disks: " + std::to_string(e);
                ok = false; break;
            }
            const auto* extents = reinterpret_cast<const VOLUME_DISK_EXTENTS*>(extents_buffer.data());
            const std::size_t required = offsetof(VOLUME_DISK_EXTENTS, Extents) +
                static_cast<std::size_t>(extents->NumberOfDiskExtents) * sizeof(DISK_EXTENT);
            if (required > returned || extents->NumberOfDiskExtents == 0) {
                CloseHandle(volume);
                error = "Mounted volume returned an invalid physical-disk extent list.";
                ok = false; break;
            }
            bool belongs_to_target = false;
            for (DWORD i = 0; i < extents->NumberOfDiskExtents; ++i)
                if (extents->Extents[i].DiskNumber == target_disk) belongs_to_target = true;
            if (!belongs_to_target) {
                CloseHandle(volume);
                continue;
            }

            DWORD ignored = 0;
            if (!DeviceIoControl(volume, FSCTL_LOCK_VOLUME, nullptr, 0,
                                 nullptr, 0, &ignored, nullptr)) {
                const DWORD e = GetLastError();
                CloseHandle(volume);
                error = "Could not lock a mounted target volume; close applications using it and retry. Win32 error: " + std::to_string(e);
                ok = false; break;
            }
            if (!DeviceIoControl(volume, FSCTL_DISMOUNT_VOLUME, nullptr, 0,
                                 nullptr, 0, &ignored, nullptr)) {
                const DWORD e = GetLastError();
                DeviceIoControl(volume, FSCTL_UNLOCK_VOLUME, nullptr, 0,
                                nullptr, 0, &ignored, nullptr);
                CloseHandle(volume);
                error = "Could not dismount a mounted target volume. Win32 error: " + std::to_string(e);
                ok = false; break;
            }
            handles_.push_back(volume);
        } while (FindNextVolumeW(find, volume_name.data(),
                                 static_cast<DWORD>(volume_name.size())));
        const DWORD enumeration_error = GetLastError();
        FindVolumeClose(find);
        if (ok && enumeration_error != ERROR_NO_MORE_FILES) {
            error = "Volume enumeration ended unexpectedly: " + std::to_string(enumeration_error);
            ok = false;
        }
        return ok;
    }
private:
    std::vector<HANDLE> handles_;
};
#endif
}

SanitizationResult execute_physical_device_overwrite(
    const SanitizationPlan& plan, const ExecutionAuthorization& authorization) {
    if (!authorization.confirmed)
        return failed(plan, "AUTHORIZATION_REQUIRED", "Explicit confirmation is required.");
    if (authorization.confirmed_target_path != plan.target_path ||
        authorization.confirmed_target_capacity_bytes != plan.target_capacity_bytes)
        return failed(plan, "AUTHORIZATION_TARGET_MISMATCH", "Confirmed target path/capacity does not match the plan.");
    if (authorization.confirmation_phrase != "SANITIZE THIS PHYSICAL DEVICE")
        return failed(plan, "CONFIRMATION_PHRASE_INVALID", "Enter the exact physical-device confirmation phrase.");
    if (plan.status != PlanStatus::Ready || plan.target_kind != TargetKind::PhysicalDevice ||
        plan.target_path.empty() || plan.device_id.empty() || plan.target_capacity_bytes == 0 ||
        plan.required_level != AssuranceLevel::Clear || plan.steps.size() != 1 ||
        plan.steps.front().method != Method::Overwrite)
        return failed(plan, "INVALID_PLAN", "Physical overwrite plan is invalid or requests unsupported assurance.");

#ifndef _WIN32
    return failed(plan, "UNSUPPORTED_PLATFORM", "Physical-device overwrite is implemented only for Windows in this build.");
#else
    // Fail closed unless inventory can prove host-storage dependencies were checked.
    const auto inventory = crypty::platform::enumerate_physical_devices();
    if (inventory.status != crypty::platform::DeviceInventoryStatus::Complete)
        return failed(plan, "INVENTORY_INCOMPLETE", "Physical-device inventory is not complete; no write was attempted.");
    const auto found = std::find_if(inventory.devices.begin(), inventory.devices.end(),
        [&](const auto& d) { return d.device_path == plan.target_path && d.stable_id == plan.device_id; });
    if (found == inventory.devices.end())
        return failed(plan, "DEVICE_IDENTITY_MISMATCH", "Device path and stable identity no longer match inventory.");
    if (!found->metadata_complete || !found->protection_discovery_complete ||
        found->protection_status != crypty::platform::DeviceProtectionStatus::Eligible ||
        !found->os_volume_membership_known || found->contains_os_volume ||
        !found->read_only_status_known || found->read_only || found->capacity_bytes != plan.target_capacity_bytes ||
        found->stable_id.empty() || found->logical_sector_size == 0)
        return failed(plan, "DEVICE_NOT_ELIGIBLE", "Device is protected, read-only, mismatched, or host-storage checks are incomplete.");
    if (plan.target_capacity_bytes % found->logical_sector_size != 0)
        return failed(plan, "CAPACITY_ALIGNMENT", "Device capacity is not aligned to its logical sector size.");

    HANDLE raw = CreateFileA(plan.target_path.c_str(), GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING,
        FILE_FLAG_WRITE_THROUGH, nullptr);
    if (raw == INVALID_HANDLE_VALUE)
        return failed(plan, "OPEN_FAILED", "Could not open physical device for read/write. Win32 error: " + std::to_string(GetLastError()));
    struct Closer { HANDLE h; ~Closer(){ if (h != INVALID_HANDLE_VALUE) CloseHandle(h); } } closer{raw};

    STORAGE_DEVICE_NUMBER number{}; DWORD returned = 0;
    if (!DeviceIoControl(raw, IOCTL_STORAGE_GET_DEVICE_NUMBER, nullptr, 0, &number, sizeof(number), &returned, nullptr) ||
        number.DeviceNumber != found->device_number)
        return failed(plan, "DEVICE_NUMBER_MISMATCH", "Opened device number differs from freshly enumerated inventory.");
    GET_LENGTH_INFORMATION length{};
    if (!DeviceIoControl(raw, IOCTL_DISK_GET_LENGTH_INFO, nullptr, 0, &length, sizeof(length), &returned, nullptr) ||
        length.Length.QuadPart < 0 || static_cast<std::uint64_t>(length.Length.QuadPart) != plan.target_capacity_bytes)
        return failed(plan, "CAPACITY_MISMATCH", "Opened device capacity differs from the confirmed plan.");

    // Lock and dismount mounted filesystems on the target disk before issuing
    // raw writes. If any mounted target volume cannot be handled, abort before
    // writing a single byte.
    LockedTargetVolumes locked_volumes;
    std::string volume_lock_error;
    if (!locked_volumes.acquire(found->device_number, volume_lock_error))
        return failed(plan, "VOLUME_LOCK_FAILED", volume_lock_error);

    const std::size_t sector = found->logical_sector_size;
    const std::size_t chunk = ((1024u * 1024u) / sector) * sector;
    if (chunk == 0) return failed(plan, "SECTOR_SIZE_INVALID", "Unsupported logical sector size.");
    std::vector<unsigned char> zeros(chunk, 0), readback(chunk, 0);
    std::uint64_t offset = 0;
    while (offset < plan.target_capacity_bytes) {
        const DWORD count = static_cast<DWORD>((std::min<std::uint64_t>)(chunk, plan.target_capacity_bytes - offset));
        LARGE_INTEGER pos{}; pos.QuadPart = static_cast<LONGLONG>(offset);
        DWORD transferred = 0;
        if (!SetFilePointerEx(raw, pos, nullptr, FILE_BEGIN) || !WriteFile(raw, zeros.data(), count, &transferred, nullptr) || transferred != count) {
            auto r = failed(plan, "WRITE_FAILED", "Physical-device write failed; device may be partially overwritten.");
            r.bytes_processed = offset; r.warnings.push_back("Partial physical-device overwrite may have occurred."); return r;
        }
        offset += transferred;
    }
    if (!FlushFileBuffers(raw)) {
        auto r = failed(plan, "FLUSH_FAILED", "Flush failed after physical-device writes.");
        r.bytes_processed = offset; return r;
    }
    for (offset = 0; offset < plan.target_capacity_bytes;) {
        const DWORD count = static_cast<DWORD>((std::min<std::uint64_t>)(chunk, plan.target_capacity_bytes - offset));
        LARGE_INTEGER pos{}; pos.QuadPart = static_cast<LONGLONG>(offset);
        DWORD transferred = 0;
        if (!SetFilePointerEx(raw, pos, nullptr, FILE_BEGIN) || !ReadFile(raw, readback.data(), count, &transferred, nullptr) || transferred != count) {
            auto r = failed(plan, "READBACK_FAILED", "Could not fully read back the physical device."); r.bytes_processed = plan.target_capacity_bytes; return r;
        }
        if (std::any_of(readback.begin(), readback.begin() + transferred, [](unsigned char b){ return b != 0; })) {
            auto r = failed(plan, "VERIFICATION_FAILED", "Read-back found non-zero data."); r.bytes_processed = plan.target_capacity_bytes; r.validation_status = ValidationStatus::Failed; return r;
        }
        offset += transferred;
    }
    SanitizationResult r; r.plan_id = plan.plan_id; r.device_id = plan.device_id;
    r.method_used = Method::Overwrite; r.required_level = plan.required_level;
    r.target_capacity_bytes = plan.target_capacity_bytes; r.bytes_processed = plan.target_capacity_bytes;
    r.execution_status = ExecutionStatus::Completed; r.validation_status = ValidationStatus::Passed;
    r.successful = true;
    r.warnings.push_back("Full-device zero overwrite and read-back passed. This is not proof of SSD controller remapping or purge-level sanitization.");
    return r;
#endif
}
} // namespace crypty::sanitization
