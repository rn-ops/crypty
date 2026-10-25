from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIRMATION_PHRASE = "OVERWRITE THIS FILE"

_PLAN_STATUS_NAMES = {
    0: "Ready",
    1: "Unsupported",
    2: "RequiresUserConfirmation",
    3: "Blocked",
}
_EXECUTION_STATUS_NAMES = {
    0: "Not started",
    1: "In progress",
    2: "Completed",
    3: "Failed",
    4: "Cancelled",
}
_VALIDATION_STATUS_NAMES = {
    0: "Not performed",
    1: "Passed",
    2: "Failed",
    3: "Inconclusive",
}


@dataclass
class SanitizationTarget:
    """UI-neutral target descriptor. The backend owns target discovery and validation."""

    kind: str
    target_id: str
    label: str
    selector: str
    path: str = ""
    capacity_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SanitizationPlanHandle:
    """Stable view-model around a backend-owned plan handle."""

    native_handle: int
    target_kind: str
    target_id: str
    target_path: str
    target_label: str
    capacity_bytes: int
    status: str
    status_code: int
    reason: str
    method_id: str
    method_label: str
    assurance_label: str = "Clear"
    steps: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confirmation_phrase: str = CONFIRMATION_PHRASE
    metadata: dict[str, Any] = field(default_factory=dict)
    closed: bool = False

    @property
    def ready(self) -> bool:
        return self.status_code == 0 and not self.closed


