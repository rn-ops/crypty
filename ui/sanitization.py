from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SimulatedConfirmationDialog(QDialog):
    def __init__(self, device_name, method, scope):
        super().__init__()
        self.setWindowTitle("Review sanitization request")
        self.setModal(True)
        self.resize(480, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Review sanitization request")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        info = QLabel(
            f"Target: {device_name}\nMethod: {method}\nScope: {scope}\n\n"
            "Execution is disabled in this environment. No device data will be changed."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #c3cbc7; line-height: 1.5;")
        layout.addWidget(info)

        buttons = QHBoxLayout()
        cancel = QPushButton("CANCEL")
        confirm = QPushButton("Submit request")
        confirm.setProperty("class", "primary")
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)

        cancel.clicked.connect(self.reject)
        confirm.clicked.connect(self.accept)


class SanitizationPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._build_ui()
        self.refresh_device_context()

    def refresh_device_context(self):
        device = self.main_window.device_manager.get_selected_device()
        self.selected_device_label.setText(device["name"])
        self.target_details.setText(
            f"{device['capacity']}  |  {device['media_type']}  |  {device['filesystem']}"
        )
        self.target_mount.setText(f"Mounted at {device['mount']}  |  {device['status'].title()}")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 12)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title = QLabel("Sanitization")
        title.setFixedHeight(24)
        title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        title_row.addWidget(title)
        title_row.addStretch(1)
        demo_tag = QLabel("READ-ONLY ENVIRONMENT")
        demo_tag.setFixedHeight(20)
        demo_tag.setAlignment(Qt.AlignCenter)
        demo_tag.setStyleSheet(
            "color: #a7c0b7; border: 1px solid #3a4a48; padding: 2px 7px; "
            "font-size: 10px; letter-spacing: 0.10em;"
        )
        title_row.addWidget(demo_tag)
        layout.addLayout(title_row)

        warning = QLabel(
            "Prepare a sanitization request with an explicit target, scope, and audit trail."
        )
        warning.setStyleSheet(
            "color: #c3cbc7; font-size: 11px; background: transparent; padding: 4px 0;"
        )
        layout.addWidget(warning)

        workspace = QHBoxLayout()
        workspace.setSpacing(12)

        target = QFrame()
        target.setMinimumHeight(142)
        target.setStyleSheet("background: #171c1f; border: none;")
        target_layout = QVBoxLayout(target)
        target_layout.setContentsMargins(18, 18, 18, 18)
        target_layout.setSpacing(10)
        target_title = QLabel("SELECTED EVIDENCE SOURCE")
        target_title.setStyleSheet("color: #9aa5a1; font-size: 10px; letter-spacing: 0.12em;")
        target_layout.addWidget(target_title)
        self.selected_device_label = QLabel("Samsung Portable SSD")
        self.selected_device_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        target_layout.addWidget(self.selected_device_label)
        self.target_details = QLabel("1 TB  |  SSD  |  NTFS")
        self.target_details.setStyleSheet("color: #c3cbc7; font-size: 12px;")
        target_layout.addWidget(self.target_details)
        self.target_mount = QLabel("Mounted at /E:  |  Connected")
        self.target_mount.setStyleSheet("color: #a7c0b7; font-size: 11px;")
        target_layout.addWidget(self.target_mount)
        workspace.addWidget(target, 1)

        plan = QFrame()
        plan.setMinimumHeight(142)
        plan.setStyleSheet("background: #171c1f; border: none;")
        plan_layout = QGridLayout(plan)
        plan_layout.setContentsMargins(18, 18, 18, 18)
        plan_layout.setHorizontalSpacing(12)
        plan_layout.setVerticalSpacing(8)
        plan_title = QLabel("REQUEST PARAMETERS")
        plan_title.setStyleSheet("color: #9aa5a1; font-size: 10px; letter-spacing: 0.12em;")
        plan_layout.addWidget(plan_title, 0, 0, 1, 2)

        method_label = QLabel("Method")
        method_label.setStyleSheet("color: #c3cbc7; font-size: 11px;")
        self.method = QComboBox()
        self.method.addItems(["Device-aware sanitization", "Clear user data", "Prepare for disposal"])
        plan_layout.addWidget(method_label, 1, 0)
        plan_layout.addWidget(self.method, 1, 1)

        scope_label = QLabel("Scope")
        scope_label.setStyleSheet("color: #c3cbc7; font-size: 11px;")
        self.scope = QComboBox()
        self.scope.addItems(["Entire selected device", "User data only"])
        plan_layout.addWidget(scope_label, 2, 0)
        plan_layout.addWidget(self.scope, 2, 1)
        workspace.addWidget(plan, 2)
        layout.addLayout(workspace)

        checks = QFrame()
        checks.setStyleSheet("background: #171c1f; border: none;")
        checks_layout = QHBoxLayout(checks)
        checks_layout.setContentsMargins(14, 9, 14, 9)
        checks_layout.setSpacing(16)
        checks_title = QLabel("REQUIRED CONFIRMATIONS")
        checks_title.setStyleSheet("color: #9aa5a1; font-size: 10px; letter-spacing: 0.12em;")
        checks_layout.addWidget(checks_title)
        self.target_check = QCheckBox("Target confirmed")
        self.target_check.setChecked(True)
        self.scope_check = QCheckBox("Scope confirmed")
        self.scope_check.setChecked(True)
        self.audit_check = QCheckBox("Write audit record")
        self.audit_check.setChecked(True)
        checks_layout.addWidget(self.target_check)
        checks_layout.addWidget(self.scope_check)
        checks_layout.addWidget(self.audit_check)
        checks_layout.addStretch(1)
        layout.addWidget(checks)

        action_row = QHBoxLayout()
        self.action_button = QPushButton("Review request")
        self.action_button.setProperty("class", "primary")
        self.action_button.clicked.connect(self._confirm_sanitization)
        action_row.addWidget(self.action_button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        self.status_label = QLabel("No request submitted")
        self.status_label.setStyleSheet("color: #a7c0b7; font-size: 12px;")
        layout.addWidget(self.status_label)
        layout.addStretch(1)

    def _confirm_sanitization(self):
        if not self.target_check.isChecked() or not self.scope_check.isChecked():
            self.status_label.setText("Confirm the target and scope before reviewing")
            return

        device = self.main_window.device_manager.get_selected_device()
        dialog = SimulatedConfirmationDialog(
            device["name"], self.method.currentText(), self.scope.currentText()
        )
        if dialog.exec() != 1:
            return

        self.action_button.setEnabled(False)
        self.status_label.setText("Authorization check")
        self.progress.setValue(20)
        self._simulate_steps()

    def _simulate_steps(self):
        from PySide6.QtCore import QTimer

        self._steps = [
            (30, "Authorization check"),
            (45, "Target verification"),
            (70, "Request validation"),
            (90, "Verification"),
            (100, "Audit record" if self.audit_check.isChecked() else "Simulation complete"),
        ]
        self._step_index = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_simulation)
        self._timer.start(550)

    def _advance_simulation(self):
        if self._step_index >= len(self._steps):
            self._timer.stop()
            self.action_button.setEnabled(True)
            self.status_label.setText("Request recorded  |  No device changes made")
            self.progress.setValue(100)
            return

        value, message = self._steps[self._step_index]
        self.progress.setValue(value)
        self.status_label.setText(message)
        self._step_index += 1
