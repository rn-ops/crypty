from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from data.demo_data import RECENT_OPERATIONS


class DashboardPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._build_ui()
        self.refresh_device_context()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 18)
        layout.setSpacing(12)

        header = QVBoxLayout()
        title = QLabel("Case overview")
        title.setStyleSheet("font-size: 28px; font-weight: 600;")
        sub = QLabel("Case overview and active evidence context")
        sub.setStyleSheet("color: #9aa5a1; font-size: 13px;")
        header.addWidget(title)
        header.addWidget(sub)
        layout.addLayout(header)

        case_panel = QFrame()
        case_panel.setStyleSheet("background: #171c1f; border: none;")
        case_layout = QHBoxLayout(case_panel)
        case_layout.setContentsMargins(18, 12, 18, 12)
        case_layout.setSpacing(18)

        case_fields = [
            ("CASE", "CRYPTY-001"),
            ("OPERATOR", "Investigator session"),
            ("TARGET", "Samsung Portable SSD"),
            ("SCOPE", "Forensic Analysis"),
        ]
        for label, value in case_fields:
            box = QFrame()
            box.setStyleSheet("background: transparent; border: none;")
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(10, 8, 10, 8)
            label_widget = QLabel(label)
            label_widget.setStyleSheet("color: #9aa5a1; font-size: 10px; letter-spacing: 0.12em;")
            value_widget = QLabel(value)
            value_widget.setStyleSheet("font-size: 13px; font-weight: 600;")
            box_layout.addWidget(label_widget)
            box_layout.addWidget(value_widget)
            case_layout.addWidget(box)

        layout.addWidget(case_panel)

        lower = QHBoxLayout()
        lower.setSpacing(12)

        info_panel = QFrame()
        info_panel.setStyleSheet("background: #171c1f; border: none;")
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(18, 14, 18, 14)
        info_layout.setSpacing(10)

        info_title = QLabel("ACTIVE DEVICE")
        info_title.setStyleSheet("color: #9aa5a1; font-size: 11px; letter-spacing: 0.10em;")
        self.device_name_label = QLabel("Samsung Portable SSD")
        self.device_meta_label = QLabel("1 TB · USB 3.2")
        self.device_status_label = QLabel("Status: Connected")
        self.device_name_label.setStyleSheet("font-size: 17px; font-weight: 600;")
        self.device_meta_label.setStyleSheet("color: #dfe8e5; font-size: 12px;")
        self.device_status_label.setStyleSheet("color: #a8d9d3; font-size: 12px;")
        info_layout.addWidget(info_title)
        info_layout.addWidget(self.device_name_label)
        info_layout.addWidget(self.device_meta_label)
        info_layout.addWidget(self.device_status_label)

        info_panel2 = QFrame()
        info_panel2.setStyleSheet("background: #171c1f; border: none;")
        info2_layout = QVBoxLayout(info_panel2)
        info2_layout.setContentsMargins(18, 14, 18, 14)
        info2_layout.setSpacing(10)
        mode_title = QLabel("MODE")
        mode = QLabel("Forensic Analysis")
        integrity_title = QLabel("INTEGRITY")
        integrity = QLabel("SHA-256")
        ready = QLabel("Ready")
        mode_title.setStyleSheet("color: #9aa5a1; font-size: 11px; letter-spacing: 0.10em;")
        mode.setStyleSheet("font-size: 17px; font-weight: 600;")
        integrity_title.setStyleSheet("color: #9aa5a1; font-size: 11px; letter-spacing: 0.10em;")
        integrity.setStyleSheet("font-size: 15px;")
        ready.setStyleSheet("color: #a8d9d3; font-size: 12px;")
        info2_layout.addWidget(mode_title)
        info2_layout.addWidget(mode)
        info2_layout.addWidget(integrity_title)
        info2_layout.addWidget(integrity)
        info2_layout.addWidget(ready)

        lower.addWidget(info_panel)
        lower.addWidget(info_panel2)
        layout.addLayout(lower)

        recent = QFrame()
        recent.setStyleSheet("background: #171c1f; border: none;")
        recent_layout = QVBoxLayout(recent)
        recent_layout.setContentsMargins(16, 14, 16, 14)
        recent_layout.setSpacing(10)

        recent_header = QLabel("RECENT OPERATIONS")
        recent_header.setStyleSheet("font-size: 12px; color: #9aa5a1; letter-spacing: 0.12em;")
        recent_layout.addWidget(recent_header)

        table = QTableWidget(len(RECENT_OPERATIONS), 4)
        table.setHorizontalHeaderLabels(["TIME", "OPERATION", "DEVICE", "STATUS"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 90)
        table.setColumnWidth(1, 220)
        table.setColumnWidth(2, 200)
        table.setStyleSheet("QTableWidget { gridline-color: #2b363d; background: transparent; }")

        for row, item in enumerate(RECENT_OPERATIONS):
            table.setItem(row, 0, QTableWidgetItem(item["time"]))
            table.setItem(row, 1, QTableWidgetItem(item["operation"]))
            table.setItem(row, 2, QTableWidgetItem(item["device"]))
            table.setItem(row, 3, QTableWidgetItem(item["status"]))

        recent_layout.addWidget(table)
        layout.addWidget(recent)

    def refresh_device_context(self):
        device = self.main_window.device_manager.get_selected_device()
        self.device_name_label.setText(device["name"])
        self.device_meta_label.setText(f"{device['capacity']} · {device['interface']}")
        self.device_status_label.setText(f"Status: {device['status'].title()}")

    def on_show(self):
        self.refresh_device_context()
