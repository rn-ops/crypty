
#pragma once

#include "crypty/sanitization/sanitization_plan.hpp"
#include "crypty/sanitization/sanitization_result.hpp"

namespace crypty::sanitization {

class SanitizationEngine {
public:
    [[nodiscard]]
    SanitizationResult execute(const SanitizationPlan& plan);
};

} // namespace crypty::sanitization
