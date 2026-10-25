
#pragma once

#include "sanitization_plan.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace crypty::sanitization {

enum class ExecutionStatus {
    NotStarted,
    InProgress,
    Completed,
    Failed,
    Cancelled
};

enum class ValidationStatus {
    NotPerformed,
    Passed,
    Failed,
    Inconclusive
};

struct SanitizationResult {
    std::string operation_id;
    std::string plan_id;
    std::string device_id;

    ExecutionStatus execution_status = ExecutionStatus::NotStarted;
    ValidationStatus validation_status = ValidationStatus::NotPerformed;

    Method method_used = Method::None;
    AssuranceLevel required_level = AssuranceLevel::Clear;

    std::uint64_t bytes_processed = 0;
    std::uint64_t target_capacity_bytes = 0;

    std::string started_at_utc;
    std::string completed_at_utc;

    std::string error_code;
    std::string error_message;

    std::vector<std::string> warnings;

    // True only when execution and required validation both meet
    // the operation's defined success criteria.
    bool successful = false;
};

} // namespace crypty::sanitization