class SanitizationEngine:
    """
    Stable application-facing sanitization service.

    The UI talks only to this facade. Native ABI details, plan-handle ownership,
    status-code mapping, capability discovery and future target implementations
    stay here rather than in the Qt page.
    """

    def __init__(self, backend):
        self.backend = backend

    def capabilities(self) -> dict[str, Any]:
        """Return capability descriptors; unavailable future targets stay visible but disabled."""
        provider = getattr(self.backend, "sanitization_capabilities", None)
        if callable(provider):
            supplied = provider()
            if isinstance(supplied, dict) and supplied.get("targets"):
                return supplied

        return {
            "targets": [
                {
                    "kind": "disk_image_file",
                    "label": "Disposable image file",
                    "selector": "file",
                    "enabled": True,
                    "description": (
                        "Overwrite a Crypty-marked disposable image file and verify it by read-back."
                    ),
                },
                {
                    "kind": "physical_device",
                    "label": "Physical device",
                    "selector": "device",
                    "enabled": False,
                    "description": (
                        "Unavailable until mounted-volume, boot-critical-volume and device-safety "
                        "preflight checks are implemented and validated."
                    ),
                },
            ],
            "methods": [
                {
                    "id": "image_file_zero_overwrite",
                    "label": "Zero overwrite + read-back verification",
                    "enabled": True,
                    "assurance": "Clear",
                    "description": "Supported only for eligible disposable image files.",
                }
            ],
            "execution_enabled": True,
            "limitations": [
                "Physical-device sanitization is not enabled.",
                "File overwrite does not establish physical-media sanitization assurance.",
            ],
        }

    def list_targets(self, target_kind: str) -> list[SanitizationTarget]:
        """
        Enumerate selectable targets for a capability.

        Future device backends can implement list_sanitization_targets(kind) without
        changing the UI. The current image-file workflow uses a native file picker.
        """
        provider = getattr(self.backend, "list_sanitization_targets", None)
        if not callable(provider):
            return []
        targets = []
        for item in provider(target_kind) or []:
            targets.append(
                SanitizationTarget(
                    kind=str(item.get("kind", target_kind)),
                    target_id=str(item.get("target_id", item.get("id", ""))),
                    label=str(item.get("label", item.get("name", "Unnamed target"))),
                    selector=str(item.get("selector", "device")),
                    path=str(item.get("path", "")),
                    capacity_bytes=int(item.get("capacity_bytes", 0) or 0),
                    metadata=dict(item.get("metadata", {})),
                )
            )
        return targets

    def plan_target(
        self,
        target: SanitizationTarget,
        method_id: str | None = None,
    ) -> SanitizationPlanHandle:
        """Create a plan for a selected target; no target is modified by planning."""
        if target.kind == "disk_image_file":
            if not target.path:
                raise ValueError("The selected image target has no path")
            raw = self.backend.create_sanitization_plan(target.path)
            return self._wrap_native_plan(
                raw,
                target=target,
                method_id=method_id or "image_file_zero_overwrite",
                method_label="Zero overwrite + read-back verification",
            )

        # Forward-compatible extension point: the frontend already uses this
        # generic method. A future backend may expose a generic plan operation.
        provider = getattr(self.backend, "create_sanitization_plan_for_target", None)
        if callable(provider):
            raw = provider(
                {
                    "kind": target.kind,
                    "target_id": target.target_id,
                    "path": target.path,
                    "capacity_bytes": target.capacity_bytes,
                    "metadata": target.metadata,
                },
                method_id,
            )
            return self._wrap_native_plan(
                raw,
                target=target,
                method_id=method_id or str(raw.get("method_id", "backend_defined")),
                method_label=str(raw.get("method_label", "Backend-defined method")),
            )

        raise RuntimeError(
            f"The backend does not implement planning for target type '{target.kind}'"
        )

    def plan_image_file(self, path: str) -> SanitizationPlanHandle:
        """Compatibility convenience method for the currently supported target."""
        target = SanitizationTarget(
            kind="disk_image_file",
            target_id=str(Path(path).resolve()),
            label=Path(path).name or str(path),
            selector="file",
            path=str(path),
        )
        return self.plan_target(target, "image_file_zero_overwrite")

    def _wrap_native_plan(
        self,
        raw: dict[str, Any],
        target: SanitizationTarget,
        method_id: str,
        method_label: str,
    ) -> SanitizationPlanHandle:
        native_handle = int(raw.get("_handle") or 0)
        if not native_handle:
            raise RuntimeError("The native sanitization planner returned an invalid plan handle")

        status_code = int(raw.get("status", 3))
        status = str(raw.get("status_name") or _PLAN_STATUS_NAMES.get(status_code, "Unknown"))
        target_path = str(raw.get("target_path") or target.path or target.target_id)
        capacity = int(raw.get("capacity_bytes", target.capacity_bytes) or 0)

        supplied_steps = raw.get("steps")
        if supplied_steps:
            steps = [
                item if isinstance(item, dict) else {"description": str(item)}
                for item in supplied_steps
            ]
        elif target.kind == "disk_image_file":
            steps = [
                {"id": "overwrite", "label": "Overwrite file contents with zeroes", "status": "planned"},
                {"id": "verify", "label": "Read back and verify overwritten bytes", "status": "planned"},
            ]
        else:
            steps = []

        warnings = [str(item) for item in raw.get("warnings", [])]
        if target.kind == "disk_image_file":
            warnings.append(
                "This operation does not establish sanitization of physical media, SSD remapped blocks, or snapshots."
            )

        return SanitizationPlanHandle(
            native_handle=native_handle,
            target_kind=str(raw.get("target_kind", target.kind)),
            target_id=str(raw.get("target_id", target.target_id)),
            target_path=target_path,
            target_label=target.label or Path(target_path).name,
            capacity_bytes=capacity,
            status=status,
            status_code=status_code,
            reason=str(raw.get("reason", "")),
            method_id=str(raw.get("method_id", method_id)),
            method_label=str(raw.get("method_label", method_label)),
            assurance_label=str(raw.get("assurance_label", "Clear")),
            steps=steps,
            warnings=list(dict.fromkeys(warnings)),
            confirmation_phrase=str(raw.get("confirmation_phrase", CONFIRMATION_PHRASE)),
            metadata=dict(raw.get("metadata", {})),
        )

    def execute_plan(
        self,
        plan: SanitizationPlanHandle,
        authorization: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a plan with explicit target/path/capacity/phrase authorization.
        The native plan handle is always released after the attempt.
        """
        if plan.closed:
            raise RuntimeError("This sanitization plan has already been closed")
        if not plan.ready:
            raise RuntimeError("Only a Ready sanitization plan can be executed")

        try:
            if plan.target_kind == "disk_image_file":
                result = self.backend.execute_sanitization_plan(
                    plan.native_handle,
                    str(authorization.get("confirmed_target_path", "")),
                    int(authorization.get("confirmed_target_capacity_bytes", 0)),
                    str(authorization.get("confirmation_phrase", "")),
                )
            else:
                provider = getattr(self.backend, "execute_sanitization_plan_for_target", None)
                if not callable(provider):
                    raise RuntimeError(
                        f"The backend does not implement execution for target type '{plan.target_kind}'"
                    )
                result = provider(plan.native_handle, authorization)
            return self._normalize_result(result, plan)
        finally:
            self.close_plan(plan)

    def execute_image_file(
        self,
        plan: SanitizationPlanHandle,
        confirmation_phrase: str,
    ) -> dict[str, Any]:
        """Compatibility wrapper for the previous page contract."""
        return self.execute_plan(
            plan,
            {
                "confirmed": True,
                "confirmed_target_path": plan.target_path,
                "confirmed_target_capacity_bytes": plan.capacity_bytes,
                "confirmation_phrase": confirmation_phrase,
            },
        )

    @staticmethod
    def _normalize_result(raw: dict[str, Any], plan: SanitizationPlanHandle) -> dict[str, Any]:
        execution_code = int(raw.get("execution_status", 2 if raw.get("executed") else 3))
        validation_code = int(raw.get("validation_status", 1 if raw.get("successful") else 0))
        return {
            "operation_id": str(raw.get("operation_id", "")),
            "plan_id": str(raw.get("plan_id", "")),
            "target_kind": str(raw.get("target_kind", plan.target_kind)),
            "target_path": str(raw.get("target_path", plan.target_path)),
            "method_id": str(raw.get("method_id", plan.method_id)),
            "method_label": str(raw.get("method_label", plan.method_label)),
            "execution_status": str(
                raw.get("execution_status_name")
                or _EXECUTION_STATUS_NAMES.get(execution_code, "Unknown")
            ),
            "validation_status": str(
                raw.get("validation_status_name")
                or _VALIDATION_STATUS_NAMES.get(validation_code, "Unknown")
            ),
            "executed": bool(raw.get("executed", False)),
            "successful": bool(raw.get("successful", False)),
            "bytes_processed": int(raw.get("bytes_processed", 0) or 0),
            "target_capacity_bytes": int(raw.get("target_capacity_bytes", plan.capacity_bytes) or 0),
            "started_at_utc": str(raw.get("started_at_utc", "")),
            "completed_at_utc": str(raw.get("completed_at_utc", "")),
            "error_code": str(raw.get("error_code", "")),
            "error_message": str(raw.get("error_message", "")),
            "warnings": [str(item) for item in raw.get("warnings", [])],
            "metadata": dict(raw.get("metadata", {})),
        }

    def close_plan(self, plan: SanitizationPlanHandle | None) -> None:
        if plan is None or plan.closed:
            return
        try:
            self.backend.destroy_sanitization_plan(plan.native_handle)
        finally:
            plan.closed = True

    # Legacy spelling used by some callers.
    def close(self, plan: SanitizationPlanHandle | None) -> None:
        self.close_plan(plan)
