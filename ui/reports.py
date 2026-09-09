from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from crypty.data.demo_data import REPORT_SUMMARY


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
            ("CASE", REPORT_SUMMARY["case_id"]),
            ("OPERATOR", REPORT_SUMMARY["operator"]),
            ("DEVICE", REPORT_SUMMARY["device"]),
            ("OPERATION", REPORT_SUMMARY["operation"]),
            ("START", REPORT_SUMMARY["start_time"]),
            ("STATUS", REPORT_SUMMARY["status"]),
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
        stats_layout.addWidget(QLabel("RECOVERY RESULTS\n127 files identified\n94 high-confidence results"))
        stats_layout.addWidget(QLabel("INTEGRITY\nSHA-256 records generated"))
        stats_layout.addWidget(QLabel("AUDIT\n12 events recorded"))
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

        integrity = QLabel("AUDIT INTEGRITY\nVALID")
        integrity.setStyleSheet("color: #a8d9d3; font-size: 11px; letter-spacing: 0.10em; border: 1px solid #2b363d; background: #171c1f; padding: 6px 10px;")
        layout.addWidget(integrity)

        log_panel = QFrame()
        log_panel.setStyleSheet("background: #171c1f; border: 1px solid #2b363d;")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(18, 16, 18, 16)
        log_layout.setSpacing(12)

        from crypty.data.demo_data import AUDIT_LOG

        for event in AUDIT_LOG:
            line = QLabel(
                f"{event['timestamp']}\n{event['action']}\n{event['target']}\n{event['status']}\nOperator: {event['operator']}"
            )
            line.setStyleSheet("font-family: 'Consolas'; font-size: 12px; line-height: 1.8; border-bottom: 1px solid #2b363d; padding-bottom: 6px;")
            log_layout.addWidget(line)

        layout.addWidget(log_panel)
        layout.addStretch(1)

    def _preview_report(self):
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlainText(
            "Crypty Investigation Report\n"
            "Case: CRYPTY-001\n"
            "Operator: Investigator session\n"
            "Device: Samsung Portable SSD\n"
            "Operation: Recovery Analysis\n"
            "Status: Completed\n\n"
            "Report preview. No live evidence was acquired or modified."
        )
        self._preview.show()

    def _export_report(self):
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setPlainText(
            "REPORT EXPORT PREVIEW\n"
            "Crypty report export prepared successfully.\n"
            "No physical data was modified."
        )
        self._preview.show()
