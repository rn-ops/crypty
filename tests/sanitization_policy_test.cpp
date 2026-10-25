
#include "crypty/sanitization/policy_engine.hpp"

#include <cassert>
#include <iostream>

using namespace crypty::sanitization;

namespace {

SanitizationPolicy make_policy(
    AssuranceLevel level,
    Method method
) {
    SanitizationPolicy policy;
    policy.policy_id = "TEST-POLICY";
    policy.policy_version = "1.0";
    policy.required_level = level;
    policy.require_validation = true;
    policy.require_audit_evidence = true;
    policy.permitted_methods = {method};
    return policy;
}

SanitizationTarget make_image_target() {
    SanitizationTarget target;
    target.device_id = "TEST-IMAGE";
    target.kind = TargetKind::DiskImageFile;
    target.target_path = "test-image.img";
    target.media_type = MediaType::HDD;
    target.capacity_bytes = 1024 * 1024;
    target.available_methods = {Method::ImageFileOverwrite};

    target.target_identity.valid = true;
    target.target_identity.volume_or_device_id = 1;
    target.target_identity.file_id_high = 0;
    target.target_identity.file_id_low = 42;



    return target;
}

SanitizationTarget make_physical_target() {
    SanitizationTarget target;
    target.device_id = "TEST-PHYSICAL-DEVICE";
    target.kind = TargetKind::PhysicalDevice;
    target.media_type = MediaType::HDD;
    target.capacity_bytes = 1024 * 1024;
    target.available_methods = {Method::Overwrite};
    return target;
}

void test_clear_image_overwrite_is_plannable() {
    PolicyEngine engine;
    auto policy = make_policy(
        AssuranceLevel::Clear,
        Method::ImageFileOverwrite
    );

    const auto plan = engine.create_plan(policy, make_image_target());

    assert(plan.status == PlanStatus::Ready);
    assert(plan.target_kind == TargetKind::DiskImageFile);
    assert(plan.target_path == "test-image.img");
    assert(plan.steps.size() == 1);
    assert(plan.steps[0].method == Method::ImageFileOverwrite);
    assert(plan.requires_post_sanitization_validation);
    assert(plan.requires_audit_evidence);
    assert(plan.target_identity.valid);
    assert(plan.target_identity.volume_or_device_id == 1);
    assert(plan.target_identity.file_id_low == 42);
}

void test_image_overwrite_cannot_claim_purge() {
    PolicyEngine engine;
    auto policy = make_policy(
        AssuranceLevel::Purge,
        Method::ImageFileOverwrite
    );

    const auto plan = engine.create_plan(policy, make_image_target());

    assert(plan.status == PlanStatus::Unsupported);
    assert(plan.steps.empty());
}

void test_unknown_physical_media_is_rejected() {
    PolicyEngine engine;
    auto policy = make_policy(
        AssuranceLevel::Clear,
        Method::Overwrite
    );

    auto target = make_physical_target();
    target.media_type = MediaType::Unknown;

    const auto plan = engine.create_plan(policy, target);

    assert(plan.status == PlanStatus::Unsupported);
    assert(plan.steps.empty());
}

void test_image_path_is_required() {
    PolicyEngine engine;
    auto policy = make_policy(
        AssuranceLevel::Clear,
        Method::ImageFileOverwrite
    );

    auto target = make_image_target();
    target.target_path.clear();

    const auto plan = engine.create_plan(policy, target);

    assert(plan.status == PlanStatus::Blocked);
    assert(plan.steps.empty());
}

void test_method_must_be_permitted_and_available() {
    PolicyEngine engine;
    auto policy = make_policy(
        AssuranceLevel::Clear,
        Method::ImageFileOverwrite
    );

    auto target = make_image_target();
    target.available_methods.clear();

    const auto plan = engine.create_plan(policy, target);

    assert(plan.status == PlanStatus::Unsupported);
    assert(plan.steps.empty());
}

void test_image_file_does_not_require_underlying_media_type() {
    PolicyEngine engine;
    auto policy = make_policy(
        AssuranceLevel::Clear,
        Method::ImageFileOverwrite
    );
    auto target = make_image_target();
    target.media_type = MediaType::Unknown;

    const auto plan = engine.create_plan(policy, target);

    assert(plan.status == PlanStatus::Ready);
    assert(plan.steps.size() == 1);
}

void test_image_file_requires_captured_identity() {
    PolicyEngine engine;
    auto policy = make_policy(
        AssuranceLevel::Clear,
        Method::ImageFileOverwrite
    );
    auto target = make_image_target();
    target.target_identity.valid = false;

    const auto plan = engine.create_plan(policy, target);

    assert(plan.status == PlanStatus::Blocked);
    assert(plan.steps.empty());
}

void test_physical_device_remains_blocked() {
    PolicyEngine engine;
    auto policy = make_policy(
        AssuranceLevel::Clear,
        Method::Overwrite
    );

    const auto plan = engine.create_plan(policy, make_physical_target());

    assert(plan.status == PlanStatus::Unsupported);
    assert(plan.steps.empty());
}

void test_empty_policy_id_is_rejected() {
    PolicyEngine engine;
    auto policy = make_policy(
        AssuranceLevel::Clear,
        Method::ImageFileOverwrite
    );
    policy.policy_id.clear();

    const auto plan = engine.create_plan(policy, make_image_target());

    assert(plan.status == PlanStatus::Blocked);
    assert(plan.steps.empty());
}

} // namespace

int main() {
    test_clear_image_overwrite_is_plannable();
    test_image_overwrite_cannot_claim_purge();
    test_unknown_physical_media_is_rejected();
    test_image_path_is_required();
    test_method_must_be_permitted_and_available();
    test_image_file_does_not_require_underlying_media_type();
    test_image_file_requires_captured_identity();
    test_physical_device_remains_blocked();
    test_empty_policy_id_is_rejected();

    std::cout << "All sanitization policy tests passed.\n";
    return 0;
}
