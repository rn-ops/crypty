#include "../device_access.hpp"

#include <windows.h>

#include <algorithm>
#include <cctype>
#include <cstring>
#include <fstream>
#include <limits>
#include <vector>

namespace crypty::platform {
namespace {

std::string raw_volume_path(const std::string& path) {
    if (path.size() == 3 &&
        std::isalpha(static_cast<unsigned char>(path[0])) &&
        path[1] == ':' &&
        (path[2] == '\\' || path[2] == '/')) {
        return "\\\\.\\" + path.substr(0, 2);
    }
    return path;
}

std::size_t read_file(
    const std::string& path,
    std::uint64_t offset,
    std::uint8_t* output,
    std::size_t capacity
) {
    if (offset > static_cast<std::uint64_t>(
                     (std::numeric_limits<std::streamoff>::max)()) ||
        capacity > static_cast<std::size_t>(
                       (std::numeric_limits<std::streamsize>::max)())) {
        return 0;
    }

    std::ifstream input(path, std::ios::binary);
    if (!input) return 0;

    input.seekg(static_cast<std::streamoff>(offset));
    if (!input) return 0;

    input.read(
        reinterpret_cast<char*>(output),
        static_cast<std::streamsize>(capacity)
    );
    return input.gcount() == static_cast<std::streamsize>(capacity)
        ? capacity
        : 0;
}

} // namespace

std::vector<StorageDevice> enumerate_devices() {
    std::vector<StorageDevice> result;
    const DWORD drives = GetLogicalDrives();
    for (int index = 0; index < 26; ++index) {
        if ((drives & (1u << index)) == 0) continue;

        const std::string root =
            std::string(1, static_cast<char>('A' + index)) + ":\\";
        char volume_name[MAX_PATH]{};
        char filesystem_name[MAX_PATH]{};
        DWORD serial = 0;
        DWORD max_component = 0;
        DWORD flags = 0;
        if (!GetVolumeInformationA(
                root.c_str(),
                volume_name,
                MAX_PATH,
                &serial,
                &max_component,
                &flags,
                filesystem_name,
                MAX_PATH)) {
            continue;
        }

        ULARGE_INTEGER available{};
        ULARGE_INTEGER total{};
        ULARGE_INTEGER free_bytes{};
        if (!GetDiskFreeSpaceExA(
                root.c_str(), &available, &total, &free_bytes)) {
            continue;
        }

        const UINT drive_type = GetDriveTypeA(root.c_str());
        const bool removable = drive_type == DRIVE_REMOVABLE;
        result.push_back({
            root,
            volume_name[0] == '\0' ? root : volume_name,
            filesystem_name,
            removable ? "Removable" : "Local volume",
            removable ? "USB / removable" : "Windows volume",
            total.QuadPart,
            "CONNECTED",
        });
    }
    return result;
}

std::size_t read_media(
    const std::string& path,
    std::uint64_t offset,
    std::uint8_t* output,
    std::size_t capacity
) {
    if (output == nullptr || capacity == 0) return 0;

    const auto media = raw_volume_path(path);
    if (media == path) {
        return read_file(path, offset, output, capacity);
    }

    constexpr std::uint64_t sector_size = 512;
    const auto aligned_offset = offset - (offset % sector_size);
    const auto offset_delta = offset - aligned_offset;
    if (capacity > 1024U * 1024U ||
        offset_delta > (std::numeric_limits<std::uint64_t>::max)() - capacity) {
        return 0;
    }
    const auto requested = offset_delta + capacity;
    if (requested >
        (std::numeric_limits<std::uint64_t>::max)() - (sector_size - 1)) {
        return 0;
    }
    const auto aligned_size =
        ((requested + sector_size - 1) / sector_size) * sector_size;
    if (aligned_size > 1024U * 1024U ||
        aligned_size > (std::numeric_limits<DWORD>::max)() ||
        aligned_offset > static_cast<std::uint64_t>(
                             (std::numeric_limits<LONGLONG>::max)())) {
        return 0;
    }

    HANDLE handle = CreateFileA(
        media.c_str(),
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        nullptr
    );
    if (handle == INVALID_HANDLE_VALUE) return 0;

    std::vector<std::uint8_t> buffer(static_cast<std::size_t>(aligned_size));
    LARGE_INTEGER position{};
    position.QuadPart = static_cast<LONGLONG>(aligned_offset);
    DWORD bytes_read = 0;
    const bool success =
        SetFilePointerEx(handle, position, nullptr, FILE_BEGIN) &&
        ReadFile(
            handle,
            buffer.data(),
            static_cast<DWORD>(aligned_size),
            &bytes_read,
            nullptr
        ) &&
        bytes_read >= requested;
    CloseHandle(handle);

    if (!success) return 0;
    std::memcpy(output, buffer.data() + offset_delta, capacity);
    return capacity;
}

} // namespace crypty::platform
