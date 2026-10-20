
#include "data_attribute.hpp"

#include "mft_parser.hpp"

#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace crypty::recovery::ntfs {
namespace {

constexpr std::uint32_t ATTR_DATA = 0x80;

bool read_u16(
    const std::vector<std::uint8_t>& data,
    std::size_t offset,
    std::uint16_t& value
) {
    if (offset > data.size() || data.size() - offset < 2) {
        return false;
    }

    value = static_cast<std::uint16_t>(data[offset]) |
            (static_cast<std::uint16_t>(data[offset + 1]) << 8);
    return true;
}

bool read_u32(
    const std::vector<std::uint8_t>& data,
    std::size_t offset,
    std::uint32_t& value
) {
    if (offset > data.size() || data.size() - offset < 4) {
        return false;
    }

    value = static_cast<std::uint32_t>(data[offset]) |
            (static_cast<std::uint32_t>(data[offset + 1]) << 8) |
            (static_cast<std::uint32_t>(data[offset + 2]) << 16) |
            (static_cast<std::uint32_t>(data[offset + 3]) << 24);
    return true;
}

bool read_u64(
    const std::vector<std::uint8_t>& data,
    std::size_t offset,
    std::uint64_t& value
) {
    if (offset > data.size() || data.size() - offset < 8) {
        return false;
    }

    value = 0;

    for (unsigned int i = 0; i < 8; ++i) {
        value |= static_cast<std::uint64_t>(data[offset + i]) << (i * 8);
    }

    return true;
}

bool range_fits(
    std::size_t total_size,
    std::size_t offset,
    std::size_t length
) {
    return offset <= total_size && length <= total_size - offset;
}

} // namespace

bool extract_data_attribute(
    const std::vector<std::uint8_t>& record,
    std::uint16_t first_attribute_offset,
    NtfsDataAttribute& output
) {
    output = {};

    std::vector<AttributeView> attributes;

    if (!parse_attributes(record, first_attribute_offset, attributes)) {
        return false;
    }

    for (const auto& attribute : attributes) {
        if (attribute.type != ATTR_DATA) {
            continue;
        }

        const std::size_t offset = attribute.offset;
        const std::size_t length = attribute.length;

        // Attribute names identify alternate data streams.
        // This function deliberately handles only the unnamed stream.
        if (!range_fits(record.size(), offset, length) || length < 16) {
            return false;
        }

        const std::uint8_t name_length = record[offset + 9];

        if (name_length != 0) {
            continue;
        }

        NtfsDataAttribute parsed;

        if (!attribute.non_resident) {
            if (length < 24) {
                return false;
            }

            std::uint32_t value_length = 0;
            std::uint16_t value_offset = 0;

            if (!read_u32(record, offset + 16, value_length) ||
                !read_u16(record, offset + 20, value_offset)) {
                return false;
            }

            if (value_offset < 24 ||
                !range_fits(length, value_offset, value_length)) {
                return false;
            }

            parsed.resident = true;
            parsed.data_size = value_length;
            parsed.initialized_size = value_length;
            parsed.allocated_size = value_length;

            parsed.resident_data.assign(
                record.begin() + offset + value_offset,
                record.begin() + offset + value_offset + value_length
            );

            output = std::move(parsed);
            return true;
        }

        if (length < 64) {
            return false;
        }

        std::uint16_t mapping_pairs_offset = 0;

        if (!read_u16(record, offset + 32, mapping_pairs_offset) ||
            !read_u64(record, offset + 40, parsed.allocated_size) ||
            !read_u64(record, offset + 48, parsed.data_size) ||
            !read_u64(record, offset + 56, parsed.initialized_size)) {
            return false;
        }

        if (mapping_pairs_offset < 64 ||
            mapping_pairs_offset >= length ||
            parsed.initialized_size > parsed.data_size) {
            return false;
        }

        parsed.resident = false;

        const std::size_t runlist_offset = offset + mapping_pairs_offset;
        const std::size_t runlist_size = length - mapping_pairs_offset;

        if (!parse_data_runs(
                record.data() + runlist_offset,
                runlist_size,
                parsed.runs)) {
            return false;
        }

        output = std::move(parsed);
        return true;
    }

    return true;
}

} // namespace crypty::recovery::ntfs
