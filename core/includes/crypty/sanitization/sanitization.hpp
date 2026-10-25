#pragma once

#include "sanitization_plan.hpp"
#include "sanitization_policy.hpp"
#include "sanitization_result.hpp"
#include "verification.hpp"

namespace crypty::sanitization {

// The policy API plans eligible disposable-image file overwrites. The native
// executor independently inspects and validates the file before writing.
// Physical-device sanitization remains unsupported until media-specific
// executors and verification are implemented.
class PolicyEngine;
class SanitizationEngine;

} // namespace crypty::sanitization
