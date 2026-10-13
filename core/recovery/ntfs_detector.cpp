#include "ntfs_detector.hpp"

#include <windows.h>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#include <unordered_map>
#include <cstdio>
#include <fstream>



/*

Responsibility	                            Existing code	                        Destination
Read little-endian integers	                u16, u32, u64	                        NTFS parsing utilities, initially
Identify NTFS boot sector and partition	    ntfs_boot, find_ntfs_partition	        core/filesystem/
Decode NTFS data runs	                    parse_data_runs	                        NTFS-specific parsing
Parse names and timestamps                  utf16_name, parse_standard_information	NTFS metadata parsing
Reconstruct directory paths                 resolve_ntfs_path	                    NTFS recovery/metadata logic
Read MFT and locate file records	        NtfsDetector::find_entries	            NTFS recovery
Filter deleted entries	                    find_deleted_entries	                Recovery orchestration or NTFS recovery
Write recovered file contents	            NtfsDetector::recover_to	            NTFS recovery

namespace crypty::recovery {
namespace {

    u16()
    u32()
    u64()

    ntfs_boot()
    find_ntfs_partition()

    DataRun
    parse_data_runs()

    utf16_name()

    format_filetime()
    NtfsTimestamps
    parse_standard_information()

} // namespace

NtfsDetector::find_entries()
NtfsDetector::find_deleted_entries()
*/



