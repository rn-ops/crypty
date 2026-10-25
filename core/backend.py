
from __future__ import annotations

from data.demo_data import RECOVERY_RESULTS


class SimulatedBackend:
    """Read-only demonstration backend. Never performs real recovery."""

    mode = "simulated"
    is_simulated = True

    def analyze_device(self, device: dict) -> dict:
        return {
            "filesystem": device["filesystem"],
            "media_type": device["media_type"],
            "status": device["status"],
            "mode": self.mode,
            "is_simulated": True,
            "message": "Demonstration data only. No device was analyzed.",
        }

    def recover_files(self, device: dict) -> dict:
        valid = sum(
            result["status"] == "Valid"
            for result in RECOVERY_RESULTS
        )
        review = sum(
            result["status"] == "Review"
            for result in RECOVERY_RESULTS
        )
        invalid = len(RECOVERY_RESULTS) - valid - review

        return {
            "files_found": len(RECOVERY_RESULTS),
            "recoverable": valid,
            "needs_review": review,
            "invalid": invalid,
            "mode": self.mode,
            "is_simulated": True,
            "success": False,
            "message": (
                "These are demonstration counts, not actual recovery results. "
                "No files were recovered."
            ),
        }
