
#pragma once

#include <cstdint>
#include <string>

namespace crypty::sanitization {

// Records the user's explicit approval for a specific destructive operation.
// This is an application-level safety gate, not a security boundary.
struct ExecutionAuthorization {
    bool confirmed = false;

    // Must match the target presented to the user for confirmation.
    std::string confirmed_target_path;

    // Must match the target capacity shown to the user.
    std::uint64_t confirmed_target_capacity_bytes = 0;

    // The UI must require the user to enter this exact phrase.
    std::string confirmation_phrase;
};

inline constexpr const char* kSanitizationConfirmationPhrase =
    "OVERWRITE THIS FILE";

} // namespace crypty::sanitization
