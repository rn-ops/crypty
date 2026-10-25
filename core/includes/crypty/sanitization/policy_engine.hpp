
#pragma once

#include "crypty/sanitization/sanitization_plan.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace crypty::sanitization {

struct SanitizationTarget {
    std::string device_id;
    MediaType media_type = MediaType::Unknown;
    std::uint64_t capacity_bytes = 0;

    TargetKind kind = TargetKind::Unknown;

    // Required for DiskImageFile targets.
    // This must identify an existing, explicitly selected image file.
    std::string target_path;

    // Methods confirmed as available for this target.
    std::vector<Method> available_methods;
    
    FileIdentity target_identity;
};

class PolicyEngine {
public:
    [[nodiscard]]
    SanitizationPlan create_plan(
        const SanitizationPolicy& policy,
        const SanitizationTarget& target
    ) const;
};

} // namespace crypty::sanitization
