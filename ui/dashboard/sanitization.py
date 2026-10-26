from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QInputDialog,
    QPushButton,
    QProgressBar,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from auth_client import AuthenticationError

from core.sanitization_engine import (
    CONFIRMATION_PHRASE,
    SanitizationEngine,
    SanitizationPlanHandle,
    SanitizationTarget,
)


class _ExecutionWorker(QThread):
    completed = Signal(dict)
    failed = Signal(str)

    def __init__(self, engine: SanitizationEngine, plan: SanitizationPlanHandle, authorization: dict, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.plan = plan
        self.authorization = authorization

    def run(self):
        try:
            self.completed.emit(self.engine.execute_plan(self.plan, self.authorization))
        except Exception as error:
            self.failed.emit(str(error))


class _AuthorizationDialog(QDialog):
    """Target-specific confirmation, deliberately independent of backend implementation."""

    def __init__(self, plan: SanitizationPlanHandle, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.setWindowTitle("Authorize sanitization")
        self.setModal(True)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("Destructive operation authorization")
        title.setObjectName("workspaceTitle")
        layout.addWidget(title)

        warning = QLabel(
            "Review the exact target and capacity. This operation may permanently destroy data. "
            "Authorization applies only to the plan shown below."
        )
        warning.setWordWrap(True)
        warning.setObjectName("muted")
        layout.addWidget(warning)

        details = QFrame()
        details.setObjectName("inspectionPanel")
        grid = QGridLayout(details)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        for row, (label, value) in enumerate((
            ("Target", plan.target_path),
            ("Capacity", self._format_capacity(plan.capacity_bytes)),
            ("Method", plan.method_label),
            ("Assurance", plan.assurance_label),
        )):
            key = QLabel(label.upper())
            key.setObjectName("panelEyebrow")
            val = QLabel(value)
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(key, row, 0)
            grid.addWidget(val, row, 1)
        layout.addWidget(details)

        self.acknowledge = QCheckBox(
            "I understand this is destructive and have verified the target."
        )
        layout.addWidget(self.acknowledge)

        phrase_label = QLabel(f"Type exactly: {plan.confirmation_phrase}")
        phrase_label.setObjectName("panelEyebrow")
        layout.addWidget(phrase_label)
        self.phrase = QLineEdit()
        self.phrase.setPlaceholderText(plan.confirmation_phrase)
        self.phrase.textChanged.connect(self._update_acceptance)
        self.acknowledge.toggled.connect(self._update_acceptance)
        layout.addWidget(self.phrase)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = QPushButton("Cancel")
        accept = QPushButton("Authorize operation")
        accept.setProperty("class", "danger")
        accept.setEnabled(False)
        cancel.clicked.connect(self.reject)
        accept.clicked.connect(self.accept)
        self._accept_button = accept
        actions.addWidget(cancel)
        actions.addWidget(accept)
        layout.addLayout(actions)
        self._update_acceptance()

    def _update_acceptance(self, *_):
        self._accept_button.setEnabled(
            self.acknowledge.isChecked()
            and self.phrase.text() == self.plan.confirmation_phrase
        )

    @staticmethod
    def _format_capacity(value: int) -> str:
        amount = float(value)
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if amount < 1024 or unit == "TiB":
                return f"{amount:.2f} {unit}"
            amount /= 1024
        return f"{amount:.2f} TiB"

    def authorization(self) -> dict[str, Any]:
        return {
            "confirmed": True,
            "confirmed_target_path": self.plan.target_path,
            "confirmed_target_capacity_bytes": self.plan.capacity_bytes,
            "confirmation_phrase": self.phrase.text(),
        }


class SanitizationPage(QWidget):
    """
    Capability-driven sanitization workspace.

    UI contract: capabilities -> select target -> create plan -> authorize -> execute
    -> display result. Backend-specific types and native handles stay in SanitizationEngine.
    """

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.engine: SanitizationEngine = main_window.sanitization_engine
        self._capabilities: dict[str, Any] = {}
        self._target: SanitizationTarget | None = None
        self._plan: SanitizationPlanHandle | None = None
        self._worker: _ExecutionWorker | None = None
        self._audit_case: dict | None = None
        self._audit_fingerprint: str | None = None
        self._build_ui()
        self._load_capabilities()
        self.refresh_device_context()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 12)
        root.setSpacing(9)

        breadcrumb = QLabel("WORKSPACE  /  SANITIZATION")
        breadcrumb.setObjectName("breadcrumb")
        root.addWidget(breadcrumb)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("Sanitization")
        title.setObjectName("workspaceTitle")
        subtitle = QLabel(
            "Plan, authorize, execute and validate a sanitization operation."
        )
        subtitle.setObjectName("workspaceSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch(1)
        self.mode_badge = QLabel("CAPABILITY-GATED")
        self.mode_badge.setStyleSheet(
            "color: #d5b36a; background: #211e18; border: 1px solid #5b4b31; "
            "padding: 5px 8px; font-size: 10px; letter-spacing: .08em;"
        )
        header.addWidget(self.mode_badge)
        root.addLayout(header)

        self.safety_banner = QLabel()
        self.safety_banner.setWordWrap(True)
        self.safety_banner.setStyleSheet(
            "color: #e6c58b; background: #211e18; border: 1px solid #4a3d2b; "
            "padding: 9px 11px; font-size: 11px;"
        )
        root.addWidget(self.safety_banner)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)

        left = QFrame()
        left.setProperty("class", "section")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        target_heading = QLabel("TARGET & METHOD")
        target_heading.setObjectName("panelEyebrow")
        left_layout.addWidget(target_heading)

        left_layout.addWidget(self._key_label("Target type"))
        self.target_type = QComboBox()
        self.target_type.currentIndexChanged.connect(self._on_target_kind_changed)
        left_layout.addWidget(self.target_type)

        self.target_description = QLabel("Loading backend capabilities…")
        self.target_description.setWordWrap(True)
        self.target_description.setObjectName("muted")
        left_layout.addWidget(self.target_description)

        left_layout.addWidget(self._key_label("Method"))
        self.method_combo = QComboBox()
        self.method_combo.currentIndexChanged.connect(self._on_method_changed)
        left_layout.addWidget(self.method_combo)

        self.target_button = QPushButton("Choose image file…")
        self.target_button.setProperty("class", "secondary")
        self.target_button.clicked.connect(self._choose_target)
        left_layout.addWidget(self.target_button)

        self.refresh_physical_button = QPushButton("Refresh physical devices")
        self.refresh_physical_button.setProperty("class", "secondary")
        self.refresh_physical_button.clicked.connect(self._refresh_physical_devices)
        self.refresh_physical_button.setVisible(False)
        left_layout.addWidget(self.refresh_physical_button)

        self.physical_device_combo = QComboBox()
        self.physical_device_combo.setVisible(False)
        self.physical_device_combo.currentIndexChanged.connect(self._on_physical_device_selected)
        left_layout.addWidget(self.physical_device_combo)

        self.physical_device_status = QLabel("Physical-device inventory has not been refreshed.")
        self.physical_device_status.setWordWrap(True)
        self.physical_device_status.setObjectName("muted")
        self.physical_device_status.setVisible(False)
        left_layout.addWidget(self.physical_device_status)

        self.selected_device_button = QPushButton("Use selected Evidence device")
        self.selected_device_button.setProperty("class", "secondary")
        self.selected_device_button.setToolTip(
            "Load the globally selected sidebar/Evidence volume for review. "
            "This does not select or authorize its underlying physical disk for erasure."
        )
        self.selected_device_button.clicked.connect(self._use_selected_evidence_device)
        left_layout.addWidget(self.selected_device_button)

        self.selected_device_context = QLabel("Evidence selection: none")
        self.selected_device_context.setWordWrap(True)
        self.selected_device_context.setObjectName("muted")
        left_layout.addWidget(self.selected_device_context)

        self.target_path = QLabel("No target selected")
        self.target_path.setWordWrap(True)
        self.target_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.target_path.setObjectName("metadataValue")
        left_layout.addWidget(self.target_path)

        self.target_meta = QLabel("Target size: —")
        self.target_meta.setObjectName("muted")
        left_layout.addWidget(self.target_meta)

        self.inspect_button = QPushButton("Inspect & build plan")
        self.inspect_button.setProperty("class", "primary")
        self.inspect_button.clicked.connect(self._inspect_target)
        left_layout.addWidget(self.inspect_button)

        left_layout.addSpacing(6)
        checks_heading = QLabel("EXECUTION GUARDRAILS")
        checks_heading.setObjectName("panelEyebrow")
        left_layout.addWidget(checks_heading)
        self.guardrail_text = QTextEdit()
        self.guardrail_text.setReadOnly(True)
        self.guardrail_text.setMaximumHeight(120)
        self.guardrail_text.setObjectName("detailText")
        left_layout.addWidget(self.guardrail_text, 1)
        splitter.addWidget(left)

        right = QFrame()
        right.setProperty("class", "section")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)

        plan_header = QHBoxLayout()
        plan_title = QLabel("PLAN INSPECTOR")
        plan_title.setObjectName("panelEyebrow")
        plan_header.addWidget(plan_title)
        plan_header.addStretch(1)
        self.plan_badge = QLabel("NO PLAN")
        self.plan_badge.setStyleSheet(
            "color: #9aa5a1; border: 1px solid #34434a; padding: 3px 7px; font-size: 10px;"
        )
        plan_header.addWidget(self.plan_badge)
        right_layout.addLayout(plan_header)

        self.plan_target = QLabel("Select a target and inspect it to create a plan.")
        self.plan_target.setWordWrap(True)
        self.plan_target.setObjectName("previewName")
        right_layout.addWidget(self.plan_target)

        self.plan_summary = QLabel("No plan available")
        self.plan_summary.setWordWrap(True)
        self.plan_summary.setObjectName("muted")
        right_layout.addWidget(self.plan_summary)

        steps_heading = QLabel("PLANNED STEPS")
        steps_heading.setObjectName("panelEyebrow")
        right_layout.addWidget(steps_heading)
        self.steps_view = QTextEdit()
        self.steps_view.setReadOnly(True)
        self.steps_view.setObjectName("detailText")
        self.steps_view.setMinimumHeight(110)
        right_layout.addWidget(self.steps_view, 1)

        warnings_heading = QLabel("WARNINGS / BLOCKERS")
        warnings_heading.setObjectName("panelEyebrow")
        right_layout.addWidget(warnings_heading)
        self.warnings_view = QTextEdit()
        self.warnings_view.setReadOnly(True)
        self.warnings_view.setObjectName("detailText")
        self.warnings_view.setMaximumHeight(92)
        right_layout.addWidget(self.warnings_view)

        result_heading = QLabel("EXECUTION RESULT")
        result_heading.setObjectName("panelEyebrow")
        right_layout.addWidget(result_heading)
        self.result_view = QTextEdit()
        self.result_view.setReadOnly(True)
        self.result_view.setObjectName("detailText")
        self.result_view.setMaximumHeight(110)
        self.result_view.setPlainText("No operation performed.")
        right_layout.addWidget(self.result_view)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Idle")
        right_layout.addWidget(self.progress)

        action_row = QHBoxLayout()
        self.clear_button = QPushButton("Clear plan")
        self.clear_button.clicked.connect(self._clear_plan)
        action_row.addWidget(self.clear_button)
        action_row.addStretch(1)
        self.execute_button = QPushButton("Authorize & execute")
        self.execute_button.setProperty("class", "danger")
        self.execute_button.setEnabled(False)
        self.execute_button.clicked.connect(self._authorize_and_execute)
        action_row.addWidget(self.execute_button)
        right_layout.addLayout(action_row)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([360, 650])
        root.addWidget(splitter, 1)

        self.status_line = QLabel("Ready. No sanitization operation has been performed.")
        self.status_line.setObjectName("statusLine")
        self.status_line.setWordWrap(True)
        root.addWidget(self.status_line)

    @staticmethod
    def _key_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("metadataKey")
        return label

    def _load_capabilities(self):
        try:
            self._capabilities = self.engine.capabilities()
        except Exception as error:
            self._capabilities = {"targets": [], "methods": [], "limitations": []}
            self.status_line.setText(f"Unable to load sanitization capabilities: {error}")

        targets = self._capabilities.get("targets", [])
        self.target_type.blockSignals(True)
        self.target_type.clear()
        for descriptor in targets:
            label = descriptor.get("label", descriptor.get("kind", "Target"))
            if not descriptor.get("enabled", False):
                label = f"{label} — unavailable"
            self.target_type.addItem(label, descriptor)
            index = self.target_type.count() - 1
            item = self.target_type.model().item(index) if hasattr(self.target_type.model(), "item") else None
            if item is not None and not descriptor.get("enabled", False):
                item.setEnabled(False)
        self.target_type.blockSignals(False)

        methods = self._capabilities.get("methods", [])
        self.method_combo.blockSignals(True)
        self.method_combo.clear()
        for descriptor in methods:
            label = descriptor.get("label", descriptor.get("id", "Method"))
            if not descriptor.get("enabled", False):
                label = f"{label} — unavailable"
            self.method_combo.addItem(label, descriptor)
            item = self.method_combo.model().item(self.method_combo.count() - 1) if hasattr(self.method_combo.model(), "item") else None
            if item is not None and not descriptor.get("enabled", False):
                item.setEnabled(False)
        self.method_combo.blockSignals(False)

        limitations = self._capabilities.get("limitations", [])
        self.guardrail_text.setPlainText("\n".join(f"• {item}" for item in limitations) or "No additional limitations reported.")
        self.safety_banner.setText(
            "Destructive operations require a Ready native plan and target-specific authorization. "
            "Physical-device plans are refreshed against whole-device identity and remain blocked when protection checks are incomplete."
        )
        self._on_target_kind_changed()
        self._on_method_changed()

    def _selected_descriptor(self, combo: QComboBox) -> dict[str, Any]:
        value = combo.currentData()
        return value if isinstance(value, dict) else {}

    def _on_target_kind_changed(self, *_):
        descriptor = self._selected_descriptor(self.target_type)
        self.target_description.setText(str(descriptor.get("description", "No target capability selected.")))
        selector = descriptor.get("selector", "")
        if selector == "file":
            self.target_button.setText("Choose image file…")
            self.target_button.setEnabled(bool(descriptor.get("enabled")) and not self._busy())
        elif selector == "device":
            self.target_button.setText("Choose physical device…")
            self.target_button.setEnabled(bool(descriptor.get("enabled")) and not self._busy())
        else:
            self.target_button.setEnabled(False)
        if hasattr(self, "refresh_physical_button"):
            self.refresh_physical_button.setVisible(selector == "device")
            self.refresh_physical_button.setEnabled(selector == "device" and not self._busy())
        if hasattr(self, "physical_device_combo"):
            self.physical_device_combo.setVisible(selector == "device")
            self.physical_device_status.setVisible(selector == "device")
        # Keep the method selector aligned with the selected target type. A physical
        # device must never accidentally retain the image-file-only method.
        desired_method = (
            "physical_device_zero_overwrite" if descriptor.get("kind") == "physical_device"
            else "image_file_zero_overwrite"
        )
        for method_index in range(self.method_combo.count()):
            method = self.method_combo.itemData(method_index)
            if isinstance(method, dict) and method.get("id") == desired_method:
                self.method_combo.blockSignals(True)
                self.method_combo.setCurrentIndex(method_index)
                self.method_combo.blockSignals(False)
                break
        self._target = None
        self.target_path.setText("No target selected")
        self.target_meta.setText("Target size: —")
        self._discard_plan()
        self._update_actions()

    def _on_method_changed(self, *_):
        self._discard_plan()
        self._update_actions()

    def _refresh_physical_devices(self):
        """Refresh and render whole-device inventory with per-device protection state."""
        if self._busy():
            return
        try:
            targets = self.engine.list_targets("physical_device")
        except Exception as error:
            self.physical_device_combo.clear()
            self.physical_device_status.setText(f"Physical-device refresh failed: {error}")
            self.status_line.setText(f"Physical-device refresh failed: {error}")
            QMessageBox.warning(self, "Device refresh failed", str(error))
            return

        self._discard_plan()
        self._target = None
        self.target_path.setText("No target selected")
        self.target_meta.setText("Target size: —")
        # Keep native Python objects outside Qt item data. PySide/Qt item-data
        # conversion should not determine whether a physical target is usable.
        self._physical_targets = list(targets)

        self.physical_device_combo.blockSignals(True)
        self.physical_device_combo.clear()

        for target in self._physical_targets:
            meta = target.metadata if isinstance(target.metadata, dict) else {}
            model = str(meta.get("model") or target.label)
            path = str(meta.get("path") or target.path)
            capacity = self._format_capacity(target.capacity_bytes)
            complete = bool(meta.get("protection_discovery_complete", False))
            reason = str(meta.get("block_reason") or "")
            state = (
                "protection checks complete"
                if complete
                else "PROTECTION CHECKS INCOMPLETE"
            )
            label = f"{model} · {capacity} · {path} · {state}"
            if reason:
                label += f" · {reason}"

            # Store only text in Qt; retain the target in _physical_targets.
            self.physical_device_combo.addItem(label)

        self.physical_device_combo.blockSignals(False)

        if targets:
            self.physical_device_status.setText(
                f"{len(targets)} physical device(s) found. Select the exact whole disk. "
                "Incomplete protection discovery means the native plan must remain blocked."
            )
            self.physical_device_combo.setCurrentIndex(0)
            self._on_physical_device_selected(0)
        else:
            self.physical_device_status.setText(
                "No physical devices returned by the native inventory. Run Crypty elevated "
                "if raw-device access is required; no device has been opened for writing."
            )
            self.status_line.setText("Physical-device inventory is empty. No operation performed.")
        self.result_view.setPlainText("No operation performed.")
        self._update_actions()

    def _on_physical_device_selected(self, index: int):
        if self._busy() or index < 0:
            return

        targets = getattr(self, "_physical_targets", [])
        if index >= len(targets):
            self.physical_device_status.setText(
                "The selected entry has no matching native target. Refresh inventory."
            )
            return

        target = targets[index]
        if not isinstance(target, SanitizationTarget):
            self.physical_device_status.setText(
                f"Unexpected native target type: {type(target).__name__}"
            )
            return

        self._discard_plan()
        self._target = target
        self.target_path.setText(target.path or target.label or target.target_id)
        self.target_meta.setText(
            f"Whole-device capacity: {self._format_capacity(target.capacity_bytes)}"
        )

        meta = target.metadata if isinstance(target.metadata, dict) else {}
        complete = bool(meta.get("protection_discovery_complete", False))
        reason = str(
            meta.get("block_reason") or "No specific blocker supplied by inventory."
        )

        self.physical_device_status.setText(
            f"Selected: {meta.get('model') or target.label}\n"
            f"Stable identity: {target.target_id}\n"
            f"Protection discovery: {'COMPLETE' if complete else 'INCOMPLETE'}\n"
            f"Inventory reason: {reason}"
        )
        self.status_line.setText(
            "Physical device selected. Inspect it to request a fresh native plan."
        )
        self._update_actions()

    def _choose_target(self):
        if self._busy():
            return
        descriptor = self._selected_descriptor(self.target_type)
        if not descriptor or not descriptor.get("enabled"):
            return
        kind = str(descriptor.get("kind", ""))

        if descriptor.get("selector") == "file":
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select a Crypty disposable image file",
                "",
                "Disk image files (*.img *.dd *.raw *.bin);;All files (*)",
            )
            if not path:
                return
            from pathlib import Path
            self._target = SanitizationTarget(
                kind=kind,
                target_id=str(Path(path).resolve()),
                label=Path(path).name,
                selector="file",
                path=str(Path(path).resolve()),
            )
        elif descriptor.get("selector") == "device":
            # The physical-device dropdown is the source of selection.
            # _on_physical_device_selected() sets self._target.
            target = self._target

            if target is None or target.kind != kind:
                index = self.physical_device_combo.currentIndex()
                targets = getattr(self, "_physical_targets", [])

                if index < 0 or index >= len(targets):
                    self.status_line.setText(
                        f"Selection diagnostic: combo_count="
                        f"{self.physical_device_combo.count()}, "
                        f"combo_index={index}, "
                        f"cached_targets={len(targets)}, "
                        f"current_target_type="
                        f"{type(self._target).__name__}"
                    )
                    return

                target = targets[index]

            self._target = target

        self._discard_plan()
        self.target_path.setText(self._target.path or self._target.label or self._target.target_id)
        self.target_meta.setText(f"Target size: {self._format_capacity(self._target.capacity_bytes)}")
        self.status_line.setText("Target selected. Inspect it to request a backend-generated plan.")
        self.result_view.setPlainText("No operation performed for this target.")
        self._update_actions()

    def _use_selected_evidence_device(self):
        """Load the shared sidebar/Evidence selection as a read-only candidate.

        Evidence selections are mounted-volume paths, not proven physical-disk
        identities. This path intentionally never creates an executable plan.
        """
        if self._busy():
            return
        device = self.main_window.device_manager.get_selected_device()
        if not isinstance(device, dict) or not device.get("path"):
            QMessageBox.information(
                self,
                "No evidence device selected",
                "Select a mounted device in the sidebar or Evidence page first.",
            )
            return

        self._discard_plan()
        self._target = SanitizationTarget(
            kind="mounted_volume_inspection",
            target_id=str(device.get("path", "")),
            label=str(device.get("name", "Selected evidence volume")),
            selector="device",
            path=str(device.get("path", "")),
            capacity_bytes=int(device.get("capacity_bytes", 0) or 0),
            metadata=dict(device),
        )
        self.target_path.setText(
            f"{self._target.label}\n{self._target.path}"
        )
        capacity = self._target.capacity_bytes
        if capacity <= 0:
            capacity_text = str(device.get("capacity", "Unknown capacity"))
        else:
            capacity_text = self._format_capacity(capacity)
        self.target_meta.setText(f"Mounted evidence volume: {capacity_text}")
        self.target_description.setText(
            "Evidence selection is a mounted volume, not a verified whole physical disk. "
            "To sanitize a USB, switch Target type to Physical USB / storage device and select "
            "the exact whole disk from the refreshed native inventory."
        )
        self.plan_badge.setText("INSPECTION ONLY")
        self.plan_badge.setStyleSheet(self._badge_style(False))
        self.plan_target.setText(f"{self._target.label} — candidate")
        self.plan_summary.setText(
            "No sanitization plan was created. This is the globally selected evidence volume, "
            "not a verified physical-device target."
        )
        self.steps_view.setPlainText(
            "1. Read selected volume metadata [not performed here]\n"
            "2. Mounted-volume to physical-disk mapping is not inferred from this selection\n"
            "3. For a physical target, use the dedicated whole-device selector and native planner\n"
            "4. Destructive execution [DISABLED for this mounted-volume candidate]"
        )
        self.warnings_view.setPlainText(
            "BLOCKER: The selected evidence path does not establish the underlying physical disk.\n"
            "BLOCKER: This candidate is a mounted volume, not a verified whole physical disk.\n"
            "BLOCKER: Select the physical-device target type to request native inventory and preflight."
        )
        self.execute_button.setEnabled(False)
        self.result_view.setPlainText("No operation performed. Candidate selected; execution is not available from this selection.")
        self.status_line.setText(
            "Shared Evidence selection loaded. No device was opened for writing; execution remains disabled."
        )
        self._update_actions()

    def _inspect_target(self):
        if self._busy():
            return
        if self._target is None:
            self.status_line.setText("Select a target before building a plan.")
            return
        if self._target.kind == "mounted_volume_inspection":
            self.status_line.setText(
                "This mounted-volume candidate is inspection-only. Switch Target type to "
                "Physical USB / storage device, refresh inventory, and select the whole disk."
            )
            self.execute_button.setEnabled(False)
            return
        method = self._selected_descriptor(self.method_combo)
        if not method or not method.get("enabled", False):
            self.status_line.setText("No enabled sanitization method is available for this target.")
            return

        self._discard_plan()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Inspecting target…")
        self.inspect_button.setEnabled(False)
        self.status_line.setText("Building a sanitization plan…")
        try:
            self._plan = self.engine.plan_target(self._target, str(method.get("id", "")))
        except Exception as error:
            self.plan_badge.setText("ERROR")
            self.plan_summary.setText("The backend could not create a plan.")
            self.warnings_view.setPlainText(str(error))
            self.status_line.setText(f"Plan creation failed: {error}")
        else:
            self._render_plan(self._plan)
            if self._plan.ready:
                self.status_line.setText("Plan ready. No target data has been changed.")
            else:
                self.status_line.setText("Plan blocked. No target data has been changed.")
        finally:
            self.inspect_button.setEnabled(True)
            self.progress.setFormat("Idle")
            self._update_actions()

    def _render_plan(self, plan: SanitizationPlanHandle):
        self.plan_badge.setText(plan.status.upper())
        self.plan_badge.setStyleSheet(self._badge_style(plan.ready))
        self.plan_target.setText(plan.target_path or plan.target_label)
        self.plan_summary.setText(
            f"Status: {plan.status}    |    Capacity: {self._format_capacity(plan.capacity_bytes)}\n"
            f"Method: {plan.method_label}    |    Assurance: {plan.assurance_label}\n"
            f"{plan.reason}"
        )
        steps = []
        for index, step in enumerate(plan.steps, start=1):
            label = str(step.get("label", step.get("description", step.get("id", "Backend step"))))
            status = str(step.get("status", "planned"))
            steps.append(f"{index:02d}  {label}  [{status}]")
        self.steps_view.setPlainText("\n".join(steps) or "The backend did not provide a step breakdown.")
        warnings = list(plan.warnings)
        if not plan.ready and plan.reason:
            warnings.insert(0, f"BLOCKER: {plan.reason}")
        self.warnings_view.setPlainText("\n".join(f"• {item}" for item in warnings) or "No warnings reported by the backend.")
        self.execute_button.setEnabled(plan.ready and not self._busy())

    def _authorize_and_execute(self):
        plan = self._plan
        if plan is None or not plan.ready or self._busy():
            return
        dialog = _AuthorizationDialog(plan, self)
        if dialog.exec() != QDialog.Accepted:
            self.status_line.setText("Authorization cancelled. No target data was changed.")
            return

        try:
            fingerprint = self.main_window.auth_client.device_fingerprint({
                "stable_id": self._target.target_id if self._target else "",
                "path": self._target.path if self._target else "",
            })
            audit_case = self.main_window.active_case
            if audit_case and fingerprint not in {
                source.get("identity") for source in audit_case.get("devices", [])
            }:
                audit_case = None
            self.main_window.record_audit_event(
                "SANITIZATION_STARTED",
                f"Started {plan.method_id} for {plan.target_kind} target '{plan.target_label}'.",
                case=audit_case,
                device_fingerprint=fingerprint,
            )
        except (AuthenticationError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Sanitization blocked",
                f"The audit event could not be saved, so the operation was not started:\n{error}",
            )
            return
        self._audit_case = audit_case
        self._audit_fingerprint = fingerprint

        self.execute_button.setEnabled(False)
        self.inspect_button.setEnabled(False)
        self.target_button.setEnabled(False)
        self.target_type.setEnabled(False)
        self.method_combo.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.setFormat("Executing (native byte progress unavailable)…")
        self.status_line.setText("The backend is executing the authorized plan. Byte-level progress is not exposed by the current native API. Do not disconnect the target.")
        self._worker = _ExecutionWorker(self.engine, plan, dialog.authorization(), self)
        self._worker.completed.connect(self._on_execution_completed)
        self._worker.failed.connect(self._on_execution_failed)
        self._worker.finished.connect(self._on_worker_stopped)
        self._worker.start()

    def _on_execution_completed(self, result: dict[str, Any]):
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if result.get("successful") else 0)
        self.progress.setFormat("Completed" if result.get("successful") else "Finished with errors")
        lines = [
            f"Outcome: {'SUCCESS' if result.get('successful') else 'NOT SUCCESSFUL'}",
            f"Execution: {result.get('execution_status', 'Unknown')}",
            f"Validation: {result.get('validation_status', 'Unknown')}",
            f"Bytes processed: {int(result.get('bytes_processed', 0)):,}",
            f"Target: {result.get('target_path') or (self._target.path if self._target else '')}",
        ]
        if result.get("operation_id"):
            lines.append(f"Operation ID: {result['operation_id']}")
        if result.get("started_at_utc"):
            lines.append(f"Started (UTC): {result['started_at_utc']}")
        if result.get("completed_at_utc"):
            lines.append(f"Completed (UTC): {result['completed_at_utc']}")
        if result.get("error_code"):
            lines.append(f"Error code: {result['error_code']}")
        if result.get("error_message"):
            lines.append(f"Error: {result['error_message']}")
        lines.extend(f"Warning: {item}" for item in result.get("warnings", []))
        self.result_view.setPlainText("\n".join(lines))
        try:
            self.main_window.record_audit_event(
                "SANITIZATION_COMPLETED" if result.get("successful") else "SANITIZATION_FAILED",
                f"Sanitization execution {result.get('execution_status', 'unknown')}; "
                f"validation {result.get('validation_status', 'unknown')}.",
                case=self._audit_case,
                device_fingerprint=self._audit_fingerprint,
            )
        except AuthenticationError as error:
            lines.append(f"Audit result update failed: {error}")
            self.result_view.setPlainText("\n".join(lines))
            self.status_line.setText(
                "Execution finished, but its result could not be appended to the audit log: "
                f"{error}"
            )
        if result.get("successful"):
            if "Audit result update failed:" not in self.result_view.toPlainText():
                self.status_line.setText(
                    "Backend reports execution and required validation successful. This does not prove physical-media sanitization."
                )
        else:
            if "Audit result update failed:" not in self.result_view.toPlainText():
                self.status_line.setText(
                    "The backend did not report full success. Review the execution and validation result; do not retry blindly."
                )
        self._plan = None
        self.plan_badge.setText("CONSUMED")
        self.plan_badge.setStyleSheet(self._badge_style(False))
        self.plan_summary.setText("The plan handle was consumed by the execution attempt. Inspect again before another operation.")
        self.execute_button.setEnabled(False)

    def _on_execution_failed(self, message: str):
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Failed")
        self.result_view.setPlainText(f"Execution call failed before a result was returned.\n{message}")
        self.status_line.setText("Execution failed. The plan has been closed; inspect the target again before any retry.")
        try:
            self.main_window.record_audit_event(
                "SANITIZATION_FAILED",
                f"Sanitization execution failed: {message}",
                case=self._audit_case,
                device_fingerprint=self._audit_fingerprint,
            )
        except AuthenticationError as error:
            self.status_line.setText(
                f"Execution failed and the failure could not be appended to the audit log: {error}"
            )
        self._plan = None
        self.execute_button.setEnabled(False)

    def _on_worker_stopped(self):
        self.target_type.setEnabled(True)
        self.method_combo.setEnabled(True)
        self.inspect_button.setEnabled(True)
        self.clear_button.setEnabled(True)
        descriptor = self._selected_descriptor(self.target_type)
        self.target_button.setEnabled(bool(descriptor.get("enabled")) and not self._busy())
        self._worker = None
        self._update_actions()

    def _clear_plan(self):
        if self._busy():
            return
        self._discard_plan()
        self.plan_badge.setText("NO PLAN")
        self.plan_badge.setStyleSheet(self._badge_style(False))
        self.plan_target.setText("Select a target and inspect it to create a plan.")
        self.plan_summary.setText("No plan available")
        self.steps_view.clear()
        self.warnings_view.clear()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Idle")
        self.status_line.setText("Plan cleared. No target data was changed.")
        self._update_actions()

    def _discard_plan(self):
        if self._plan is not None:
            try:
                self.engine.close_plan(self._plan)
            except Exception:
                pass
        self._plan = None
        self.execute_button.setEnabled(False)

    def _update_actions(self):
        busy = self._busy()
        descriptor = self._selected_descriptor(self.target_type)
        method = self._selected_descriptor(self.method_combo)
        self.target_type.setEnabled(not busy)
        self.method_combo.setEnabled(not busy)
        self.inspect_button.setEnabled(
            not busy and self._target is not None and bool(method.get("enabled", False))
        )
        self.clear_button.setEnabled(not busy and self._plan is not None)
        self.execute_button.setEnabled(
            not busy and self._plan is not None and self._plan.ready
        )
        self.target_button.setEnabled(
            not busy and bool(descriptor.get("enabled", False))
        )
        if hasattr(self, "refresh_physical_button"):
            self.refresh_physical_button.setEnabled(
                not busy and descriptor.get("selector") == "device"
            )
        if hasattr(self, "selected_device_button"):
            self.selected_device_button.setEnabled(
                not busy and self.main_window.device_manager.get_selected_device() is not None
            )

    def _busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def refresh_device_context(self):
        # Reflect the shared sidebar/Evidence selection, but never treat a mounted
        # volume path as authorization to erase its underlying physical device.
        device = self.main_window.device_manager.get_selected_device()
        if not isinstance(device, dict):
            self.selected_device_context.setText("Evidence selection: none")
            self.selected_device_button.setEnabled(not self._busy())
            return
        name = str(device.get("name", "Selected evidence volume"))
        path = str(device.get("path", "Unknown path"))
        capacity = str(device.get("capacity", "Unknown capacity"))
        self.selected_device_context.setText(
            f"Evidence selection: {name} | {capacity}\n{path}"
        )
        self.selected_device_button.setEnabled(not self._busy())
        # If the shared selection changes after loading a candidate, discard it so
        # the page cannot continue showing a stale target.
        if (
            self._target is not None
            and self._target.kind == "mounted_volume_inspection"
            and self._target.path != path
        ):
            self._discard_plan()
            self._target = None
            self.target_path.setText("No target selected")
            self.target_meta.setText("Target size: —")
            self.plan_badge.setText("NO PLAN")
            self.plan_target.setText("Select a target and inspect it to create a plan.")
            self.plan_summary.setText("Evidence selection changed; previous candidate cleared.")
            self.steps_view.clear()
            self.warnings_view.clear()
            self.status_line.setText(
                "Evidence selection changed. Load the current selection again if needed."
            )
        self._update_actions()

    def closeEvent(self, event):
        if self._busy():
            QMessageBox.information(
                self,
                "Sanitization in progress",
                "Wait for the active sanitization attempt to finish before closing Crypty.",
            )
            event.ignore()
            return
        self._discard_plan()
        super().closeEvent(event)

    @staticmethod
    def _format_capacity(value: int) -> str:
        if value <= 0:
            return "Unknown size"
        amount = float(value)
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if amount < 1024 or unit == "TiB":
                return f"{amount:.2f} {unit}"
            amount /= 1024
        return f"{amount:.2f} TiB"

    @staticmethod
    def _badge_style(ready: bool) -> str:
        if ready:
            return "color: #a8d9d3; background: #1e2d2a; border: 1px solid #334642; padding: 3px 7px; font-size: 10px;"
        return "color: #e6c58b; background: #211e18; border: 1px solid #5b4b31; padding: 3px 7px; font-size: 10px;"
