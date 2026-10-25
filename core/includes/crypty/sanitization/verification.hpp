
#pragma once

#include "sanitization_result.hpp"

#include <cstdint>
#include <string>
#include <vector>

namespace crypty::sanitization {

enum class VerificationMethod {
    None,
    ReadBackSample,
    FullReadBack,
    DeviceStatusCheck,
    CryptographicEraseEvidence,
    ExternalInspection
};

enum class VerificationOutcome {
    NotStarted,
    Passed,
    Failed,
    Inconclusive,
    Unsupported
};

struct VerificationCheck {
    VerificationMethod method = VerificationMethod::None;
    VerificationOutcome outcome = VerificationOutcome::NotStarted;

    std::string description;
    std::string details;

    std::uint64_t bytes_checked = 0;

    // Identifies the evidence supporting this check.
    std::string evidence_id;
};

struct VerificationReport {
    std::string verification_id;
    std::string operation_id;
    std::string device_id;

    VerificationOutcome outcome = VerificationOutcome::NotStarted;

    std::vector<VerificationCheck> checks;
    std::vector<std::string> warnings;

    std::string started_at_utc;
    std::string completed_at_utc;
    std::string summary;

    // This records the verification conclusion, not a guarantee
    // that every physical cell on a storage device was inspected.
    bool supports_sanitization_claim = false;
};

} // namespace crypty::sanitization
