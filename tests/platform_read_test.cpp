#include "device_access.hpp"

#include <array>
#include <cassert>
#include <filesystem>
#include <fstream>
#include <string>

int main() {
    const auto image =
        std::filesystem::temp_directory_path() / "crypty-platform-read.img";
    const std::array<unsigned char, 8> original{
        0x10, 0x21, 0x32, 0x43, 0x54, 0x65, 0x76, 0x87
    };
    {
        std::ofstream output(image, std::ios::binary | std::ios::trunc);
        output.write(
            reinterpret_cast<const char*>(original.data()),
            static_cast<std::streamsize>(original.size())
        );
        assert(output.good());
    }

    std::array<std::uint8_t, 3> result{};
    const auto bytes_read = crypty::platform::read_media(
        image.string(), 2, result.data(), result.size()
    );
    assert(bytes_read == result.size());
    assert(result[0] == original[2]);
    assert(result[1] == original[3]);
    assert(result[2] == original[4]);

    std::array<std::uint8_t, 4> out_of_range{};
    assert(
        crypty::platform::read_media(
            image.string(), original.size() - 1, out_of_range.data(),
            out_of_range.size()
        ) == 0
    );

    std::array<unsigned char, 8> unchanged{};
    {
        std::ifstream input(image, std::ios::binary);
        input.read(
            reinterpret_cast<char*>(unchanged.data()),
            static_cast<std::streamsize>(unchanged.size())
        );
        assert(input.gcount() == static_cast<std::streamsize>(unchanged.size()));
    }
    assert(unchanged == original);
    std::filesystem::remove(image);

    return 0;
}
