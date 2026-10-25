#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace crypty::platform {

struct StorageDevice {
    std::string path;
    std::string name;
    std::string filesystem;
    std::string media_type;
    std::string interface_name;
    std::uint64_t capacity = 0;
    std::string status;
};

std::vector<StorageDevice> enumerate_devices();

std::size_t read_media(
    const std::string& path,
    std::uint64_t offset,
    std::uint8_t* output,
    std::size_t capacity
);

} // namespace crypty::platform
