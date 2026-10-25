#include "crypty/sanitization/sanitization_plan.hpp"
#include "crypty/sanitization/execution_authorization.hpp"
#include "sanitization_engine.hpp"

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>
#include <algorithm>
#include <stdexcept>
#include <cassert>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <sys/stat.h>
#endif

using namespace crypty::sanitization;

namespace {

constexpr char kMarker[] = "CRYPTY_DISPOSABLE_IMAGE_V1\n";

std::filesystem::path unique_temp_path(const char* suffix) {
    const auto ticks =
        std::chrono::steady_clock::now().time_since_epoch().count();

    return std::filesystem::temp_directory_path() /
        (std::string("crypty_sanitization_") +
         std::to_string(ticks) + suffix);
}

bool write_file(
    const std::filesystem::path& path,
    const std::vector<unsigned char>& bytes
) {
    std::ofstream file(path, std::ios::binary | std::ios::trunc);
    if (!file) {
        return false;
    }

    file.write(
        reinterpret_cast<const char*>(bytes.data()),
        static_cast<std::streamsize>(bytes.size())
    );

    file.flush();
    return file.good();
}

std::vector<unsigned char> read_file(
    const std::filesystem::path& path
) {
    std::ifstream file(path, std::ios::binary);
    return std::vector<unsigned char>(
        std::istreambuf_iterator<char>(file),
        std::istreambuf_iterator<char>()
    );
}

bool capture_file_identity(
    const std::filesystem::path& path,
    FileIdentity& identity
) {
#ifdef _WIN32
    HANDLE file = CreateFileW(
        path.c_str(),
        0,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        nullptr
    );

    if (file == INVALID_HANDLE_VALUE) {
        return false;
    }

    BY_HANDLE_FILE_INFORMATION info{};
    const bool ok = GetFileInformationByHandle(file, &info) != 0;
    CloseHandle(file);

    if (!ok) {
        return false;
    }

    identity.valid = true;
    identity.volume_or_device_id = info.dwVolumeSerialNumber;
    identity.file_id_high = info.nFileIndexHigh;
    identity.file_id_low = info.nFileIndexLow;
    return true;
#else
    struct stat info{};

    if (::stat(path.c_str(), &info) != 0 ||
        !S_ISREG(info.st_mode)) {
        return false;
    }

    identity.valid = true;
    identity.volume_or_device_id =
        static_cast<std::uint64_t>(info.st_dev);
    identity.file_id_high = 0;
    identity.file_id_low =
        static_cast<std::uint64_t>(info.st_ino);
    return true;
#endif
}

SanitizationPlan make_plan(
    const std::filesystem::path& path,
    std::uint64_t size
) {
    SanitizationPlan plan;
    plan.plan_id = "EXECUTION-TEST-001";
    plan.device_id = "TEST-IMAGE";
    plan.policy_id = "TEST-POLICY";
    plan.target_kind = TargetKind::DiskImageFile;
    plan.target_path = path.string();
    if (!capture_file_identity(path, plan.target_identity)) {
        throw std::runtime_error(
            "Could not capture test target file identity."
        );
    }
    plan.media_type = MediaType::HDD;
    plan.required_level = AssuranceLevel::Clear;
    plan.status = PlanStatus::Ready;
    plan.target_capacity_bytes = size;
    plan.requires_post_sanitization_validation = true;
    plan.requires_audit_evidence = true;

    plan.steps.push_back({
        Method::ImageFileOverwrite,
        "Test real file overwrite",
        false,
        true
    });

    return plan;
}

bool test_real_zero_overwrite() {
    const auto path = unique_temp_path("_valid.img");

    // Larger than one 1 MiB engine chunk.
    constexpr std::size_t file_size = 2 * 1024 * 1024 + 37;

    std::vector<unsigned char> original(file_size, 0xA5);
    std::copy(
        kMarker,
        kMarker + sizeof(kMarker) - 1,
        original.begin()
    );

    if (!write_file(path, original)) {
        std::cerr << "Could not create the temporary test image.\n";
        return false;
    }

    bool passed = false;

    try {
        SanitizationEngine engine;
        const auto plan = make_plan(path, file_size);

        // Restored authorization safety test
        ExecutionAuthorization no_authorization;
        const auto rejected = engine.execute(plan, no_authorization);

        assert(!rejected.successful);
        assert(rejected.error_code == "AUTHORIZATION_REQUIRED");

        const auto unchanged = read_file(path);
        assert(unchanged == original);

        ExecutionAuthorization authorization;
        authorization.confirmed = true;
        authorization.confirmed_target_path = plan.target_path;
        authorization.confirmed_target_capacity_bytes =
            plan.target_capacity_bytes;
        authorization.confirmation_phrase =
            kSanitizationConfirmationPhrase;

        const auto result = engine.execute(plan, authorization);

        const auto contents = read_file(path);

        passed =
            result.successful &&
            result.execution_status == ExecutionStatus::Completed &&
            result.validation_status == ValidationStatus::Passed &&
            result.bytes_processed == file_size &&
            contents.size() == file_size;

        if (passed) {
            for (const auto byte : contents) {
                if (byte != 0) {
                    passed = false;
                    break;
                }
            }
        }

        if (!passed) {
            std::cerr
                << "Zero-overwrite test failed. Error code: "
                << result.error_code << "\n"
                << result.error_message << "\n";
        }
    } catch (const std::exception& error) {
        std::cerr << "Execution test exception: "
                  << error.what() << "\n";
    }

    std::error_code ec;
    std::filesystem::remove(path, ec);

    if (ec) {
        std::cerr << "Warning: could not remove test image: "
                  << path.string() << "\n";
    }

    return passed;
}

bool test_unmarked_file_is_rejected() {
    const auto path = unique_temp_path("_unmarked.img");

    const std::vector<unsigned char> original = {
        'N', 'O', 'T', '_', 'C', 'R', 'Y', 'P', 'T', 'Y',
        0x11, 0x22, 0x33, 0x44
    };

    if (!write_file(path, original)) {
        std::cerr << "Could not create the rejection-test file.\n";
        return false;
    }

    bool passed = false;

    try {
        SanitizationEngine engine;
        const auto plan = make_plan(path, original.size());
        
        // Unmarked file test uses default (unauthorized) execution 
        // which will trigger authorization check first, or marker mismatch depending on flow.
        ExecutionAuthorization authorization;
        authorization.confirmed = true;
        authorization.confirmed_target_path = plan.target_path;
        authorization.confirmed_target_capacity_bytes =
            plan.target_capacity_bytes;
        authorization.confirmation_phrase =
            kSanitizationConfirmationPhrase;

        const auto result = engine.execute(plan, authorization);
        const auto contents = read_file(path);

        passed =
            !result.successful &&
            result.execution_status == ExecutionStatus::Failed &&
            result.error_code == "MARKER_MISMATCH" &&
            contents == original;

        if (!passed) {
            std::cerr
                << "Unmarked-file rejection test failed. Error code: "
                << result.error_code << "\n";
        }
    } catch (const std::exception& error) {
        std::cerr << "Rejection test exception: "
                  << error.what() << "\n";
    }

    std::error_code ec;
    std::filesystem::remove(path, ec);

    if (ec) {
        std::cerr << "Warning: could not remove test file: "
                  << path.string() << "\n";
    }

    return passed;
}

} // namespace

int main() {
    const bool overwrite_ok = test_real_zero_overwrite();
    const bool rejection_ok = test_unmarked_file_is_rejected();

    if (!overwrite_ok || !rejection_ok) {
        std::cerr << "Sanitization execution tests FAILED.\n";
        return 1;
    }

    std::cout << "All sanitization execution tests passed.\n";
    return 0;
}