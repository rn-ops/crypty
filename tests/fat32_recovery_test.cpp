
#include "../core/recovery/fat32/fat32_recovery.hpp"

#include <cassert>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <vector>

using crypty::FileEntry;
using crypty::filesystem::ReadAt;
using crypty::recovery::fat32::Fat32Recovery;

using Image = std::vector<std::uint8_t>;

constexpr std::size_t SECTOR = 512;
constexpr std::size_t FAT_OFFSET = SECTOR;
constexpr std::size_t ROOT_OFFSET = 2 * SECTOR;
constexpr std::size_t FILE_OFFSET = 3 * SECTOR;
constexpr std::uint32_t EOC = 0x0FFFFFFF;

void set_u16(Image& image, std::size_t offset, std::uint16_t value) {
    image[offset] = static_cast<std::uint8_t>(value);
    image[offset + 1] = static_cast<std::uint8_t>(value >> 8);
}

void set_u32(Image& image, std::size_t offset, std::uint32_t value) {
    set_u16(image, offset, static_cast<std::uint16_t>(value));
    set_u16(image, offset + 2, static_cast<std::uint16_t>(value >> 16));
}

void make_fat_entry(Image& image, std::uint32_t cluster,
                    std::uint32_t value) {
    set_u32(image, FAT_OFFSET + cluster * 4, value);
}

Image make_volume(std::uint32_t file_size = 5) {
    Image image(4 * SECTOR, 0);

    // FAT32 boot sector.
    set_u16(image, 11, 512);       // Bytes per sector.
    image[13] = 1;                 // Sectors per cluster.
    set_u16(image, 14, 1);         // Reserved sectors.
    image[16] = 1;                 // Number of FATs.
    set_u32(image, 36, 1);         // Sectors per FAT.
    set_u32(image, 44, 2);         // Root directory cluster.
    std::memcpy(image.data() + 82, "FAT32", 5);
    image[510] = 0x55;
    image[511] = 0xAA;

    // Root directory and file cluster chains terminate at EOC.
    make_fat_entry(image, 2, EOC);
    make_fat_entry(image, 3, EOC);

    // Deleted 8.3 directory entry at the start of the root cluster.
    auto* entry = image.data() + ROOT_OFFSET;
    entry[0] = 0xE5;
    std::memcpy(entry + 1, "ESTFILE", 7);
    std::memcpy(entry + 8, "TXT", 3);
    entry[11] = 0x20;              // Archive attribute.
    set_u16(image, ROOT_OFFSET + 20, 0); // High cluster word.
    set_u16(image, ROOT_OFFSET + 26, file_size == 0 ? 0 : 3);
    set_u32(image, ROOT_OFFSET + 28, file_size);

    // Known file contents, with the rest of the cluster zero-filled.
    if (file_size != 0) {
        std::memcpy(image.data() + FILE_OFFSET, "hello", 5);
    }

    return image;
}

ReadAt reader_for(const Image& image) {
    return [&image](std::uint64_t offset, std::uint8_t* output,
                    std::size_t count) -> std::size_t {
        if (offset > image.size()) {
            return 0;
        }

        const auto start = static_cast<std::size_t>(offset);
        if (count > image.size() - start) {
            return 0;
        }

        std::memcpy(output, image.data() + start, count);
        return count;
    };
}

std::string output_path(const char* filename) {
    return (std::filesystem::temp_directory_path() / filename).string();
}

std::string read_file(const std::string& path) {
    std::ifstream input(path, std::ios::binary);
    return std::string(
        std::istreambuf_iterator<char>(input),
        std::istreambuf_iterator<char>()
    );
}

void test_scan_and_recover_known_file() {
    auto image = make_volume();
    const auto original = image;
    const auto entries = Fat32Recovery::find_deleted_entries(reader_for(image));

    assert(entries.size() == 1);
    assert(entries[0].deleted);
    assert(entries[0].size == 5);
    assert(entries[0].clusters.size() == 1);
    assert(entries[0].clusters[0] == 3);

    const auto path = output_path("crypty_fat32_known.bin");
    std::filesystem::remove(path);

    bool complete = false;
    const auto bytes = Fat32Recovery::recover_to(
        reader_for(image), entries[0], path, complete
    );

    assert(bytes == 5);
    assert(complete);
    assert(read_file(path) == "hello");
    assert(image == original); // The source volume was not modified.

    std::filesystem::remove(path);
}

void test_failed_data_read_is_incomplete() {
    const auto image = make_volume();
    const auto entries = Fat32Recovery::find_deleted_entries(reader_for(image));
    assert(entries.size() == 1);

    auto reader = [&image](std::uint64_t offset, std::uint8_t* output,
                           std::size_t count) -> std::size_t {
        if (offset == FILE_OFFSET) {
            return 0; // Simulate unreadable file data.
        }

        if (offset > image.size()) {
            return 0;
        }

        const auto start = static_cast<std::size_t>(offset);
        if (count > image.size() - start) {
            return 0;
        }

        std::memcpy(output, image.data() + start, count);
        return count;
    };

    const auto path = output_path("crypty_fat32_incomplete.bin");
    std::filesystem::remove(path);

    bool complete = true;
    const auto bytes = Fat32Recovery::recover_to(
        reader, entries[0], path, complete
    );

    assert(bytes == 0);
    assert(!complete);

    std::filesystem::remove(path);
}

void test_zero_byte_file() {
    const auto image = make_volume(0);
    const auto entries = Fat32Recovery::find_deleted_entries(reader_for(image));
    assert(entries.size() == 1);
    assert(entries[0].size == 0);
    assert(entries[0].clusters.empty());

    const auto path = output_path("crypty_fat32_empty.bin");
    std::filesystem::remove(path);

    bool complete = false;
    const auto bytes = Fat32Recovery::recover_to(
        reader_for(image), entries[0], path, complete
    );

    assert(bytes == 0);
    assert(complete);
    assert(std::filesystem::exists(path));
    assert(std::filesystem::file_size(path) == 0);

    std::filesystem::remove(path);
}

void test_invalid_volume_returns_no_entries() {
    const Image image(4 * SECTOR, 0);
    const auto entries = Fat32Recovery::find_deleted_entries(reader_for(image));
    assert(entries.empty());
}

int main() {
    test_scan_and_recover_known_file();
    test_failed_data_read_is_incomplete();
    test_zero_byte_file();
    test_invalid_volume_returns_no_entries();
}
