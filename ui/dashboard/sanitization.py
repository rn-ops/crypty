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
            "Destructive operations require a Ready plan and target-specific authorization. "
            "Physical-device sanitization remains disabled unless the backend explicitly advertises and implements it."
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
            self.target_button.setText("Choose device…")
            self.target_button.setEnabled(bool(descriptor.get("enabled")) and not self._busy())
        else:
            self.target_button.setEnabled(False)
        self._target = None
        self.target_path.setText("No target selected")
        self.target_meta.setText("Target size: —")
        self._discard_plan()
        self._update_actions()

    def _on_method_changed(self, *_):
        self._discard_plan()
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
            try:
                targets = self.engine.list_targets(kind)
            except Exception as error:
                self.status_line.setText(f"Unable to enumerate targets: {error}")
                return
            if not targets:
                QMessageBox.information(self, "No targets", "The backend did not report any eligible targets.")
                return
            labels = [f"{item.label} — {self._format_capacity(item.capacity_bytes)}" for item in targets]
            chosen, accepted = QInputDialog.getItem(self, "Select target device", "Target", labels, 0, False)
            if not accepted:
                return
            self._target = targets[labels.index(chosen)]
        else:
            return

        self._discard_plan()
        self.target_path.setText(self._target.path or self._target.label or self._target.target_id)
        self.target_meta.setText(f"Target size: {self._format_capacity(self._target.capacity_bytes)}")
        self.status_line.setText("Target selected. Inspect it to request a backend-generated plan.")
        self.result_view.setPlainText("No operation performed for this target.")
        self._update_actions()

    def _inspect_target(self):
        if self._busy():
            return
        if self._target is None:
            self.status_line.setText("Select a target before building a plan.")
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
        self.status_line.setText("Building a read-only sanitization plan…")
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

        self.execute_button.setEnabled(False)
        self.inspect_button.setEnabled(False)
        self.target_button.setEnabled(False)
        self.target_type.setEnabled(False)
        self.method_combo.setEnabled(False)
        self.clear_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.setFormat("Executing and validating…")
        self.status_line.setText("The backend is executing the authorized plan. Do not disconnect the target.")
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
        if result.get("successful"):
            self.status_line.setText(
                "Backend reports execution and required validation successful. This does not prove physical-media sanitization."
            )
        else:
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

    def _busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def refresh_device_context(self):
        # Intentionally independent of the selected evidence device. Sanitization
        # targets are chosen through sanitization capabilities, never inferred from
        # the globally selected forensic evidence source.
        pass

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
