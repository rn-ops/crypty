
#pragma once

#include <string>
#include <vector>

namespace crypty::sanitization {

enum class AssuranceLevel {
    Clear,
    Purge,
    Destroy
};

enum class MediaType {
    Unknown,
    HDD,
    SATA_SSD,
    NVME_SSD,
    USB_FLASH,
    REMOVABLE_DISK
};

enum class Method {
    None,
    ImageFileOverwrite,
    Overwrite,
    DeviceNativeSanitize,
    CryptoErase,
    PhysicalDestruction
};

struct SanitizationPolicy {
    std::string policy_id;
    std::string policy_version;

    AssuranceLevel required_level = AssuranceLevel::Clear;

    bool require_validation = true;
    bool require_audit_evidence = true;
    bool allow_fallback = false;

    // Ordered from preferred to least preferred.
    std::vector<Method> permitted_methods;
};

} // namespace crypty::sanitization
