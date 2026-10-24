#pragma once

#include <cstddef>
#include <cstdint>
#include <functional>

namespace crypty::filesystem {

using ReadAt = std::function<
    std::size_t(
        std::uint64_t,
        std::uint8_t*,
        std::size_t
    )
>;

}