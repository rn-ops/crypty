
#pragma once

#include "sanitization_policy.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace crypty::sanitization {

enum class PlanStatus {
    Ready,
    Unsupported,
    RequiresUserConfirmation,
    Blocked
};

enum class TargetKind {
    Unknown,
    DiskImageFile,
    PhysicalDevice
};

struct SanitizationStep {
    Method method = Method::None;
    std::string description;
    bool requires_device_support = false;
    bool requires_validation = true;
};


struct FileIdentity {
    bool valid = false;

    // Windows: volume serial number.
    // POSIX: device ID.
    std::uint64_t volume_or_device_id = 0;

    // Windows: file ID (low/high parts).
    // POSIX: inode number.
    std::uint64_t file_id_high = 0;
    std::uint64_t file_id_low = 0;
};


struct SanitizationPlan {
    std::string plan_id;
    std::string device_id;
    std::string policy_id;

    TargetKind target_kind = TargetKind::Unknown;

    // Used only when target_kind == DiskImageFile.
    // The execution backend must independently validate this path.
    std::string target_path;

    MediaType media_type = MediaType::Unknown;
    AssuranceLevel required_level = AssuranceLevel::Clear;

    PlanStatus status = PlanStatus::Blocked;
    std::string status_reason;

    std::vector<SanitizationStep> steps;

    std::uint64_t target_capacity_bytes = 0;

    bool requires_post_sanitization_validation = true;
    bool requires_audit_evidence = true;

    FileIdentity target_identity;
};

} // namespace crypty::sanitization
