#include <algorithm>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

extern "C" {
void* crypty_sanitization_plan_image_file(const char* path);
void crypty_sanitization_plan_destroy(void* handle);
int crypty_sanitization_plan_status(void* handle);
const char* crypty_sanitization_plan_reason(void* handle);
const char* crypty_sanitization_plan_path(void* handle);
std::uint64_t crypty_sanitization_plan_capacity(void* handle);
int crypty_sanitization_execute_image_file(
    void* handle,
    int confirmed,
    const char* confirmed_path,
    std::uint64_t confirmed_capacity,
    const char* confirmation_phrase
);
int crypty_sanitization_result_successful(void* handle);
const char* crypty_sanitization_result_error_code(void* handle);
}

namespace {
constexpr char kMarker[] = "CRYPTY_DISPOSABLE_IMAGE_V1\n";
constexpr char kConfirmation[] = "OVERWRITE THIS FILE";

std::filesystem::path unique_path(const char* suffix) {
    const auto ticks = std::chrono::steady_clock::now().time_since_epoch().count();
    return std::filesystem::temp_directory_path() /
        (std::string("crypty_native_sanitization_") +
         std::to_string(ticks) + suffix);
}

bool write_bytes(
    const std::filesystem::path& path,
    const std::vector<unsigned char>& bytes
) {
    std::ofstream file(path, std::ios::binary | std::ios::trunc);
    if (!file) return false;
    file.write(
        reinterpret_cast<const char*>(bytes.data()),
        static_cast<std::streamsize>(bytes.size())
    );
    file.flush();
    return file.good();
}

std::vector<unsigned char> read_bytes(const std::filesystem::path& path) {
    std::ifstream file(path, std::ios::binary);
    return {
        std::istreambuf_iterator<char>(file),
        std::istreambuf_iterator<char>()
    };
}

bool test_marked_image_executes_and_verifies() {
    const auto path = unique_path("_marked.img");
    constexpr std::size_t payload_size = 64 * 1024;
    std::vector<unsigned char> original(sizeof(kMarker) - 1 + payload_size, 0xA5);
    std::copy(kMarker, kMarker + sizeof(kMarker) - 1, original.begin());
    if (!write_bytes(path, original)) return false;

    void* plan = crypty_sanitization_plan_image_file(path.u8string().c_str());
    bool passed = false;
    if (plan != nullptr && crypty_sanitization_plan_status(plan) == 0) {
        const std::string canonical_path = crypty_sanitization_plan_path(plan);
        const auto capacity = crypty_sanitization_plan_capacity(plan);
        const int executed = crypty_sanitization_execute_image_file(
            plan, 1, canonical_path.c_str(), capacity, kConfirmation
        );
        const auto contents = read_bytes(path);
        passed = executed == 1 &&
            crypty_sanitization_result_successful(plan) == 1 &&
            contents.size() == original.size() &&
            std::all_of(contents.begin(), contents.end(),
                [](unsigned char byte) { return byte == 0; });
        if (!passed) {
            std::cerr << "Marked image failed: "
                      << crypty_sanitization_result_error_code(plan) << '\n';
        }
    } else if (plan != nullptr) {
        std::cerr << "Marked image was blocked: "
                  << crypty_sanitization_plan_reason(plan) << '\n';
    }

    if (plan != nullptr) crypty_sanitization_plan_destroy(plan);
    std::error_code ec;
    std::filesystem::remove(path, ec);
    return passed && !ec;
}

bool test_unmarked_file_is_blocked_unchanged() {
    const auto path = unique_path("_ordinary.img");
    const std::vector<unsigned char> original = {
        'N', 'O', 'T', '_', 'A', '_', 'C', 'R', 'Y', 'P', 'T', 'Y', 0x11, 0x22
    };
    if (!write_bytes(path, original)) return false;

    void* plan = crypty_sanitization_plan_image_file(path.u8string().c_str());
    const bool blocked = plan != nullptr && crypty_sanitization_plan_status(plan) == 3;
    const auto contents = read_bytes(path);
    if (plan != nullptr) crypty_sanitization_plan_destroy(plan);
    std::error_code ec;
    std::filesystem::remove(path, ec);
    return blocked && contents == original && !ec;
}
} // namespace

int main() {
    if (!test_marked_image_executes_and_verifies() ||
        !test_unmarked_file_is_blocked_unchanged()) {
        std::cerr << "Native sanitization bridge tests FAILED.\n";
        return 1;
    }
    std::cout << "Native sanitization bridge tests passed.\n";
    return 0;
}
