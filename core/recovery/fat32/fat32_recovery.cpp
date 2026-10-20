#include "fat32_recovery.hpp"


#include <algorithm>
#include <cctype>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

namespace crypty::recovery::fat32 {
using crypty::filesystem::ReadAt;
crypty::FileEntry;
namespace {

std::uint16_t u16(const std::uint8_t* value) {
    return value[0] | (std::uint16_t(value[1]) << 8);
}

std::uint32_t u32(const std::uint8_t* value) {
    return u16(value) | (std::uint32_t(u16(value + 2)) << 16);
}

bool valid_fat32_boot_sector(const std::uint8_t* boot) {
    if (boot[510] != 0x55 || boot[511] != 0xAA) return false;

    const auto bytes_per_sector = u16(boot + 11);
    const auto sectors_per_cluster = boot[13];
    const auto reserved = u16(boot + 14);
    const auto fat_count = boot[16];
    const auto sectors_per_fat = u32(boot + 36);
    const auto root_cluster = u32(boot + 44);

    if (bytes_per_sector < 512 ||
        (bytes_per_sector & (bytes_per_sector - 1)) != 0 ||
        !sectors_per_cluster ||
        !reserved ||
        !fat_count ||
        !sectors_per_fat ||
        root_cluster < 2) {
        return false;
    }

    return std::memcmp(boot + 82, "FAT32", 5) == 0;
}

bool is_fat32_partition_type(std::uint8_t type) {
    return type == 0x0B || type == 0x0C;
}

std::uint64_t find_fat32_partition(const ReadAt& read_at) {
    std::uint8_t sector[512]{};

    if (read_at(0, sector, sizeof(sector)) != sizeof(sector)) {
        return 0;
    }

    /*
     * First support the case where ReadAt already points directly
     * at a FAT32 volume.
     */
    if (valid_fat32_boot_sector(sector)) {
        return 0;
    }

    /*
     * Otherwise interpret sector 0 as an MBR.
     *
     * Partition table:
     *   446 + entry * 16
     *
     * Starting LBA:
     *   entry + 8
     */
    if (sector[510] != 0x55 || sector[511] != 0xAA) {
        return 0;
    }

    for (int index = 0; index < 4; ++index) {
        const std::size_t entry_offset = 446 + index * 16;
        const auto partition_type = sector[entry_offset + 4];

        if (!is_fat32_partition_type(partition_type)) {
            continue;
        }

        const auto starting_lba = u32(sector + entry_offset + 8);

        if (starting_lba == 0) {
            continue;
        }

        const std::uint64_t partition_offset =
            std::uint64_t(starting_lba) * 512;

        std::uint8_t boot[512]{};

        if (read_at(partition_offset, boot, sizeof(boot)) != sizeof(boot)) {
            continue;
        }

        if (valid_fat32_boot_sector(boot)) {
            return partition_offset;
        }
    }

    return 0;
}

std::string extension(const std::uint8_t* entry) {
    std::string value;

    for (int i = 8; i < 11 && entry[i] != ' '; ++i) {
        value += char(entry[i]);
    }

    std::transform(
        value.begin(),
        value.end(),
        value.begin(),
        [](unsigned char c) {
            return char(std::toupper(c));
        }
    );

    return value.empty() ? "BIN" : value;
}

std::string deleted_name(
    const std::uint8_t* entry,
    std::size_t index
) {
    std::string stem = "deleted_" + std::to_string(index);

    for (int i = 1; i < 8 && entry[i] != ' '; ++i) {
        const unsigned char c = entry[i];

        if (std::isalnum(c) || c == '_' || c == '-') {
            stem += char(c);
        }
    }

    return stem + "." + extension(entry);
}

} // namespace

std::vector<FileEntry> Fat32Recovery::find_deleted_entries(
    const ReadAt& read_at
) {
    const std::uint64_t partition_offset =
        find_fat32_partition(read_at);

    std::uint8_t boot[512]{};

    if (read_at(partition_offset, boot, sizeof(boot)) != sizeof(boot)) {
        return {};
    }

    if (!valid_fat32_boot_sector(boot)) {
        return {};
    }

    const auto bytes_per_sector = u16(boot + 11);
    const auto sectors_per_cluster = boot[13];
    const auto reserved = u16(boot + 14);
    const auto fat_count = boot[16];
    const auto sectors_per_fat = u32(boot + 36);
    const auto root_cluster = u32(boot + 44);

    const std::uint64_t first_data_sector =
        std::uint64_t(reserved) +
        std::uint64_t(fat_count) * sectors_per_fat;

    const std::uint64_t data_region_offset =
        partition_offset +
        first_data_sector * bytes_per_sector;

    const std::size_t cluster_size =
        std::size_t(bytes_per_sector) *
        sectors_per_cluster;

    if (cluster_size == 0 || cluster_size > 1024 * 1024) {
        return {};
    }

    /*
     * Read a FAT32 cluster number from the FAT.
     */
    auto next_cluster = [&](std::uint32_t cluster) -> std::uint32_t {
        const std::uint64_t fat_entry =
            partition_offset +
            std::uint64_t(reserved) * bytes_per_sector +
            std::uint64_t(cluster) * 4;

        std::uint8_t value[4]{};

        if (read_at(fat_entry, value, sizeof(value)) != sizeof(value)) {
            return 0x0FFFFFF7;
        }

        return u32(value) & 0x0FFFFFFF;
    };

    /*
     * Convert a cluster number into a physical byte offset.
     */
    auto cluster_offset = [&](std::uint32_t cluster) -> std::uint64_t {
        return data_region_offset +
               std::uint64_t(cluster - 2) * cluster_size;
    };

    /*
     * Read an entire directory cluster.
     */
    auto read_cluster = [&](std::uint32_t cluster,
                            std::vector<std::uint8_t>& buffer) -> bool {
        if (cluster < 2 || cluster >= 0x0FFFFFF7) {
            return false;
        }

        buffer.resize(cluster_size);

        return read_at(
            cluster_offset(cluster),
            buffer.data(),
            buffer.size()
        ) == buffer.size();
    };

    std::vector<FileEntry> found;

    /*
     * Recursively scan a directory.
     *
     * depth prevents pathological/corrupted directory structures
     * from causing unbounded recursion.
     */
    std::function<void(std::uint32_t, int)> scan_directory;

    scan_directory = [&](std::uint32_t start_cluster, int depth) {
        if (start_cluster < 2 || depth > 32) {
            return;
        }

        /*
        * Keep track of visited directory clusters.
        *
        * A damaged filesystem can contain cyclic FAT chains.
        * Without this guard, recovery could loop forever.
        */
        std::vector<std::uint32_t> visited;

        std::uint32_t current = start_cluster;

        while (
            current >= 2 &&
            current < 0x0FFFFFF8
        ) {
            /*
             * Detect FAT cycles.
             */
            if (
                std::find(
                    visited.begin(),
                    visited.end(),
                    current
                ) != visited.end()
            ) {
                return;
            }

            visited.push_back(current);

            std::vector<std::uint8_t> directory;

            if (!read_cluster(current, directory)) {
                return;
            }

            for (
                std::size_t offset = 0;
                offset + 32 <= directory.size();
                offset += 32
            ) {
                const auto* entry =
                    directory.data() + offset;

                /*
                 * 00 means there are no more entries in
                 * this directory.
                 */
                if (entry[0] == 0x00) {
                    break;
                }

                const std::uint8_t attributes = entry[11];

                /*
                 * Long filename entry.
                 *
                 * We deliberately ignore these for now.
                 * Deleted 8.3 entries are still useful for
                 * the first recovery implementation.
                 */
                if (attributes == 0x0F) {
                    continue;
                }

                /*
                 * Deleted entry.
                 */
                if (
                    entry[0] == 0xE5 &&
                    !(attributes & 0x08) &&
                    !(attributes & 0x10)
                ) {
                    const std::uint32_t cluster =
                        (std::uint32_t(u16(entry + 20)) << 16) |
                        u16(entry + 26);

                    const std::uint32_t size =
                        u32(entry + 28);

                    FileEntry candidate;

                    candidate.name =
                        deleted_name(
                            entry,
                            found.size()
                        );

                    candidate.type =
                        extension(entry);

                    candidate.size =
                        size;

                    candidate.recoverable =
                        size;

                    candidate.deleted =
                        true;

                    candidate.cluster_size =
                        static_cast<std::uint32_t>(
                            cluster_size
                        );

                    candidate.data_region_offset =
                        data_region_offset;

                    candidate.source_offset =
                        cluster >= 2
                            ? cluster_offset(cluster)
                            : cluster_offset(current) + offset;

                    /*
                     * Follow the existing FAT chain when
                     * possible. This is useful evidence even
                     * though deleted files may have lost it.
                     */
                    const std::size_t required_clusters =
                        size == 0
                            ? 0
                            : (
                                std::size_t(size) +
                                cluster_size - 1
                              ) / cluster_size;

                    std::uint32_t file_cluster = cluster;

                    std::vector<std::uint32_t> file_visited;

                    for (
                        std::size_t part = 0;
                        file_cluster >= 2 &&
                        file_cluster < 0x0FFFFFF8 &&
                        part < required_clusters;
                        ++part
                    ) {
                        if (
                            std::find(
                                file_visited.begin(),
                                file_visited.end(),
                                file_cluster
                            ) != file_visited.end()
                        ) {
                            break;
                        }

                        file_visited.push_back(file_cluster);
                        candidate.clusters.push_back(file_cluster);

                        const std::uint32_t next =
                            next_cluster(file_cluster);

                        if (
                            next == file_cluster ||
                            next == 0x0FFFFFF7
                        ) {
                            break;
                        }

                        file_cluster = next;
                    }

                    const bool chain_complete =
                        required_clusters == 0 ||
                        candidate.clusters.size() ==
                            required_clusters;

                    candidate.confidence =
                        chain_complete
                            ? 90
                            : (
                                candidate.clusters.empty()
                                    ? 35
                                    : 60
                              );

                    candidate.recovery_method =
                        chain_complete
                            ? "FAT32 cluster chain"
                            : "FAT32 partial chain";

                    found.push_back(
                        std::move(candidate)
                    );

                    continue;
                }

                /*
                 * Directory entry.
                 *
                 * Follow it recursively.
                 *
                 * Ignore "." and "..".
                 */
                if (
                    (attributes & 0x10) &&
                    entry[0] != 0xE5
                ) {
                    const std::uint32_t child_cluster =
                        (std::uint32_t(u16(entry + 20)) << 16) |
                        u16(entry + 26);

                    if (
                        child_cluster >= 2 &&
                        child_cluster != 0x0FFFFFF7
                    ) {
                        scan_directory(
                            child_cluster,
                            depth + 1
                        );
                    }
                }
            }

            const std::uint32_t next =
                next_cluster(current);

            if (
                next == current ||
                next == 0x0FFFFFF7
            ) {
                return;
            }

            current = next;
        }
    };

    /*
     * Start at the FAT32 root directory.
     */
    scan_directory(root_cluster, 0);

    return found;
}
std::uintmax_t Fat32Recovery::recover_to(
    const ReadAt& read_at,
    const FileEntry& entry,
    const std::string& destination,
    bool& complete
) {
    complete = false;

    if (!entry.deleted || destination.empty()) {
        return 0;
    }

    std::ofstream output(
        destination,
        std::ios::binary | std::ios::trunc
    );

    if (!output) {
        return 0;
    }

    // A zero-byte file is recovered by creating an empty file.
    if (entry.size == 0) {
        complete = true;
        return 0;
    }

    if (entry.cluster_size == 0 || entry.clusters.empty()) {
        return 0;
    }

    std::vector<std::uint8_t> buffer(entry.cluster_size);

    std::uintmax_t written = 0;

    for (const auto cluster : entry.clusters) {
        if (written >= entry.size) {
            break;
        }

        const auto wanted =
            static_cast<std::size_t>(
                std::min<std::uintmax_t>(
                    buffer.size(),
                    entry.size - written
                )
            );

        if (wanted == 0) {
            break;
        }

        const auto source =
            entry.data_region_offset +
            std::uint64_t(cluster - 2) *
                entry.cluster_size;

        if (
            read_at(
                source,
                buffer.data(),
                wanted
            ) != wanted
        ) {
            break;
        }

        output.write(
            reinterpret_cast<const char*>(buffer.data()),
            static_cast<std::streamsize>(wanted)
        );

        if (!output) {
            break;
        }

        written += wanted;
    }

    complete = written == entry.size;

    return written;
}
} // namespace crypty::recovery
