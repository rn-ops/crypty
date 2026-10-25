
#include "recovery_engine.hpp"

#include "../filesystem/detector.hpp"
#include <crypty/filesystem/types.hpp>

#include "ntfs/ntfs_recovery.hpp"
#include "fat32/fat32_recovery.hpp"
#include "exfat/exfat_recovery.hpp"

namespace crypty::recovery {

std::vector<FileEntry> RecoveryEngine::scan(const ReadAt& read_at) {
    const auto fs = crypty::filesystem::detect_filesystem(read_at);

    if (fs.status != crypty::filesystem::DetectionStatus::Detected) {
        return {};
    }

    switch (fs.type) {
    case crypty::filesystem::FilesystemType::NTFS:
        return crypty::recovery::ntfs::scan_mft(read_at);

    case crypty::filesystem::FilesystemType::FAT32:
        return crypty::recovery::fat32::Fat32Recovery::find_deleted_entries(
            read_at
        );

    case crypty::filesystem::FilesystemType::exFAT:
        return crypty::recovery::exfat::ExFatRecovery::find_deleted_entries(
            read_at
        );

    case crypty::filesystem::FilesystemType::Unknown:
    default:
        return {};
    }
}

RecoveryResult RecoveryEngine::recover(
    const ReadAt& read_at,
    const FileEntry& entry,
    const std::string& destination
) {
    const auto fs = crypty::filesystem::detect_filesystem(read_at);

    if (fs.status != crypty::filesystem::DetectionStatus::Detected) {
        return {false, "Filesystem detection failed; recovery was not attempted.", 0};
    }

    switch (fs.type) {
    case crypty::filesystem::FilesystemType::FAT32: {
        bool complete = false;

        const auto bytes =
            crypty::recovery::fat32::Fat32Recovery::recover_to(
                read_at, entry, destination, complete
            );

        return {
            complete,
            complete ? "Recovery completed."
                     : "Recovery was incomplete or failed.",
            static_cast<std::uint64_t>(bytes)
        };
    }

    case crypty::filesystem::FilesystemType::NTFS:
        return {
            false,
            "NTFS recovery is not yet connected to the modular recovery API.",
            0
        };

    case crypty::filesystem::FilesystemType::exFAT:
        return {
            false,
            "exFAT scanning is available, but file recovery is not implemented.",
            0
        };

    case crypty::filesystem::FilesystemType::Unknown:
    default:
        return {false, "Unsupported or unknown filesystem.", 0};
    }
}

} // namespace crypty::recovery
