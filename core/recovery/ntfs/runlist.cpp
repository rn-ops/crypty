
#include "runlist.hpp"

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>

namespace crypty::recovery::ntfs {
namespace {

bool read_unsigned(
    const std::uint8_t* data,
    std::size_t size,
    std::size_t& pos,
    unsigned int byte_count,
    std::uint64_t& value
) {
    if (byte_count == 0 || byte_count > 8 ||
        pos > size || byte_count > size - pos) {
        return false;
    }

    value = 0;

    for (unsigned int i = 0; i < byte_count; ++i) {
        value |= static_cast<std::uint64_t>(data[pos++]) << (i * 8);
    }

    return true;
}

bool read_signed_delta(
    const std::uint8_t* data,
    std::size_t size,
    std::size_t& pos,
    unsigned int byte_count,
    std::int64_t& value
) {
    if (byte_count == 0 || byte_count > 8 ||
        pos > size || byte_count > size - pos) {
        return false;
    }

    std::uint64_t raw = 0;

    for (unsigned int i = 0; i < byte_count; ++i) {
        raw |= static_cast<std::uint64_t>(data[pos++]) << (i * 8);
    }

    // Sign-extend values shorter than 64 bits.
    if (byte_count < 8) {
        const unsigned int bits = byte_count * 8;
        if ((raw & (std::uint64_t{1} << (bits - 1))) != 0) {
            raw |= (~std::uint64_t{0}) << bits;
        }
    }

    // Preserve the two's-complement bit pattern.
    std::memcpy(&value, &raw, sizeof(value));
    return true;
}

bool apply_lcn_delta(
    std::uint64_t previous_lcn,
    std::int64_t delta,
    std::uint64_t& next_lcn
) {
    if (delta >= 0) {
        const auto positive = static_cast<std::uint64_t>(delta);

        if (positive >
            std::numeric_limits<std::uint64_t>::max() - previous_lcn) {
            return false;
        }

        next_lcn = previous_lcn + positive;
        return true;
    }

    // Avoid negating INT64_MIN directly.
    const std::uint64_t magnitude =
        static_cast<std::uint64_t>(-(delta + 1)) + 1;

    if (magnitude > previous_lcn) {
        return false;
    }

    next_lcn = previous_lcn - magnitude;
    return true;
}

} // namespace

bool parse_data_runs(
    const std::uint8_t* data,
    std::size_t size,
    std::vector<NtfsDataRun>& runs
) {
    runs.clear();

    if (data == nullptr || size == 0) {
        return false;
    }

    std::size_t pos = 0;
    std::uint64_t current_lcn = 0;
    bool terminated = false;

    while (pos < size) {
        const std::uint8_t header = data[pos++];

        // A zero header terminates the mapping-pairs array.
        if (header == 0) {
            terminated = true;
            break;
        }

        const unsigned int length_bytes = header & 0x0F;
        const unsigned int offset_bytes = header >> 4;

        // A run must encode a length. Offset size zero means sparse.
        if (length_bytes == 0 || length_bytes > 8 ||
            offset_bytes > 8) {
            runs.clear();
            return false;
        }

        std::uint64_t run_length = 0;

        if (!read_unsigned(
                data, size, pos, length_bytes, run_length) ||
            run_length == 0) {
            runs.clear();
            return false;
        }

        if (run_length >
            std::numeric_limits<std::uint64_t>::max() -
                [&]() -> std::uint64_t {
                    std::uint64_t total = 0;
                    for (const auto& run : runs) {
                        if (run.length >
                            std::numeric_limits<std::uint64_t>::max() -
                                total) {
                            return std::numeric_limits<std::uint64_t>::max();
                        }
                        total += run.length;
                    }
                    return total;
                }()) {
            runs.clear();
            return false;
        }

        NtfsDataRun run;
        run.length = run_length;
        run.sparse = (offset_bytes == 0);

        if (!run.sparse) {
            std::int64_t delta = 0;

            if (!read_signed_delta(
                    data, size, pos, offset_bytes, delta) ||
                !apply_lcn_delta(current_lcn, delta, current_lcn)) {
                runs.clear();
                return false;
            }

            run.lcn = current_lcn;
        }

        runs.push_back(run);
    }

    if (!terminated) {
        runs.clear();
        return false;
    }

    return true;
}

} // namespace crypty::recovery::ntfs
