
#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace crypty::recovery::ntfs {

struct AttributeView {
    std::uint32_t type = 0;
    std::size_t offset = 0;
    std::size_t length = 0;
    bool non_resident = false;
};

// Validates and applies update-sequence-array fixups in-place.
// The record buffer must contain exactly one complete MFT record.
bool prepare_mft_record(
    std::vector<std::uint8_t>& record,
    std::uint32_t bytes_per_sector,
    std::uint16_t& first_attribute_offset,
    std::uint16_t& flags
);

// Reads bounded attribute headers from a prepared MFT record.
// Returns false if the attribute sequence is malformed.
bool parse_attributes(
    const std::vector<std::uint8_t>& record,
    std::uint16_t first_attribute_offset,
    std::vector<AttributeView>& attributes
);

} // namespace crypty::recovery::ntfs
