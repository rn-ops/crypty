
#pragma once

#include <cstdint>
#include <vector>

namespace crypty::recovery::ntfs {

struct NtfsDataRun {
    std::uint64_t lcn = 0;
    std::uint64_t length = 0;
    bool sparse = false;
};

// Parses NTFS mapping pairs into logical cluster runs.
// Returns false for malformed or truncated input.
bool parse_data_runs(
    const std::uint8_t* data,
    std::size_t size,
    std::vector<NtfsDataRun>& runs
);

} // namespace crypty::recovery::ntfs
