#include "exfat_detector.hpp"

#include <cstdint>
#include <cstring>
#include <functional>
#include <string>
#include <vector>
#include <algorithm>

namespace crypty::recovery {
namespace {

std::uint16_t u16(const std::uint8_t* p) {
    return std::uint16_t(p[0]) |
           (std::uint16_t(p[1]) << 8);
}

std::uint32_t u32(const std::uint8_t* p) {
    return std::uint32_t(u16(p)) |
           (std::uint32_t(u16(p + 2)) << 16);
}

std::uint64_t u64(const std::uint8_t* p) {
    return std::uint64_t(u32(p)) |
           (std::uint64_t(u32(p + 4)) << 32);
}

bool exfat_boot(const std::uint8_t* boot) {
    if (
        boot[510] != 0x55 ||
        boot[511] != 0xAA
    ) {
        return false;
    }

    return std::memcmp(
        boot + 3,
        "EXFAT   ",
        8
    ) == 0;
}

std::uint64_t find_exfat_partition(
    const ReadAt& read_at
) {
    std::uint8_t boot[512]{};

    if (
        read_at(0, boot, sizeof(boot)) !=
        sizeof(boot)
    ) {
        return 0;
    }

    if (exfat_boot(boot)) {
        return 0;
    }

    if (
        boot[510] != 0x55 ||
        boot[511] != 0xAA
    ) {
        return 0;
    }

    for (int i = 0; i < 4; ++i) {
        const std::size_t entry =
            446 + i * 16;

        /*
         * 0x07 is commonly used for IFS/exFAT
         * partitions in MBR partition tables.
         */
        if (boot[entry + 4] != 0x07) {
            continue;
        }

        const auto lba =
            u32(boot + entry + 8);

        if (!lba) {
            continue;
        }

        const std::uint64_t offset =
            std::uint64_t(lba) * 512;

        if (
            read_at(
                offset,
                boot,
                sizeof(boot)
            ) != sizeof(boot)
        ) {
            continue;
        }

        if (exfat_boot(boot)) {
            return offset;
        }
    }

    return 0;
}

std::string utf16_ascii(
    const std::vector<std::uint8_t>& entries,
    std::size_t offset,
    std::size_t character_count
) {
    std::string result;

    for (
        std::size_t i = 0;
        i < character_count;
        ++i
    ) {
        const std::size_t position =
            offset + 2 + i * 2;

        if (position + 2 > entries.size()) {
            break;
        }

        const auto c =
            u16(entries.data() + position);

        if (c == 0) {
            break;
        }

        if (c < 128) {
            result += static_cast<char>(c);
        } else {
            result += '?';
        }
    }

    return result;
}

} // namespace

std::vector<FileEntry>
ExFatDetector::find_deleted_entries(
    const ReadAt& read_at
) {
    const std::uint64_t partition_offset =
        find_exfat_partition(read_at);

    std::uint8_t boot[512]{};

    if (
        read_at(
            partition_offset,
            boot,
            sizeof(boot)
        ) != sizeof(boot)
    ) {
        return {};
    }

    if (!exfat_boot(boot)) {
        return {};
    }

    const auto bytes_per_sector_shift =
        boot[108];

    const auto sectors_per_cluster_shift =
        boot[109];

    if (
        bytes_per_sector_shift < 9 ||
        bytes_per_sector_shift > 12
    ) {
        return {};
    }

    if (
        sectors_per_cluster_shift > 25
    ) {
        return {};
    }

    const std::uint64_t bytes_per_sector =
        std::uint64_t(1) <<
        bytes_per_sector_shift;

    const std::uint64_t sectors_per_cluster =
        std::uint64_t(1) <<
        sectors_per_cluster_shift;

    const std::uint64_t cluster_size =
        bytes_per_sector *
        sectors_per_cluster;

    const std::uint32_t fat_offset =
        u32(boot + 80);

    const std::uint32_t fat_length =
        u32(boot + 84);

    const std::uint32_t cluster_heap_offset =
        u32(boot + 88);

    const std::uint32_t cluster_count =
        u32(boot + 92);

    const std::uint32_t root_cluster =
        u32(boot + 96);

    const std::uint64_t cluster_heap =
        partition_offset +
        std::uint64_t(cluster_heap_offset) *
            bytes_per_sector;

    if (
        cluster_count == 0 ||
        root_cluster < 2
    ) {
        return {};
    }

    auto cluster_offset =
        [&](std::uint32_t cluster) {
            return cluster_heap +
                std::uint64_t(cluster - 2) *
                    cluster_size;
        };

    auto next_cluster =
        [&](std::uint32_t cluster)
            -> std::uint32_t {
        const std::uint64_t fat_entry =
            partition_offset +
            std::uint64_t(fat_offset) *
                bytes_per_sector +
            std::uint64_t(cluster) * 4;

        std::uint8_t value[4]{};

        if (
            read_at(
                fat_entry,
                value,
                sizeof(value)
            ) != sizeof(value)
        ) {
            return 0xFFFFFFFF;
        }

        return u32(value);
    };

    /*
     * exFAT can mark a file's data as contiguous
     * (NoFatChain). For directory traversal we use
     * the FAT chain for now.
     */
    auto read_directory =
        [&](std::uint32_t start_cluster,
            std::vector<std::uint8_t>& output) {
        output.clear();

        std::uint32_t current =
            start_cluster;

        std::vector<std::uint32_t> visited;

        for (
            std::size_t guard = 0;
            guard < cluster_count;
            ++guard
        ) {
            if (
                current < 2 ||
                current >=
                    cluster_count + 2
            ) {
                break;
            }

            if (
                std::find(
                    visited.begin(),
                    visited.end(),
                    current
                ) != visited.end()
            ) {
                break;
            }

            visited.push_back(current);

            std::vector<std::uint8_t> cluster(
                static_cast<std::size_t>(
                    cluster_size
                )
            );

            if (
                read_at(
                    cluster_offset(current),
                    cluster.data(),
                    cluster.size()
                ) != cluster.size()
            ) {
                break;
            }

            output.insert(
                output.end(),
                cluster.begin(),
                cluster.end()
            );

            const auto next =
                next_cluster(current);

            if (
                next >= 0xFFFFFFF8
            ) {
                break;
            }

            if (next == current) {
                break;
            }

            current = next;
        }

        return !output.empty();
    };

    std::vector<std::uint8_t> directory;

    if (
        !read_directory(
            root_cluster,
            directory
        )
    ) {
        return {};
    }

    std::vector<FileEntry> found;

    for (
        std::size_t offset = 0;
        offset + 32 <= directory.size();
    ) {
        const auto type =
            directory[offset];

        if (type == 0x00) {
            break;
        }

        /*
         * Deleted file primary entry.
         *
         * 0x05 = file type code with InUse bit cleared.
         */
        if (type == 0x05) {
            const std::size_t secondary_count =
                directory[offset + 1];

            const std::size_t set_size =
                (secondary_count + 1) * 32;

            if (
                offset + set_size >
                directory.size()
            ) {
                break;
            }

            const auto* stream =
                directory.data() +
                offset + 32;

            std::uint64_t file_size = 0;
            std::uint32_t first_cluster = 0;
            std::uint8_t name_length = 0;

            std::string name;

            if (
                secondary_count >= 1 &&
                stream[0] == 0x40
            ) {
                name_length = stream[3];

                file_size =
                    u64(stream + 24);

                first_cluster =
                    u32(stream + 20);

                /*
                 * File Name entries immediately follow
                 * the Stream Extension entry.
                 */
                std::size_t remaining =
                    name_length;

                for (
                    std::size_t i = 1;
                    i < secondary_count &&
                    remaining > 0;
                    ++i
                ) {
                    const auto* name_entry =
                        directory.data() +
                        offset +
                        i * 32;

                    if (
                        name_entry[0] != 0x41
                    ) {
                        continue;
                    }

                    const std::size_t count =
                        remaining > 15
                            ? 15
                            : remaining;

                    for (
                        std::size_t c = 0;
                        c < count;
                        ++c
                    ) {
                        const auto character =
                            u16(
                                name_entry +
                                2 + c * 2
                            );

                        if (
                            character == 0
                        ) {
                            break;
                        }

                        if (
                            character < 128
                        ) {
                            name +=
                                static_cast<char>(
                                    character
                                );
                        } else {
                            name += '?';
                        }
                    }

                    remaining -= count;
                }
            }

            if (name.empty()) {
                name =
                    "deleted_exfat_" +
                    std::to_string(
                        found.size()
                    );
            }

            FileEntry candidate;

            candidate.name = name;
            candidate.type = "exFAT";
            candidate.size = file_size;
            candidate.recoverable = file_size;
            candidate.deleted = true;

            candidate.cluster_size =
                static_cast<std::uint32_t>(
                    cluster_size
                );

            candidate.data_region_offset =
                cluster_heap;

            candidate.source_offset =
                first_cluster >= 2
                    ? cluster_offset(
                        first_cluster
                    )
                    : partition_offset +
                      offset;

            candidate.confidence =
                first_cluster >= 2
                    ? 85
                    : 55;

            candidate.recovery_method =
                first_cluster >= 2
                    ? "exFAT directory metadata"
                    : "exFAT deleted entry";

            found.push_back(
                std::move(candidate)
            );

            offset += set_size;
            continue;
        }

        offset += 32;
    }

    return found;
}

} // namespace crypty::recovery