#include "../device_access.hpp"

#include <sys/statvfs.h>

#if defined(__APPLE__)
#include <sys/mount.h>
#else
#include <fstream>
#include <sstream>
#endif

#include <algorithm>
#include <cerrno>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>

#include <fcntl.h>
#include <unistd.h>

namespace crypty::platform {
namespace {

std::string unescape_mount_field(const std::string& field) {
    std::string result;
    result.reserve(field.size());
    for (std::size_t index = 0; index < field.size(); ++index) {
        if (field[index] == '\\' && index + 3 < field.size() &&
            field[index + 1] >= '0' && field[index + 1] <= '7' &&
            field[index + 2] >= '0' && field[index + 2] <= '7' &&
            field[index + 3] >= '0' && field[index + 3] <= '7') {
            const auto value =
                (field[index + 1] - '0') * 64 +
                (field[index + 2] - '0') * 8 +
                (field[index + 3] - '0');
            result.push_back(static_cast<char>(value));
            index += 3;
        } else {
            result.push_back(field[index]);
        }
    }
    return result;
}

bool device_source(const std::string& source) {
#if defined(__APPLE__)
    return source.rfind("/dev/disk", 0) == 0;
#else
    return source.rfind("/dev/", 0) == 0;
#endif
}

std::uint64_t volume_capacity(const std::string& mount_point) {
    struct statvfs info {};
    if (statvfs(mount_point.c_str(), &info) != 0) return 0;
    const auto block_size = static_cast<std::uint64_t>(info.f_frsize);
    const auto block_count = static_cast<std::uint64_t>(info.f_blocks);
    if (block_size != 0 &&
        block_count > (std::numeric_limits<std::uint64_t>::max)() / block_size) {
        return 0;
    }
    return block_size * block_count;
}

} // namespace

std::vector<StorageDevice> enumerate_devices() {
    std::vector<StorageDevice> result;
#if defined(__APPLE__)
    struct statfs* mounts = nullptr;
    const int count = getmntinfo(&mounts, MNT_NOWAIT);
    for (int index = 0; index < count; ++index) {
        const std::string source = mounts[index].f_mntfromname;
        if (!device_source(source)) continue;

        const std::string mount_point = mounts[index].f_mntonname;
        result.push_back({
            source,
            mount_point,
            mounts[index].f_fstypename,
            "Mounted volume",
            "macOS volume",
            volume_capacity(mount_point),
            "CONNECTED",
        });
    }
#else
    std::ifstream mounts("/proc/self/mounts");
    std::string line;
    while (std::getline(mounts, line)) {
        std::istringstream fields(line);
        std::string source;
        std::string mount_point;
        std::string filesystem;
        if (!(fields >> source >> mount_point >> filesystem)) continue;

        source = unescape_mount_field(source);
        mount_point = unescape_mount_field(mount_point);
        if (!device_source(source)) continue;

        result.push_back({
            source,
            mount_point,
            filesystem,
            "Mounted volume",
            "Linux volume",
            volume_capacity(mount_point),
            "CONNECTED",
        });
    }
#endif
    return result;
}

std::size_t read_media(
    const std::string& path,
    std::uint64_t offset,
    std::uint8_t* output,
    std::size_t capacity
) {
    if (path.empty() || output == nullptr || capacity == 0 ||
        offset > static_cast<std::uint64_t>(
                     (std::numeric_limits<off_t>::max)()) ||
        capacity > static_cast<std::size_t>(
                       (std::numeric_limits<ssize_t>::max)()) ||
        capacity > static_cast<std::uint64_t>(
                       (std::numeric_limits<off_t>::max)()) - offset) {
        return 0;
    }

    const int descriptor = open(path.c_str(), O_RDONLY | O_CLOEXEC);
    if (descriptor < 0) return 0;

    std::size_t total_read = 0;
    while (total_read < capacity) {
        const auto bytes_read = pread(
            descriptor,
            output + total_read,
            capacity - total_read,
            static_cast<off_t>(offset + total_read)
        );
        if (bytes_read < 0 && errno == EINTR) continue;
        if (bytes_read <= 0) {
            close(descriptor);
            return 0;
        }
        total_read += static_cast<std::size_t>(bytes_read);
    }
    close(descriptor);
    return total_read;
}

} // namespace crypty::platform
