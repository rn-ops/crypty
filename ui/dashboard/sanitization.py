from __future__ import annotations

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QInputDialog,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.sanitization_engine import (
    CONFIRMATION_PHRASE,
    SanitizationEngine,
    SanitizationPlanHandle,
)


class _SanitizationWorker(QThread):
    finished_result = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        engine: SanitizationEngine,
        plan: SanitizationPlanHandle,
        confirmation_phrase: str,
        parent=None,
    ):
        super().__init__(parent)
        self.engine = engine
        self.plan = plan
        self.confirmation_phrase = confirmation_phrase

    def run(self):
        try:
            self.finished_result.emit(
                self.engine.execute_image_file(self.plan, self.confirmation_phrase)
            )
        except Exception as error:
            self.failed.emit(str(error))


class SanitizationPage(QWidget):
    """Real file-backed sanitization workflow; physical devices remain disabled."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.engine: SanitizationEngine = main_window.sanitization_engine
        self._plan: SanitizationPlanHandle | None = None
        self._worker: _SanitizationWorker | None = None
        self._build_ui()
        self.refresh_device_context()

    def refresh_device_context(self):
        # The selected physical device is intentionally not used as a target.
        if self._plan is None:
            self.status_label.setText(
                "Physical-device sanitization is disabled. Select a Crypty-marked disposable image file."
            )

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 16)
        layout.setSpacing(12)

        title_row = QHBoxLayout()
        title = QLabel("Sanitization")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        title_row.addWidget(title)
        title_row.addStretch(1)
        tag = QLabel("DISPOSABLE IMAGE FILES ONLY")
        tag.setStyleSheet(
            "color: #e6c58b; border: 1px solid #5b4b31; padding: 4px 8px; "
            "font-size: 10px; letter-spacing: 0.08em;"
        )
        title_row.addWidget(tag)
        layout.addLayout(title_row)

        warning = QLabel(
            "This workflow can overwrite a Crypty-marked disposable image file. "
            "It does not sanitize physical drives, SSDs, USB devices, or mounted volumes. "
            "Overwriting is destructive and cannot be undone."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "color: #e6c58b; background: #211e18; padding: 10px; font-size: 12px;"
        )
        layout.addWidget(warning)

        target = QFrame()
        target.setStyleSheet("background: #171c1f; border: none;")
        target_layout = QVBoxLayout(target)
        target_layout.setContentsMargins(18, 16, 18, 16)
        target_layout.setSpacing(8)

        target_heading = QLabel("PLANNED FILE TARGET")
        target_heading.setStyleSheet(
            "color: #9aa5a1; font-size: 10px; letter-spacing: 0.12em;"
        )
        target_layout.addWidget(target_heading)

        self.target_path_label = QLabel("No image file selected")
        self.target_path_label.setWordWrap(True)
        self.target_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.target_path_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        target_layout.addWidget(self.target_path_label)

        self.plan_details_label = QLabel(
            "Choose a file that was prepared as a Crypty disposable image."
        )
        self.plan_details_label.setWordWrap(True)
        self.plan_details_label.setStyleSheet("color: #9aa5a1; font-size: 11px;")
        target_layout.addWidget(self.plan_details_label)
        layout.addWidget(target)

        actions = QHBoxLayout()
        self.select_button = QPushButton("Select image and inspect")
        self.select_button.setProperty("class", "primary")
        self.select_button.clicked.connect(self._select_image)
        actions.addWidget(self.select_button)

        self.execute_button = QPushButton("Execute zero-overwrite")
        self.execute_button.setEnabled(False)
        self.execute_button.clicked.connect(self._confirm_and_execute)
        actions.addWidget(self.execute_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        self.status_label = QLabel("No sanitization operation performed")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #a7c0b7; font-size: 12px;")
        layout.addWidget(self.status_label)
        layout.addStretch(1)

    def _release_current_plan(self):
        if self._plan is not None and not self._plan.closed:
            self.engine.close_plan(self._plan)
        self._plan = None

    def _select_image(self):
        if self._worker is not None and self._worker.isRunning():
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a Crypty disposable image file",
            "",
            "Disk image files (*.img *.dd *.raw *.bin);;All files (*)",
        )
        if not path:
            return

        self._release_current_plan()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.target_path_label.setText(path)
        self.status_label.setText("Inspecting selected file read-only…")
        self.execute_button.setEnabled(False)

        try:
            plan = self.engine.plan_image_file(path)
        except Exception as error:
            self.plan_details_label.setText(str(error))
            self.status_label.setText("Could not create a sanitization plan")
            return

        self._plan = plan
        if plan.capacity_bytes:
            size = self._format_capacity(plan.capacity_bytes)
        else:
            size = "Unknown size"
        self.plan_details_label.setText(
            f"Plan status: {plan.status}  |  Size: {size}\n{plan.reason}"
        )

        if plan.ready:
            self.execute_button.setEnabled(True)
            self.status_label.setText(
                "Plan ready. No file data has been changed. Review the target before execution."
            )
        else:
            self.status_label.setText(
                "Execution blocked. The target was not modified."
            )

    def _confirm_and_execute(self):
        plan = self._plan
        if plan is None or not plan.ready:
            self.status_label.setText("There is no Ready sanitization plan to execute")
            return

        answer = QMessageBox.warning(
            self,
            "Irreversible file overwrite",
            "This will overwrite every byte of the selected file with zeroes.\n\n"
            f"Target: {plan.target_path}\n"
            f"Size: {self._format_capacity(plan.capacity_bytes)}\n\n"
            "Continue only if this is a disposable test image. This operation does not "
            "establish physical-media sanitization assurance.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if answer != QMessageBox.Yes:
            return

        phrase, accepted = QInputDialog.getText(
            self,
            "Confirm destructive operation",
            f"Type exactly: {CONFIRMATION_PHRASE}",
            QLineEdit.Normal,
        )
        if not accepted:
            return
        if phrase != CONFIRMATION_PHRASE:
            self.status_label.setText("Confirmation phrase did not match; no data was changed")
            return

        self.select_button.setEnabled(False)
        self.execute_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self.status_label.setText("Overwriting and verifying the image file…")

        self._worker = _SanitizationWorker(self.engine, plan, phrase, self)
        self._worker.finished_result.connect(self._on_execution_finished)
        self._worker.failed.connect(self._on_execution_failed)
        self._worker.start()

    def _on_execution_finished(self, result: dict):
        self.progress.setRange(0, 100)
        self.select_button.setEnabled(True)
        self.execute_button.setEnabled(False)

        if result.get("successful"):
            self.progress.setValue(100)
            self.status_label.setText(
                "Completed: file bytes were overwritten and read-back verification passed. "
                "This is not proof of physical-media sanitization."
            )
            self.plan_details_label.setText(
                f"Bytes processed: {result.get('bytes_processed', 0):,}\n"
                "Validation: Passed"
            )
        else:
            self.progress.setValue(0)
            self.status_label.setText(
                f"Sanitization failed [{result.get('error_code', 'UNKNOWN')}]: "
                f"{result.get('error_message', 'No further details available')}"
            )
        self._plan = None  # The service closed the native plan handle after execution.

    def _on_execution_failed(self, message: str):
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.select_button.setEnabled(True)
        self.execute_button.setEnabled(False)
        self.status_label.setText(f"Sanitization failed: {message}")
        self._plan = None

    @staticmethod
    def _format_capacity(value: int) -> str:
        amount = float(value)
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if amount < 1024 or unit == "TiB":
                return f"{amount:.2f} {unit}"
            amount /= 1024
        return f"{amount:.2f} TiB"

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self,
                "Sanitization in progress",
                "Wait for the current sanitization operation to finish before closing this page.",
            )
            event.ignore()
            return
        self._release_current_plan()
        super().closeEvent(event)
