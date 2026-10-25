
#include "sanitization_engine.hpp"

namespace crypty::sanitization {

SanitizationResult SanitizationEngine::execute(
    const SanitizationPlan& plan
) {
    SanitizationResult result;

    result.plan_id = plan.plan_id;
    result.device_id = plan.device_id;
    result.required_level = plan.required_level;
    result.target_capacity_bytes = plan.target_capacity_bytes;

    result.execution_status = ExecutionStatus::NotStarted;
    result.validation_status = ValidationStatus::NotPerformed;
    result.successful = false;

    result.error_code = "EXECUTION_BACKEND_UNAVAILABLE";
    result.error_message =
        "No validated sanitization backend is available. "
        "No data was intentionally modified.";

    result.warnings.push_back(
        "Planning does not establish that sanitization occurred."
    );

    return result;
}

} // namespace crypty::sanitization
