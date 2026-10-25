
#pragma once

#include "crypty/sanitization/sanitization_plan.hpp"
#include "crypty/sanitization/sanitization_result.hpp"
#include "crypty/sanitization/execution_authorization.hpp"

namespace crypty::sanitization {

class SanitizationEngine {
public:
    [[nodiscard]]
    SanitizationResult execute(
        const SanitizationPlan& plan,
        const ExecutionAuthorization& authorization
    );
};

} // namespace crypty::sanitization
