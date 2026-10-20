
#include "mft_parser.hpp"

#include <algorithm>
#include <limits>


// prepare_mft_record() validates a record and restores its sector trailers before parsing.
// parse_attributes() walks the attribute sequence with bounds checks.
// AttributeView refers to attributes by offset and length, so it doesn't create unnecessary copies of the record.
// Neither function reads the disk or discovers files. That remains the responsibility of the recovery layer.

namespace crypty::recovery::ntfs {
namespace {

std::uint16_t read_u16(
    const std::uint8_t* data
) noexcept {
    return static_cast<std::uint16_t>(data[0]) |
           (static_cast<std::uint16_t>(data[1]) << 8);
}

std::uint32_t read_u32(
    const std::uint8_t* data
) noexcept {
    return static_cast<std::uint32_t>(read_u16(data)) |
           (static_cast<std::uint32_t>(read_u16(data + 2)) << 16);
}

constexpr std::uint32_t ATTRIBUTE_END = 0xFFFFFFFFU;

} // namespace

bool prepare_mft_record(
    std::vector<std::uint8_t>& record,
    std::uint32_t bytes_per_sector,
    std::uint16_t& first_attribute_offset,
    std::uint16_t& flags
) {
    first_attribute_offset = 0;
    flags = 0;

    if (bytes_per_sector == 0 ||
        record.size() < 48 ||
        record.size() % bytes_per_sector != 0) {
        return false;
    }

    if (record[0] != 'F' ||
        record[1] != 'I' ||
        record[2] != 'L' ||
        record[3] != 'E') {
        return false;
    }

    const std::size_t usa_offset = read_u16(record.data() + 4);
    const std::size_t usa_count = read_u16(record.data() + 6);

    const std::size_t sector_count =
        record.size() / bytes_per_sector;

    // One update-sequence number plus one replacement word
    // for every sector in the record.
    if (usa_count != sector_count + 1 ||
        usa_offset > record.size() ||
        usa_count > (record.size() - usa_offset) / 2) {
        return false;
    }

    const std::uint16_t sequence =
        read_u16(record.data() + usa_offset);

    for (std::size_t sector = 1;
         sector <= sector_count;
         ++sector) {
        const std::size_t trailer =
            sector * bytes_per_sector - 2;

        if (read_u16(record.data() + trailer) != sequence) {
            return false;
        }
    }

    // Restore the original final two bytes of each sector.
    for (std::size_t sector = 1;
         sector <= sector_count;
         ++sector) {
        const std::size_t trailer =
            sector * bytes_per_sector - 2;

        const std::size_t replacement =
            usa_offset + sector * 2;

        record[trailer] = record[replacement];
        record[trailer + 1] = record[replacement + 1];
    }

    first_attribute_offset = read_u16(record.data() + 20);
    flags = read_u16(record.data() + 22);

    if (first_attribute_offset < 24 ||
        first_attribute_offset >= record.size()) {
        return false;
    }

    return true;
}

bool parse_attributes(
    const std::vector<std::uint8_t>& record,
    std::uint16_t first_attribute_offset,
    std::vector<AttributeView>& attributes
) {
    attributes.clear();

    if (first_attribute_offset < 24 ||
        first_attribute_offset >= record.size()) {
        return false;
    }

    std::size_t offset = first_attribute_offset;

    while (offset <= record.size() &&
           record.size() - offset >= 8) {
        const auto type = read_u32(record.data() + offset);

        if (type == ATTRIBUTE_END) {
            return true;
        }

        // A valid attribute header must include the common
        // 16-byte header and have a nonzero, bounded length.
        if (record.size() - offset < 16) {
            attributes.clear();
            return false;
        }

        const std::size_t length =
            read_u32(record.data() + offset + 4);

        const bool non_resident = record[offset + 8] != 0;

        const std::size_t minimum_length =
            non_resident ? 64 : 24;

        if (length < minimum_length ||
            length > record.size() - offset) {
            attributes.clear();
            return false;
        }

        attributes.push_back({
            type,
            offset,
            length,
            non_resident
        });

        offset += length;
    }

    // An attribute list without its end marker is incomplete.
    attributes.clear();
    return false;
}

} // namespace crypty::recovery::ntfs
