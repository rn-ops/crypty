from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIRMATION_PHRASE = "OVERWRITE THIS FILE"


@dataclass
class SanitizationPlanHandle:
    """A native, read-only-inspected plan for one disposable image file."""

    handle: int
    status: str
    reason: str
    target_path: str
    capacity_bytes: int
    closed: bool = False

    @property
    def ready(self) -> bool:
        return self.status == "Ready" and not self.closed


class SanitizationEngine:
    """Python orchestration adapter; policy and destructive work remain native."""

    def __init__(self, backend: Any):
        self.backend = backend

    def plan_image_file(self, path: str | Path) -> SanitizationPlanHandle:
        result = self.backend.create_sanitization_plan(str(path))
        return SanitizationPlanHandle(
            handle=result["_handle"],
            status=result["status_name"],
            reason=result["reason"],
            target_path=result["target_path"],
            capacity_bytes=result["capacity_bytes"],
        )

    def execute_image_file(
        self,
        plan: SanitizationPlanHandle,
        confirmation_phrase: str,
    ) -> dict:
        if plan.closed:
            raise RuntimeError("This sanitization plan has already been closed")
        if not plan.ready:
            raise RuntimeError("Only a Ready sanitization plan can be executed")
        if confirmation_phrase != CONFIRMATION_PHRASE:
            raise ValueError(f"Type exactly: {CONFIRMATION_PHRASE}")

        try:
            return self.backend.execute_sanitization_plan(
                plan.handle,
                plan.target_path,
                plan.capacity_bytes,
                confirmation_phrase,
            )
        finally:
            self.close_plan(plan)

    def close_plan(self, plan: SanitizationPlanHandle | None) -> None:
        if plan is None or plan.closed:
            return
        self.backend.destroy_sanitization_plan(plan.handle)
        plan.closed = True
