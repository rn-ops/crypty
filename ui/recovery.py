from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crypty.data.demo_data import RECOVERY_RESULTS


class RecoveryPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._build_ui()

    def refresh_device_context(self):
        device = self.main_window.device_manager.get_selected_device()
        self.source_value.setText(f"{device['name']}\n{device['filesystem']}\n{device['capacity']}")
        summary = self.main_window.backend.recover_files(device)
        self.summary_values[0].setText(f"Files Found: {summary['files_found']}")
        self.summary_values[1].setText(f"Recoverable: {summary['recoverable']}")
        self.summary_values[2].setText(f"Needs Review: {summary['needs_review']}")
        self.summary_values[3].setText(f"Invalid: {summary['invalid']}")

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 18)
        layout.setSpacing(12)

        header = QVBoxLayout()
        title = QLabel("Advanced File Recovery")
        title.setStyleSheet("font-size: 28px; font-weight: 600;")
        subtitle = QLabel("Analyze deleted, formatted or damaged storage using layered recovery techniques.")
        subtitle.setStyleSheet("color: #9aa5a1; font-size: 13px;")
        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)

        source = QFrame()
        source.setStyleSheet("background: #171c1f; border: 1px solid #2b363d;")
        source_layout = QHBoxLayout(source)
        source_layout.setContentsMargins(18, 12, 18, 12)
        source_label = QLabel("Evidence Source")
        source_label.setStyleSheet("color: #9aa5a1; font-size: 11px; letter-spacing: 0.10em;")
        self.source_value = QLabel("Samsung Portable SSD\nNTFS\n1 TB")
        self.source_value.setStyleSheet("font-size: 14px; line-height: 1.6;")
        source_layout.addWidget(source_label)
        source_layout.addWidget(self.source_value)
        layout.addWidget(source)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.start_button = QPushButton("START RECOVERY SCAN")
        self.start_button.setStyleSheet("QPushButton { background: #5d9f9a; color: #0d1517; border: 1px solid #5d9f9a; }")
        self.start_button.clicked.connect(self._run_scan)
        self.filter = QComboBox()
        self.filter.addItems(["All", "High Confidence", "Needs Review"])
        self.filter.currentTextChanged.connect(self._apply_filter)
        controls.addWidget(self.start_button)
        controls.addStretch(1)
        controls.addWidget(self.filter)
        layout.addLayout(controls)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #a8d9d3; font-size: 12px;")
        layout.addWidget(self.status_label)

        results = QFrame()
        results.setStyleSheet("background: #171c1f; border: 1px solid #2b363d;")
        results_layout = QHBoxLayout(results)
        results_layout.setContentsMargins(18, 16, 18, 16)
        results_layout.setSpacing(20)

        left_results = QVBoxLayout()
        self.table = QTableWidget(len(RECOVERY_RESULTS), 6)
        self.table.setHorizontalHeaderLabels(["FILE", "TYPE", "SIZE", "METHOD", "CONFIDENCE", "STATUS"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 180)
        self.table.setColumnWidth(1, 95)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 100)
        self._populate_table(RECOVERY_RESULTS)
        left_results.addWidget(self.table)

        summary = QFrame()
        summary.setStyleSheet("background: #121517; border: 1px solid #2b363d;")
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setSpacing(8)
        summary_header = QLabel("RECOVERY SUMMARY")
        summary_header.setStyleSheet("color: #9aa5a1; font-size: 11px; letter-spacing: 0.12em;")
        summary_layout.addWidget(summary_header)
        self.summary_values = [
            QLabel("Files Found: 127"),
            QLabel("Recoverable: 94"),
            QLabel("Needs Review: 21"),
            QLabel("Invalid: 12"),
            QLabel("Illustrative result set; source media remains unchanged."),
        ]
        for value in self.summary_values:
            value.setStyleSheet("font-size: 12px; color: #edf1ef;")
            summary_layout.addWidget(value)

        results_layout.addLayout(left_results, 3)
        results_layout.addWidget(summary, 1)
        layout.addWidget(results)

        self.refresh_device_context()

    def _populate_table(self, rows):
        self.table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(item["file"]))
            self.table.setItem(row, 1, QTableWidgetItem(item["type"]))
            self.table.setItem(row, 2, QTableWidgetItem(item["size"]))
            self.table.setItem(row, 3, QTableWidgetItem(item["method"]))
            self.table.setItem(row, 4, QTableWidgetItem(f"{item['confidence']}%"))
            self.table.setItem(row, 5, QTableWidgetItem(item["status"]))

    def _apply_filter(self, value):
        if value == "High Confidence":
            filtered = [item for item in RECOVERY_RESULTS if item["confidence"] >= 90]
        elif value == "Needs Review":
            filtered = [item for item in RECOVERY_RESULTS if item["status"] in {"Review", "Uncertain"}]
        else:
            filtered = RECOVERY_RESULTS
        self._populate_table(filtered)

    def _run_scan(self):
        self.start_button.setEnabled(False)
        self.status_label.setText("Analyzing filesystem...")
        self.progress.setValue(0)
        self._steps = [
            (15, "Analyzing filesystem..."),
            (35, "Reading metadata..."),
            (55, "Scanning unallocated space..."),
            (75, "Matching file signatures..."),
            (90, "Reconstructing fragments..."),
            (100, "Validating recovered files..."),
        ]
        self._scan_index = 0
        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._advance_scan)
        self._scan_timer.start(500)

    def _advance_scan(self):
        if self._scan_index >= len(self._steps):
            self._scan_timer.stop()
            self.start_button.setEnabled(True)
            self.status_label.setText("Recovery scan complete. Source media remains unchanged.")
            self._apply_filter(self.filter.currentText())
            return

        value, message = self._steps[self._scan_index]
        self.progress.setValue(value)
        self.status_label.setText(message)
        self._scan_index += 1
