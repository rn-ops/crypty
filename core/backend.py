from __future__ import annotations

from crypty.data.demo_data import RECOVERY_RESULTS


class SimulatedBackend:
    """Read-only backend used by the desktop demonstration."""

    def analyze_device(self, device: dict) -> dict:
        return {
            "filesystem": device["filesystem"],
            "media_type": device["media_type"],
            "status": device["status"],
        }

    def recover_files(self, device: dict) -> dict:
        valid = sum(result["status"] == "Valid" for result in RECOVERY_RESULTS)
        review = sum(result["status"] == "Review" for result in RECOVERY_RESULTS)
        invalid = len(RECOVERY_RESULTS) - valid - review
        return {
            "files_found": len(RECOVERY_RESULTS),
            "recoverable": valid,
            "needs_review": review,
            "invalid": invalid,
        }