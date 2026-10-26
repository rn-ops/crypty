#pragma once

#include <crypty/sanitization/sanitization_plan.hpp>
#include <crypty/sanitization/sanitization_result.hpp>
#include <crypty/sanitization/execution_authorization.hpp>

namespace crypty::sanitization {

// Executes a physical-device overwrite only after re-enumerating and
// revalidating the target. Windows implementation is currently supported;
// other platforms return Unsupported without opening a device for writing.
SanitizationResult execute_physical_device_overwrite(
    const SanitizationPlan& plan,
    const ExecutionAuthorization& authorization);

} // namespace crypty::sanitization
