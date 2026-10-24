#include "ntfs_recovery.hpp"
#include "mft_parser.hpp"
#include "data_attribute.hpp"
#include "runlist.hpp"

#include "../../reader.hpp"
#include "../../src/workflow.hpp"

#include <algorithm>
#include <cstddef>  
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <utility>
#include <vector>

namespace crypty::recovery::ntfs {
    
using crypty::filesystem::ReadAt;
using crypty::FileEntry;

namespace {

bool read_exact(
    const ReadAt& read_at,
    std::uint64_t offset,
    std::uint8_t* buffer,
    std::size_t size
) {
    return read_at && read_at(offset, buffer, size) == size;
}

bool add_u64(
    std::uint64_t a,
    std::uint64_t b,
    std::uint64_t& result
) {
    if (b > std::numeric_limits<std::uint64_t>::max() - a) {
        return false;
    }

    result = a + b;
    return true;
}

bool mul_u64(
    std::uint64_t a,
    std::uint64_t b,
    std::uint64_t& result
) {
    if (a != 0 &&
        b > std::numeric_limits<std::uint64_t>::max() / a) {
        return false;
    }

    result = a * b;
    return true;
}

std::uint16_t u16(
    const std::vector<std::uint8_t>& data,
    std::size_t offset
) {
    return static_cast<std::uint16_t>(data[offset]) |
           (static_cast<std::uint16_t>(data[offset + 1]) << 8);
}

std::uint32_t u32(
    const std::vector<std::uint8_t>& data,
    std::size_t offset
) {
    return static_cast<std::uint32_t>(data[offset]) |
           (static_cast<std::uint32_t>(data[offset + 1]) << 8) |
           (static_cast<std::uint32_t>(data[offset + 2]) << 16) |
           (static_cast<std::uint32_t>(data[offset + 3]) << 24);
}

std::uint64_t u64(
    const std::vector<std::uint8_t>& data,
    std::size_t offset
) {
    std::uint64_t value = 0;

    for (unsigned int i = 0; i < 8; ++i) {
        value |= static_cast<std::uint64_t>(data[offset + i])
                 << (i * 8);
    }

    return value;
}

std::string decode_filename(
    const std::vector<std::uint8_t>& record,
    std::uint16_t first_attribute_offset
) {
    std::vector<AttributeView> attributes;

    if (!parse_attributes(record, first_attribute_offset, attributes)) {
        return {};
    }

    // Prefer the Win32 namespace (1), then Win32+DOS (3),
    // then POSIX (0). DOS-only names are a fallback.
    std::string best_name;
    int best_priority = -1;

    for (const auto& attr : attributes) {
        if (attr.type != 0x30 || attr.non_resident ||
            attr.length < 24) {
            continue;
        }

        const std::size_t value_offset =
            attr.offset + u16(record, attr.offset + 20);
        const std::uint32_t value_length =
            u32(record, attr.offset + 16);

        if (value_offset < attr.offset ||
            value_offset > record.size() ||
            value_length > record.size() - value_offset ||
            value_length < 66) {
            continue;
        }

        const std::uint8_t name_length = record[value_offset + 64];
        const std::uint8_t name_space = record[value_offset + 65];

        if (name_length == 0 ||
            name_length > (value_length - 66) / 2) {
            continue;
        }

        int priority = -1;
        switch (name_space) {
            case 1: priority = 3; break; // Win32
            case 3: priority = 2; break; // Win32 + DOS
            case 0: priority = 1; break; // POSIX
            case 2: priority = 0; break; // DOS
            default: continue;
        }

        if (priority <= best_priority) {
            continue;
        }

        std::string name;
        name.reserve(name_length);

        for (std::size_t i = 0; i < name_length; ++i) {
            const std::uint16_t ch =
                u16(record, value_offset + 66 + i * 2);

            // Temporary ASCII-safe conversion. Replace with proper
            // UTF-16-to-UTF-8 conversion before production use.
            if (ch >= 0x20 && ch <= 0x7E) {
                name.push_back(static_cast<char>(ch));
            } else if (ch == '/' || ch == '\\' || ch == 0) {
                name.push_back('_');
            } else {
                name.push_back('?');
            }
        }

        best_name = std::move(name);
        best_priority = priority;
    }

    return best_name;
}

bool read_mft_bytes(
    const ReadAt& read_at,
    const NtfsVolumeInfo& volume,
    const std::vector<NtfsDataRun>& runs,
    std::uint64_t mft_data_size,
    std::uint64_t offset,
    std::uint8_t* output,
    std::size_t length
) {
    if (offset > mft_data_size ||
        length > mft_data_size - offset) {
        return false;
    }

    std::uint64_t run_start = 0;
    std::size_t written = 0;

    for (const auto& run : runs) {
        std::uint64_t run_bytes = 0;

        if (!mul_u64(run.length, volume.cluster_size_bytes, run_bytes)) {
            return false;
        }

        std::uint64_t run_end = 0;
        if (!add_u64(run_start, run_bytes, run_end)) {
            return false;
        }

        if (offset + written >= run_end) {
            run_start = run_end;
            continue;
        }

        const std::uint64_t absolute_position = offset + written;
        const std::uint64_t within_run = absolute_position - run_start;
        const std::uint64_t available = run_bytes - within_run;
        const std::size_t chunk = static_cast<std::size_t>(
            std::min<std::uint64_t>(available, length - written));

        if (chunk == 0) {
            run_start = run_end;
            continue;
        }

        if (run.sparse) {
            std::fill(output + written, output + written + chunk, 0);
        } else {
            std::uint64_t cluster_offset = 0;
            std::uint64_t physical = 0;

            if (!mul_u64(run.lcn, volume.cluster_size_bytes,
                         cluster_offset) ||
                !add_u64(volume.volume_offset_bytes, cluster_offset,
                         physical) ||
                !add_u64(physical, within_run, physical) ||
                !read_exact(read_at, physical, output + written, chunk)) {
                return false;
            }
        }

        written += chunk;

        if (written == length) {
            return true;
        }

        run_start = run_end;
    }

    return false;
}

} // namespace

bool locate_ntfs_volume(
    const ReadAt& read_at,
    NtfsVolumeInfo& result
) {
    result = {};
    std::vector<std::uint8_t> boot(512);
    if (!read_exact(read_at, 0, boot.data(), boot.size()) ||
        std::memcmp(boot.data() + 3, "NTFS    ", 8) != 0) {
        return false;
    }

    const auto bytes_per_sector = u16(boot, 11);
    const auto sectors_per_cluster = boot[13];
    const auto total_sectors = u64(boot, 40);
    const auto mft_lcn = u64(boot, 48);
    const int record_size_code =
        boot[64] < 0x80 ? boot[64] : static_cast<int>(boot[64]) - 256;

    if (bytes_per_sector < 512 || bytes_per_sector > 4096 ||
        (bytes_per_sector & (bytes_per_sector - 1)) != 0 ||
        sectors_per_cluster == 0 ||
        (sectors_per_cluster & (sectors_per_cluster - 1)) != 0 ||
        record_size_code == 0 || total_sectors == 0) {
        return false;
    }

    std::uint64_t cluster_size = 0;
    std::uint64_t volume_size = 0;
    std::uint64_t mft_offset = 0;
    if (!mul_u64(bytes_per_sector, sectors_per_cluster, cluster_size) ||
        !mul_u64(total_sectors, bytes_per_sector, volume_size) ||
        !mul_u64(mft_lcn, cluster_size, mft_offset) ||
        cluster_size > std::numeric_limits<std::uint32_t>::max() ||
        mft_offset >= volume_size) {
        return false;
    }

    std::uint64_t record_size = 0;
    if (record_size_code > 0) {
        if (!mul_u64(
                static_cast<std::uint64_t>(record_size_code),
                cluster_size,
                record_size)) {
            return false;
        }
    } else {
        const auto exponent = static_cast<unsigned int>(-record_size_code);
        if (exponent >= 32) return false;
        record_size = std::uint64_t{1} << exponent;
    }
    if (record_size < bytes_per_sector ||
        record_size > 1024U * 1024U ||
        record_size > volume_size - mft_offset) {
        return false;
    }

    result.volume_offset_bytes = 0;
    result.volume_size_bytes = volume_size;
    result.total_sectors = total_sectors;
    result.mft_lcn = mft_lcn;
    result.mft_offset_bytes = mft_offset;
    result.cluster_size_bytes = cluster_size;
    result.record_size_bytes = static_cast<std::uint32_t>(record_size);
    result.bytes_per_sector = bytes_per_sector;
    result.sectors_per_cluster = sectors_per_cluster;
    return true;
}

std::vector<FileEntry> scan_mft(const ReadAt& read_at) {
    std::vector<FileEntry> entries;

    NtfsVolumeInfo volume;
    if (!locate_ntfs_volume(read_at, volume)) {
        return entries;
    }

    // MFT record zero describes the MFT's own $DATA stream.
    std::vector<std::uint8_t> record(volume.record_size_bytes);

    if (!read_exact(read_at, volume.mft_offset_bytes,
                    record.data(), record.size())) {
        return entries;
    }

    std::uint16_t first_attribute_offset = 0;
    std::uint16_t record_flags = 0;

    if (!prepare_mft_record(record, volume.bytes_per_sector,
                            first_attribute_offset, record_flags)) {
        return entries;
    }

    NtfsDataAttribute mft_data;

    if (!extract_data_attribute(record, first_attribute_offset, mft_data) ||
        mft_data.resident || mft_data.runs.empty() ||
        mft_data.data_size < volume.record_size_bytes) {
        return entries;
    }

    const std::uint64_t record_count =
        mft_data.data_size / volume.record_size_bytes;

    // A safety ceiling prevents corrupt metadata from triggering
    // unbounded scans. Tune this limit for the intended product.
    const std::uint64_t max_records = std::min<std::uint64_t>(
        record_count, 500000);

    for (std::uint64_t index = 0; index < max_records; ++index) {
        std::uint64_t record_offset = 0;

        if (!mul_u64(index, volume.record_size_bytes, record_offset)) {
            break;
        }

        std::vector<std::uint8_t> current(volume.record_size_bytes);

        if (!read_mft_bytes(
                read_at, volume, mft_data.runs, mft_data.data_size,
                record_offset, current.data(), current.size())) {
            continue;
        }

        std::uint16_t attr_offset = 0;
        std::uint16_t flags = 0;

        if (!prepare_mft_record(current, volume.bytes_per_sector,
                                attr_offset, flags)) {
            continue;
        }

        // FILE record flag bit 0 means the record is in use.
        const bool in_use = (flags & 0x0001) != 0;
        const bool is_directory = (flags & 0x0002) != 0;

        std::string name = decode_filename(current, attr_offset);
        if (name.empty()) {
            continue;
        }

        NtfsDataAttribute data;
        if (!extract_data_attribute(current, attr_offset, data)) {
            continue;
        }

        FileEntry entry{};
        entry.name = std::move(name);
        entry.type = is_directory ? "directory" : "file";
        entry.record_number = index;
        entry.deleted = !in_use;
        entry.size = data.data_size;

        entry.recoverable = 0;
        if (data.resident) {
            entry.resident_data = std::move(data.resident_data);
            entry.recoverable = entry.resident_data.size();
        } else if (!data.runs.empty()) {
            // This is only a preliminary estimate.
            // Actual recoverability must be determined by the recovery routine.
            entry.recoverable = data.data_size;
        }
        
        entry.recovery_method = data.resident
            ? "ntfs_resident"
            : "ntfs_non_resident";
        entry.source_offset = volume.mft_offset_bytes + record_offset;
        entry.cluster_size = static_cast<std::uint32_t>(
            std::min<std::uint64_t>(
                volume.cluster_size_bytes,
                std::numeric_limits<std::uint32_t>::max()));

        if (data.resident) {
            entry.resident_data = std::move(data.resident_data);
        } else {
            for (const auto& run : data.runs) {
                // The shared FileEntry::DataRun cannot express sparse
                // runs explicitly. Do not silently misrepresent them.
                if (run.sparse) {
                    entry.recoverable = false;
                    continue;
                }

                entry.data_runs.push_back({run.lcn, run.length});
            }
        }

        entries.push_back(std::move(entry));
    }

    return entries;
}

} // namespace crypty::recovery::ntfs
