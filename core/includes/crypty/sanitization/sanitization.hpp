#pragma once

#include "sanitization_plan.hpp"
#include "sanitization_policy.hpp"
#include "sanitization_result.hpp"
#include "verification.hpp"

namespace crypty::sanitization {

// Phase 1 is intentionally a planning-only API. It does not open or modify
// disk-image files or physical devices.
class PolicyEngine;
class SanitizationEngine;

} // namespace crypty::sanitization
