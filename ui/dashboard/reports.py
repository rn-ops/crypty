from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from auth_client import AuthenticationError


class ReportsPage(QWidget):
    def __init__(self, main_window, audit_only=False):
        super().__init__()
        self.main_window = main_window
        self.audit_only = audit_only
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 12)
        layout.setSpacing(8)

        if self.audit_only:
            self._build_audit_log(layout)
            return

        device = self.main_window.device_manager.get_selected_device()
        inspection = self.main_window.backend.analyze_device(device) if device else {}

        title = QLabel("Investigation Report")
        title.setFixedHeight(24)
        title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)

        summary = QFrame()
        summary.setStyleSheet("background: #171c1f; border: 1px solid #2b363d;")
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        summary_layout.setSpacing(12)

        fields = [
            ("CASE", "No case assigned"),
            ("OPERATOR", getattr(self.main_window.session, "username", "Current session")),
            ("DEVICE", device.get("name", "No source selected") if device else "No source selected"),
            ("OPERATION", "Not started"),
            ("START", "—"),
            ("STATUS", "Awaiting analysis"),
        ]

        for label, value in fields:
            row = QHBoxLayout()
            label_widget = QLabel(label)
            label_widget.setStyleSheet("color: #9aa5a1; font-size: 11px; letter-spacing: 0.12em;")
            value_widget = QLabel(value)
            value_widget.setStyleSheet("font-size: 14px;")
            row.addWidget(label_widget)
            row.addStretch(1)
            row.addWidget(value_widget)
            summary_layout.addLayout(row)

        stats = QFrame()
        stats.setStyleSheet("background: #171c1f; border: 1px solid #2b363d;")
        stats_layout = QVBoxLayout(stats)
        stats_layout.setContentsMargins(18, 16, 18, 16)
        stats_layout.setSpacing(12)
        stats_layout.addWidget(QLabel(
            f"INDEXED EVIDENCE\n{inspection.get('evidence_items', 'Pending')} entries identified\n"
            f"{inspection.get('total_bytes', 'Pending')} bytes indexed"
        ))
        stats_layout.addWidget(QLabel("INTEGRITY\nPending verification"))
        stats_layout.addWidget(QLabel(f"NATIVE WORKFLOW\n{len(self.main_window.backend.audit_events())} local operation events"))
        report_columns = QHBoxLayout()
        report_columns.setSpacing(16)
        report_columns.addWidget(summary, 3)
        report_columns.addWidget(stats, 2)
        layout.addLayout(report_columns)

        buttons = QHBoxLayout()
        preview = QPushButton("Preview Report")
        export = QPushButton("Export PDF")
        buttons.addWidget(preview)
        buttons.addWidget(export)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        preview.clicked.connect(self._preview_report)
        export.clicked.connect(self._export_report)
        layout.addStretch(1)

    def _build_audit_log(self, layout):
        title = QLabel("Audit Log")
        title.setFixedHeight(24)
        title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        self.integrity = QLabel("Audit integrity has not been verified.")
        self.integrity.setWordWrap(True)
        self.integrity.setStyleSheet("color: #a8d9d3; font-size: 11px; border: 1px solid #2b363d; background: #171c1f; padding: 6px 10px;")
        toolbar.addWidget(self.integrity, 1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_audit_log)
        toolbar.addWidget(refresh)
        layout.addLayout(toolbar)

        self.audit_log_panel = QFrame()
        log_panel = self.audit_log_panel
        log_panel.setStyleSheet("background: #171c1f; border: 1px solid #2b363d;")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(18, 16, 18, 16)
        log_layout.setSpacing(12)
        self.audit_entries_layout = log_layout
        self._render_audit_logs([])

        layout.addWidget(log_panel)
        layout.addStretch(1)

    def _render_audit_logs(self, entries):
        while self.audit_entries_layout.count():
            item = self.audit_entries_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not entries:
            empty = QLabel("No account audit entries are available.")
            empty.setWordWrap(True)
            empty.setStyleSheet("color:#a7a5ac;border:none;")
            self.audit_entries_layout.addWidget(empty)
            return
        for event in entries:
            line = QLabel(
                f"{event.get('timestamp', '')}  ·  {event.get('action', '')}\n"
                f"Account: {event.get('account') or '—'}  ·  Plan: {event.get('account_plan') or '—'}\n"
                f"Case: {event.get('case_name') or '—'} ({event.get('case_id') or '—'})\n"
                f"Device fingerprint: {event.get('device_fingerprint') or '—'}\n"
                f"{event.get('details') or ''}"
            )
            line.setWordWrap(True)
            line.setStyleSheet("font-family: 'Consolas'; font-size: 11px; border-bottom: 1px solid #2b363d; padding-bottom: 8px;")
            self.audit_entries_layout.addWidget(line)

    def _refresh_audit_log(self):
        try:
            entries = self.main_window.auth_client.get_audit_logs(
                self.main_window.session
            )
            integrity = self.main_window.auth_client.verify_audit_log(
                self.main_window.session
            )
        except AuthenticationError as error:
            self.integrity.setText(f"Audit service error: {error}")
            self.integrity.setStyleSheet("color:#e58b83;font-size:11px;border:1px solid #2b363d;background:#171c1f;padding:6px 10px;")
            self._render_audit_logs([])
            return
        self.integrity.setText(integrity.get("message", "Integrity result unavailable."))
        self.integrity.setStyleSheet(
            "color:#a8d9d3;font-size:11px;border:1px solid #2b363d;background:#171c1f;padding:6px 10px;"
            if integrity.get("valid")
            else "color:#e58b83;font-size:11px;border:1px solid #2b363d;background:#171c1f;padding:6px 10px;"
        )
        self._render_audit_logs(entries)

    def _preview_report(self):
        device = self.main_window.device_manager.get_selected_device()
        inspection = self.main_window.backend.analyze_device(device) if device else {}
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlainText(
            "Crypty Investigation Report\n"
            "Case: Not assigned\n"
            f"Operator: {getattr(self.main_window.session, 'username', 'Current session')}\n"
            f"Device: {device.get('name', 'No source selected') if device else 'No source selected'}\n"
            "Operation: Metadata inspection\n"
            f"Filesystem: {inspection.get('filesystem', 'Pending')}\n"
            f"Entries identified: {inspection.get('evidence_items', 'Pending')}\n"
            f"Bytes indexed: {inspection.get('total_bytes', 'Pending')}\n\n"
            "Report generated from the native workflow engine."
        )
        self._preview.show()

    def _export_report(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Crypty report",
            "crypty-report.json",
            "JSON report (*.json)",
        )
        if not filename:
            return
        if self.main_window.backend.write_report(filename):
            QMessageBox.information(self, "Report exported", f"Report saved to:\n{filename}")
        else:
            QMessageBox.critical(self, "Report export failed", "The native workflow could not write the report.")

    def on_show(self):
        if self.audit_only:
            self._refresh_audit_log()
