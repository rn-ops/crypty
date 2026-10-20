
#pragma once

#include "runlist.hpp"

#include <cstdint>
#include <vector>

namespace crypty::recovery::ntfs {

struct NtfsDataAttribute {
    bool resident = false;

    std::uint64_t allocated_size = 0;
    std::uint64_t data_size = 0;
    std::uint64_t initialized_size = 0;

    // Populated only for resident attributes.
    std::vector<std::uint8_t> resident_data;

    // Populated only for non-resident attributes.
    std::vector<NtfsDataRun> runs;
};

// Extracts the unnamed $DATA stream from a validated MFT record.
// Returns false if its attribute structure is malformed.
// Returns true with output empty if the record has no unnamed $DATA stream.
bool extract_data_attribute(
    const std::vector<std::uint8_t>& record,
    std::uint16_t first_attribute_offset,
    NtfsDataAttribute& output
);

} // namespace crypty::recovery::ntfs