namespace crypty::recovery {
namespace {



// u16, u32, u64
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



// ntfs_boot() & find_ntfs_partition()
bool ntfs_boot(const std::uint8_t* boot) {
    if (boot[510] != 0x55 || boot[511] != 0xAA) {
        return false;
    }

    if (std::memcmp(boot + 3, "NTFS    ", 8) != 0) {
        return false;
    }

    const auto bytes_per_sector = u16(boot + 11);
    const auto sectors_per_cluster = boot[13];

    return bytes_per_sector >= 512 &&
           sectors_per_cluster != 0;
}

std::uint64_t find_ntfs_partition(const ReadAt& read_at) {
    std::uint8_t boot[512]{};

    if (read_at(0, boot, sizeof(boot)) != sizeof(boot)) {
        return 0;
    }

    if (ntfs_boot(boot)) {
        return 0;
    }

    if (boot[510] != 0x55 || boot[511] != 0xAA) {
        return 0;
    }

    for (int i = 0; i < 4; ++i) {
        const std::size_t entry = 446 + i * 16;

        /*
         * 0x07 = IFS / NTFS partition type.
         */
        if (boot[entry + 4] != 0x07) {
            continue;
        }

        const auto lba = u32(boot + entry + 8);

        if (!lba) {
            continue;
        }

        const std::uint64_t offset =
            std::uint64_t(lba) * 512;

        if (read_at(offset, boot, sizeof(boot)) != sizeof(boot)) {
            continue;
        }

        if (ntfs_boot(boot)) {
            return offset;
        }
    }

    return 0;
}



// shared DataRun from workflow.hpp & parse_data_runs()

bool parse_data_runs(
    const std::uint8_t* record,
    std::size_t record_size,
    std::size_t attribute_offset,
    std::size_t attribute_length,
    std::vector<DataRun>& runs
) {
    if (attribute_offset >= record_size) {
        return false;
    }

    if (attribute_length < 64 ||
        attribute_offset + attribute_length > record_size) {
        return false;
    }

    const auto* attribute =
        record + attribute_offset;

    if (attribute[8] != 1) {
        return false;
    }

    const auto mapping_offset =
        u16(attribute + 32);

    if (mapping_offset >= attribute_length) {
        return false;
    }

    const auto* mapping =
        attribute + mapping_offset;

    std::int64_t current_lcn = 0;

    for (std::size_t guard = 0; guard < 100000; ++guard) {
        const std::size_t mapping_offset_now =
            static_cast<std::size_t>(mapping - attribute);

        if (mapping_offset_now >= attribute_length) {
            return false;
        }

        const std::uint8_t header = mapping[0];

        if (header == 0) {
            return true;
        }

        const std::size_t length_bytes =
            header & 0x0F;

        const std::size_t offset_bytes =
            (header >> 4) & 0x0F;

        if (length_bytes == 0 ||
            length_bytes > 8 ||
            offset_bytes > 8) {
            return false;
        }

        const std::size_t run_bytes =
            1 + length_bytes + offset_bytes;

        if (mapping_offset_now + run_bytes > attribute_length) {
            return false;
        }

        std::uint64_t length = 0;

        for (std::size_t i = 0; i < length_bytes; ++i) {
            length |=
                std::uint64_t(mapping[1 + i])
                << (i * 8);
        }

        std::int64_t delta = 0;

        if (offset_bytes != 0) {
            std::uint64_t raw = 0;

            for (std::size_t i = 0; i < offset_bytes; ++i) {
                raw |=
                    std::uint64_t(
                        mapping[1 + length_bytes + i]
                    )
                    << (i * 8);
            }

            if (offset_bytes < 8 &&
                (raw & (
                    std::uint64_t(1) <<
                    (offset_bytes * 8 - 1)
                ))) {
                raw |=
                    ~std::uint64_t(0) <<
                    (offset_bytes * 8);
            }

            delta =
                static_cast<std::int64_t>(raw);

            current_lcn += delta;
        }

        runs.push_back({
            offset_bytes == 0
                ? 0
                : static_cast<std::uint64_t>(current_lcn),
            length
        });

        mapping += run_bytes;
    }

    return false;
}



// utf16_name()
std::string utf16_name(
    const std::uint8_t* value,
    std::size_t characters
) {
    std::string result;

    result.reserve(characters);

    for (std::size_t i = 0; i < characters; ++i) {
        const std::uint16_t c =
            u16(value + i * 2);

        if (c == 0) {
            break;
        }

        /*
         * Keep the detector dependency-free for now.
         * ASCII names are represented directly.
         * Non-ASCII characters receive '?' until we
         * add proper UTF-16 -> UTF-8 conversion.
         */
        if (c < 128) {
            result += static_cast<char>(c);
        } else {
            result += '?';
        }
    }

    return result;
}



// read_u64() & format_filetime() & struct NtfsTimestamps & parse_standard_information
/*
 * NTFS defines:
 * $STANDARD_INFORMATION = 0x10
 * $FILE_NAME            = 0x30
 * $DATA                 = 0x80
 *
 */
std::uint64_t read_u64(
    const std::uint8_t* data
) {
    std::uint64_t value = 0;

    for (int i = 0; i < 8; ++i) {
        value |= static_cast<std::uint64_t>(data[i]) << (i * 8);
    }

    return value;
}
std::string format_filetime(std::uint64_t filetime) {
    if (filetime == 0)
        return "Unknown";

    FILETIME ft{};
    ft.dwLowDateTime = static_cast<DWORD>(filetime & 0xFFFFFFFF);
    ft.dwHighDateTime = static_cast<DWORD>(filetime >> 32);

    SYSTEMTIME utc{};
    if (!FileTimeToSystemTime(&ft, &utc))
        return "Unknown";

    char buffer[64];

    std::snprintf(
        buffer,
        sizeof(buffer),
        "%04u-%02u-%02u %02u:%02u:%02u",
        utc.wYear,
        utc.wMonth,
        utc.wDay,
        utc.wHour,
        utc.wMinute,
        utc.wSecond
    );

    return buffer;
}

struct NtfsTimestamps {
    std::string created;
    std::string modified;
    std::string accessed;
};
NtfsTimestamps parse_standard_information(
    const std::uint8_t* record,
    std::size_t record_size
) {
    NtfsTimestamps result;

    if (record_size < 24)
        return result;

    const std::uint16_t attribute_offset =
        u16(record + 20);

    if (attribute_offset >= record_size)
        return result;

    std::size_t offset = attribute_offset;

    while (offset + 16 <= record_size) {
        const std::uint32_t type =
            u32(record + offset);

        if (type == 0xFFFFFFFF)
            break;

        const std::uint32_t length =
            u32(record + offset + 4);

        if (length < 16 ||
            offset + length > record_size)
            break;

        const std::uint8_t non_resident =
            record[offset + 8];

        if (type == 0x10 && non_resident == 0) {
            std::printf(
                "STANDARD_INFORMATION: attr=%zu length=%u value_offset=%u value_length=%u\n",
                offset,
                length,
                u16(record + offset + 20),
                u32(record + offset + 16)
            );
            const std::uint16_t value_length =
                u16(record + offset + 16);

            const std::uint16_t value_offset =
                u16(record + offset + 20);

            if (value_offset + value_length <= length &&
                value_length >= 32) {

                const auto* value =
                    record + offset + value_offset;
                std::printf(
                    "  timestamps raw: %016llX %016llX %016llX %016llX\n",
                    static_cast<unsigned long long>(u64(value + 0)),
                    static_cast<unsigned long long>(u64(value + 8)),
                    static_cast<unsigned long long>(u64(value + 16)),
                    static_cast<unsigned long long>(u64(value + 24))
                );

                result.created =
                    format_filetime(read_u64(value + 0));

                result.modified =
                    format_filetime(read_u64(value + 8));

                result.accessed =
                    format_filetime(read_u64(value + 24));

                return result;
            }
        }

        offset += length;
    }

    return result;
}



// struct NtfsPathInfo 
struct NtfsPathInfo {
    std::uint64_t record_number = 0;
    std::uint64_t parent_record = 0;
    std::string name;
};
std::string resolve_ntfs_path(
    std::uint64_t record_number,
    const std::unordered_map<
        std::uint64_t,
        std::pair<std::uint64_t, std::string>
    >& path_info
) {
    std::vector<std::string> components;

    std::uint64_t current = record_number;

    for (int depth = 0; depth < 128; ++depth) {
        const auto it = path_info.find(current);

        if (it == path_info.end()) {
            break;
        }

        const auto parent = it->second.first;
        const auto& name = it->second.second;

        if (!name.empty()) {
            components.push_back(name);
        }

        // NTFS root directory is MFT record 5.
        if (current == 5 || parent == current) {
            break;
        }

        current = parent;
    }

    std::string path;

    for (auto it = components.rbegin();
         it != components.rend();
         ++it) {

        path += "\\";
        path += *it;
    }

    if (path.empty()) {
        return "\\";
    }

    return path;
}



} // namespace



// find_entries() & find_deleted_entries()
std::vector<FileEntry> NtfsDetector::find_entries(
    const ReadAt& read_at
) {
    const auto partition_offset =
        find_ntfs_partition(read_at);

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

    if (!ntfs_boot(boot)) {
        return {};
    }

    const auto bytes_per_sector =
        u16(boot + 11);

    const auto sectors_per_cluster =
        boot[13];

    const auto total_sectors =
        u64(boot + 40);

    const auto mft_lcn =
        u64(boot + 48);

    const auto clusters_per_record =
        static_cast<std::int8_t>(boot[64]);

    if (
        bytes_per_sector < 512 ||
        sectors_per_cluster == 0 ||
        total_sectors == 0
    ) {
        return {};
    }

    const std::uint64_t cluster_size =
        std::uint64_t(bytes_per_sector) *
        sectors_per_cluster;

    std::uint64_t record_size = 0;

    if (clusters_per_record > 0) {
        record_size =
            cluster_size *
            static_cast<std::uint8_t>(
                clusters_per_record
            );
    } else {
        const auto exponent =
            static_cast<std::uint8_t>(
                -clusters_per_record
            );

        record_size =
            std::uint64_t(1) << exponent;
    }

    if (
        record_size < 512 ||
        record_size > 1024 * 1024
    ) {
        return {};
    }

    const std::uint64_t mft_offset =
        partition_offset +
        mft_lcn * cluster_size;

    /*
     * Read MFT record 0.
     */
    std::vector<std::uint8_t> record(
        static_cast<std::size_t>(record_size)
    );

    if (
        read_at(
            mft_offset,
            record.data(),
            record.size()
        ) != record.size()
    ) {
        return {};
    }

    if (
        std::memcmp(
            record.data(),
            "FILE",
            4
        ) != 0
    ) {
        return {};
    }

    /*
     * Locate the $DATA attribute of $MFT itself.
     */
    const auto attribute_offset =
        u16(record.data() + 20);

    std::vector<DataRun> mft_runs;

    std::size_t attribute =
        attribute_offset;

    while (
        attribute + 16 <= record.size()
    ) {
        const auto type =
            u32(record.data() + attribute);

        if (type == 0xFFFFFFFF) {
            break;
        }

        const auto length =
            u32(record.data() + attribute + 4);

        if (
            length < 24 ||
            attribute + length > record.size()
        ) {
            break;
        }

        if (
            type == 0x80 &&
            record[attribute + 8] == 1
        ) {
            parse_data_runs(
                record.data(),
                record.size(),
                attribute,
                length,
                mft_runs
            );

            break;
        }

        attribute += length;
    }

    if (mft_runs.empty()) {
        return {};
    }
    std::printf(
        "NTFS: cluster_size=%llu record_size=%llu\n",
        static_cast<unsigned long long>(cluster_size),
        static_cast<unsigned long long>(record_size)
    );

    for (const auto& run : mft_runs) {
        std::printf(
            "NTFS MFT run: LCN=%llu length=%llu clusters\n",
            static_cast<unsigned long long>(run.lcn),
            static_cast<unsigned long long>(run.length)
        );
    }

    std::vector<FileEntry> found;

    std::unordered_map<std::uint64_t, std::pair<std::uint64_t, std::string>> path_info;

    std::uint64_t record_index = 0;
    std::uint64_t scanned_records = 0;

    std::uint64_t file_records = 0;
    std::uint64_t active_records = 0;
    std::uint64_t deleted_records = 0;
    std::uint64_t directory_records = 0;

    constexpr std::uint64_t MAX_MFT_RECORDS = 500000;
    constexpr std::size_t READ_CHUNK = 1024 * 1024;

    for (const auto& run : mft_runs) {
        if (run.length == 0) {
            continue;
        }

        /*
        * A sparse run has no physical data to read.
        */
        if (run.lcn == 0) {
            const auto sparse_records =
                (run.length * cluster_size) / record_size;

            record_index += sparse_records;
            continue;
        }

        const std::uint64_t run_bytes =
            run.length * cluster_size;

        const std::uint64_t records_in_run =
            run_bytes / record_size;

        std::uint64_t processed_in_run = 0;

        while (
            processed_in_run < records_in_run &&
            scanned_records < MAX_MFT_RECORDS
        ) {
            const std::uint64_t remaining_records =
                records_in_run - processed_in_run;

            const std::uint64_t max_records_per_chunk =
                READ_CHUNK / record_size;

            const std::uint64_t records_this_chunk =
                std::min(
                    remaining_records,
                    max_records_per_chunk
                );

            const std::size_t chunk_size =
                static_cast<std::size_t>(
                    records_this_chunk * record_size
                );

            std::vector<std::uint8_t> chunk(chunk_size);

            const std::uint64_t chunk_offset =
                partition_offset +
                run.lcn * cluster_size +
                processed_in_run * record_size;

            if (
                read_at(
                    chunk_offset,
                    chunk.data(),
                    chunk.size()
                ) != chunk.size()
            ) {
                break;
            }

            for (
                std::uint64_t i = 0;
                i < records_this_chunk;
                ++i
            ) {
                if (scanned_records >= MAX_MFT_RECORDS) {
                    break;
                }

                const std::size_t record_offset =
                    static_cast<std::size_t>(
                        i * record_size
                    );

                const auto* current_record =
                    chunk.data() + record_offset;

                const std::uint64_t current_record_index =
                    record_index + i;

                ++scanned_records;

                if (
                    std::memcmp(
                        current_record,
                        "FILE",
                        4
                    ) != 0
                ) {
                    continue;
                }

                if (current_record_index < 20) {
                    std::printf(
                        "MFT[%llu]: FILE record\n",
                        static_cast<unsigned long long>(current_record_index)
                    );
                }

                const auto flags =
                    u16(current_record + 22);

                if (current_record_index < 20) {
                    std::printf(
                        "MFT[%llu]: flags=0x%04X\n",
                        static_cast<unsigned long long>(current_record_index),
                        flags
                    );
                }



                ++file_records;

                const bool active = (flags & 0x0001) != 0;
                const bool deleted = !active;

                if (active) {
                    ++active_records;
                } else {
                    ++deleted_records;
                }

                /*
                * Bit 1 = directory.
                *
                * The File System view currently displays files,
                * not directory MFT records.
                */
                const bool is_directory = (flags & 0x0002) != 0;

                if (is_directory) {
                    ++directory_records;
                }




                const auto first_attribute =
                    u16(current_record + 20);

                if (
                    first_attribute < 24 ||
                    first_attribute >= record_size
                ) {
                    continue;
                }

                std::string name;
                std::uint64_t file_size = 0;
                std::uint64_t first_data_lcn = 0;
                bool has_data = false;
                std::uint64_t parent_record = 0;
                std::vector<DataRun> file_data_runs;
                std::vector<std::uint8_t> resident_data;

                std::size_t current_attribute =
                    first_attribute;

                while (
                    current_attribute + 16 <= record_size
                ) {
                    const auto type =
                        u32(
                            current_record +
                            current_attribute
                        );

                    if (type == 0xFFFFFFFF) {
                        break;
                    }

                    const auto attribute_length =
                        u32(
                            current_record +
                            current_attribute +
                            4
                        );

                    if (
                        attribute_length < 24 ||
                        current_attribute +
                            attribute_length >
                            record_size
                    ) {
                        break;
                    }

                    const auto non_resident =
                        current_record[
                            current_attribute + 8
                        ];

                    /*
                    * $FILE_NAME
                    */
                    if (
                        type == 0x30 &&
                        non_resident == 0
                    ) {
                        const auto value_length =
                            u32(
                                current_record +
                                current_attribute +
                                16
                            );

                        const auto value_offset =
                            u16(
                                current_record +
                                current_attribute +
                                20
                            );

                        if (
                            value_offset < attribute_length &&
                            current_attribute +
                                value_offset +
                                value_length <=
                                record_size &&
                            value_length >= 66
                        ) {
                            const auto* file_name =
                                current_record +
                                current_attribute +
                                value_offset;


                            /*
                            Why the mask?
                            An NTFS file reference is 8 bytes:
                            48-bit MFT record number
                            16-bit sequence number
                            We only need the 48-bit MFT record number for path reconstruction.
                            */
                            parent_record = u64(file_name) & 0x0000FFFFFFFFFFFFULL;



                            const auto name_length =
                                file_name[64];

                            if (name.empty()) {
                                name =
                                    utf16_name(
                                        file_name + 66,
                                        name_length
                                    );
                            }
                        }
                    }

                    /*
                    * $DATA - non resident
                    */
                    if (
                        type == 0x80 &&
                        non_resident == 1
                    ) {
                        const auto name_length =
                            current_record[
                                current_attribute + 9
                            ];

                        // Only recover the unnamed/default $DATA stream.
                        // Named streams such as Zone.Identifier are ADS metadata.
                        if (name_length != 0) {
                            current_attribute += attribute_length;
                            continue;
                        }

                        file_size =
                            u64(
                                current_record +
                                current_attribute +
                                48
                            );

                        std::vector<DataRun> runs;

                        if (
                            parse_data_runs(
                                current_record,
                                record_size,
                                current_attribute,
                                attribute_length,
                                runs
                            ) &&
                            !runs.empty()
                        ) {
                            for (const auto& data_run : runs) {
                                file_data_runs.push_back(data_run);

                                if (data_run.lcn != 0) {
                                    if (!has_data) {
                                        first_data_lcn = data_run.lcn;
                                    }

                                    has_data = true;
                                }
                            }
                        }
                    }

                    /*
                    * $DATA - resident
                    */
                    if (
                        type == 0x80 &&
                        non_resident == 0
                    ) {
                        const auto name_length =
                            current_record[
                                current_attribute + 9
                            ];

                        // Ignore named streams such as Zone.Identifier.
                        if (name_length != 0) {
                            current_attribute += attribute_length;
                            continue;
                        }

                        const auto value_length =
                            u32(
                                current_record +
                                current_attribute +
                                16
                            );

                        const auto value_offset =
                            u16(
                                current_record +
                                current_attribute +
                                20
                            );

                        file_size = value_length;

                        if (
                            value_offset + value_length <= attribute_length &&
                            current_attribute +
                                value_offset +
                                value_length <= record_size
                        ) {
                            resident_data.assign(
                                current_record +
                                    current_attribute +
                                    value_offset,
                                current_record +
                                    current_attribute +
                                    value_offset +
                                    value_length
                            );

                            has_data = true;
                        }
                    }

                    current_attribute +=
                        attribute_length;
                }



                if (name.empty()) {
                    continue;
                }
                if (deleted && !has_data) {
                    continue;
                }
                if (deleted && !has_data) {
                    continue;
                }
                path_info[current_record_index] = {
                    parent_record,
                    name
                };




                FileEntry candidate;

                candidate.data_runs = std::move(file_data_runs);
                candidate.resident_data = std::move(resident_data);

                candidate.name = name;
                candidate.type = "NTFS";
                candidate.size = file_size;
                candidate.recoverable = deleted && has_data ? file_size : 0;
                candidate.deleted = deleted;
                const auto timestamps =
                    parse_standard_information(
                        current_record,
                        record_size
                    );

                candidate.created = timestamps.created;
                candidate.modified = timestamps.modified;
                candidate.accessed = timestamps.accessed;
                
                candidate.record_number = current_record_index;



                if (deleted) {
                    candidate.confidence = has_data ? 85 : 60;

                    candidate.recovery_method =
                        has_data
                            ? "NTFS MFT + data run"
                            : "NTFS MFT metadata";
                } else {
                    candidate.confidence = 100;
                    candidate.recovery_method = "NTFS filesystem";
                }


                        
                candidate.cluster_size =
                    static_cast<std::uint32_t>(
                        cluster_size
                    );

                candidate.data_region_offset =
                    partition_offset;

                if (has_data) {
                    candidate.source_offset =
                        partition_offset +
                        first_data_lcn *
                            cluster_size;
                } else {
                    candidate.source_offset =
                        chunk_offset +
                        record_offset;
                }

                if (!is_directory) {
                    found.push_back(
                        std::move(candidate)
                    );
                }
            } // for each record in chunk

            processed_in_run += records_this_chunk;
        } // while records in run

        record_index += records_in_run;

        if (scanned_records >= MAX_MFT_RECORDS) {
            break;
        }
    } // for each MFT run

    for (auto& entry : found) {
        entry.path = resolve_ntfs_path(
            entry.record_number,
            path_info
        );
    }

    std::printf(
        "NTFS stats: FILE=%llu active=%llu deleted=%llu directories=%llu\n",
        static_cast<unsigned long long>(file_records),
        static_cast<unsigned long long>(active_records),
        static_cast<unsigned long long>(deleted_records),
        static_cast<unsigned long long>(directory_records)
    );

    return found;
} // find_entries

std::vector<FileEntry> NtfsDetector::find_deleted_entries(
    const ReadAt& read_at
) {
    const auto all = find_entries(read_at);

    std::vector<FileEntry> deleted;

    for (const auto& entry : all) {
        if (entry.deleted) {
            deleted.push_back(entry);
        }
    }

    return deleted;
}

std::uintmax_t NtfsDetector::recover_to(
    const ReadAt& read_at,
    const FileEntry& entry,
    const std::string& destination,
    bool& complete
) {
    complete = false;

    if (destination.empty()) {
        return 0;
    }

    std::ofstream output(
        destination,
        std::ios::binary |
        std::ios::trunc
    );

    if (!output) {
        return 0;
    }

    /*
     * A genuinely zero-byte file is successfully recovered
     * by creating an empty destination.
     */
    if (entry.size == 0) {
        complete = true;
        return 0;
    }

    /*
     * Resident NTFS data lives directly inside the MFT record.
     * This is the safest recovery path for small files.
     */
    if (!entry.resident_data.empty()) {
        const auto bytes_to_write =
            std::min<std::uintmax_t>(
                entry.size,
                entry.resident_data.size()
            );

        output.write(
            reinterpret_cast<const char*>(
                entry.resident_data.data()
            ),
            static_cast<std::streamsize>(
                bytes_to_write
            )
        );

        if (!output) {
            return 0;
        }

        complete =
            bytes_to_write == entry.size;

        return bytes_to_write;
    }

    if (
        entry.data_runs.empty() ||
        entry.cluster_size == 0
    ) {
        return 0;
    }

    /*
     * read_media() is intentionally limited to 1 MiB.
     * Never ask it for more than that.
     */
    constexpr std::uint64_t READ_CHUNK =
        1024ULL * 1024ULL;

    std::vector<std::uint8_t> buffer;

    std::uintmax_t recovered = 0;

    std::printf(
    "\n=== NTFS RECOVERY DEBUG ===\n"
    "name: %s\n"
    "size: %llu\n"
    "resident: %zu\n"
    "runs: %zu\n"
    "cluster_size: %u\n"
    "data_region_offset: %llu\n"
    "source_offset: %llu\n",
    entry.name.c_str(),
    static_cast<unsigned long long>(entry.size),
    entry.resident_data.size(),
    entry.data_runs.size(),
    entry.cluster_size,
    static_cast<unsigned long long>(entry.data_region_offset),
    static_cast<unsigned long long>(entry.source_offset)
);

for (const auto& run : entry.data_runs) {
    std::printf(
        "  RUN: LCN=%llu LENGTH=%llu\n",
        static_cast<unsigned long long>(run.lcn),
        static_cast<unsigned long long>(run.length)
    );
}

    for (const auto& run : entry.data_runs) {

        if (recovered >= entry.size) {
            break;
        }

        if (run.length == 0) {
            continue;
        }

        const std::uint64_t run_bytes =
            run.length *
            static_cast<std::uint64_t>(
                entry.cluster_size
            );

        const std::uint64_t remaining =
            static_cast<std::uint64_t>(
                entry.size - recovered
            );

        std::uint64_t run_remaining =
            std::min(
                run_bytes,
                remaining
            );

        std::uint64_t run_offset = 0;

        while (run_remaining > 0) {

            const std::uint64_t chunk =
                std::min(
                    run_remaining,
                    READ_CHUNK
                );

            buffer.resize(
                static_cast<std::size_t>(chunk)
            );

            if (run.lcn == 0) {

                /*
                 * Sparse NTFS run.
                 */
                std::fill(
                    buffer.begin(),
                    buffer.end(),
                    std::uint8_t{0}
                );

            } else {

                const std::uint64_t source_offset =
                    entry.data_region_offset +
                    run.lcn *
                        static_cast<std::uint64_t>(
                            entry.cluster_size
                        ) +
                    run_offset;

                const auto bytes_read =
                    read_at(
                        source_offset,
                        buffer.data(),
                        buffer.size()
                    );

                    if (recovered == 0 && bytes_read >= 16) {
    std::printf("FIRST 16 BYTES: ");

    for (std::size_t i = 0; i < 16; ++i) {
        std::printf(
            "%02X ",
            static_cast<unsigned int>(buffer[i])
        );
    }

    std::printf("\n");
}

                if (
                    bytes_read !=
                    buffer.size()
                ) {
                    /*
                     * We could not read this chunk completely.
                     * Preserve whatever was successfully recovered.
                     */
                    return recovered;
                }
            }

            output.write(
                reinterpret_cast<const char*>(
                    buffer.data()
                ),
                static_cast<std::streamsize>(
                    buffer.size()
                )
            );

            if (!output) {
                return recovered;
            }

            recovered += chunk;
            run_offset += chunk;
            run_remaining -= chunk;
        }
    }

    complete =
        recovered == entry.size;

    return recovered;
}

} // namespace crypty::recoverycs