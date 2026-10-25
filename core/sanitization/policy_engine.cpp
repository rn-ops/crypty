
#include "crypty/sanitization/policy_engine.hpp"

#include <algorithm>
#include <utility>

namespace crypty::sanitization {
namespace {

bool contains_method(
    const std::vector<Method>& methods,
    Method candidate
) {
    return std::find(methods.begin(), methods.end(), candidate)
        != methods.end();
}

SanitizationPlan blocked_plan(
    const SanitizationPolicy& policy,
    const SanitizationTarget& target,
    PlanStatus status,
    std::string reason
) {
    SanitizationPlan plan;
    plan.device_id = target.device_id;
    plan.policy_id = policy.policy_id;
    plan.target_kind = target.kind;
    plan.target_path = target.target_path;
    plan.target_identity = target.target_identity;
    plan.media_type = target.media_type;
    plan.required_level = policy.required_level;
    plan.status = status;
    plan.status_reason = std::move(reason);
    plan.target_capacity_bytes = target.capacity_bytes;
    plan.requires_post_sanitization_validation = policy.require_validation;
    plan.requires_audit_evidence = policy.require_audit_evidence;
    return plan;
}

} // namespace

SanitizationPlan PolicyEngine::create_plan(
    const SanitizationPolicy& policy,
    const SanitizationTarget& target
) const {
    if (policy.policy_id.empty()) {
        return blocked_plan(
            policy, target, PlanStatus::Blocked,
            "Policy ID is required."
        );
    }

    if (policy.permitted_methods.empty()) {
        return blocked_plan(
            policy, target, PlanStatus::Blocked,
            "The policy permits no sanitization methods."
        );
    }

    if (target.device_id.empty()) {
        return blocked_plan(
            policy, target, PlanStatus::Blocked,
            "Target identifier is required."
        );
    }

    if (target.capacity_bytes == 0) {
        return blocked_plan(
            policy, target, PlanStatus::Blocked,
            "Target capacity must be non-zero."
        );
    }

    if (target.kind == TargetKind::Unknown ||
        target.media_type == MediaType::Unknown) {
        return blocked_plan(
            policy, target, PlanStatus::Unsupported,
            "Target kind or media type is unknown."
        );
    }

    if (target.kind == TargetKind::DiskImageFile) {
        if (target.target_path.empty()) {
            return blocked_plan(
                policy, target, PlanStatus::Blocked,
                "An explicit disk-image path is required."
            );
        }

        if (policy.required_level != AssuranceLevel::Clear) {
            return blocked_plan(
                policy, target, PlanStatus::Unsupported,
                "File overwrite cannot establish Purge or Destroy assurance."
            );
        }

        if (!contains_method(
                policy.permitted_methods, Method::ImageFileOverwrite) ||
            !contains_method(
                target.available_methods, Method::ImageFileOverwrite)) {
            return blocked_plan(
                policy, target, PlanStatus::Unsupported,
                "Image-file overwrite is not permitted and available."
            );
        }

        SanitizationPlan plan;
        plan.device_id = target.device_id;
        plan.policy_id = policy.policy_id;
        plan.target_kind = TargetKind::DiskImageFile;
        plan.target_path = target.target_path;
        plan.target_identity = target.target_identity;
        plan.media_type = target.media_type;
        plan.required_level = policy.required_level;
        plan.target_capacity_bytes = target.capacity_bytes;
        plan.status = PlanStatus::Ready;
        plan.status_reason =
            "Ready for file-backed overwrite; execution is not yet complete.";

        plan.steps.push_back({
            Method::ImageFileOverwrite,
            "Overwrite the explicitly selected disk-image file and validate it.",
            false,
            true
        });

        plan.requires_post_sanitization_validation = true;
        plan.requires_audit_evidence = policy.require_audit_evidence;
        return plan;
    }

    // Physical-device execution is not implemented in this backend yet.
    return blocked_plan(
        policy, target, PlanStatus::Unsupported,
        "Physical-device sanitization is not implemented."
    );
}

} // namespace crypty::sanitization
