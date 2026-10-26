from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


class DashboardPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._build_ui()
        self.refresh_device_context()

    def _panel(self, title, subtitle=""):
        frame = QFrame()
        frame.setObjectName("overviewPanel")
        frame.setStyleSheet("QFrame#overviewPanel { background:#19191c; border:1px solid #3a3a40; border-radius:8px; }")
        box = QVBoxLayout(frame)
        box.setContentsMargins(16, 14, 16, 14)
        box.setSpacing(8)
        label = QLabel(title)
        label.setStyleSheet("font-size:13px;font-weight:800;border:none;")
        box.addWidget(label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setWordWrap(True)
            sub.setStyleSheet("font-size:11px;color:#a7a5ac;border:none;")
            box.addWidget(sub)
        return frame, box

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(14)

        kicker = QLabel("AVANT / FORENSIC OPERATIONS")
        kicker.setStyleSheet("font-size:10px;font-weight:800;letter-spacing:.16em;color:#f0525b;border:none;")
        layout.addWidget(kicker)
        title = QLabel("Evidence deserves better tools.")
        title.setObjectName("workspaceTitle")
        title.setStyleSheet("font-size:30px;font-weight:900;letter-spacing:-.04em;border:none;")
        layout.addWidget(title)
        subtitle = QLabel("Create a case, attach the relevant media, and keep each operation tied to its evidence context.")
        subtitle.setObjectName("workspaceSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        create_case = QPushButton("+ Create a case")
        create_case.setProperty("class", "primary")
        create_case.clicked.connect(lambda: self.main_window.show_page("cases"))
        media = QPushButton("Open Media Explorer")
        media.clicked.connect(self.main_window.toggle_media_explorer)
        evidence = QPushButton("Evidence intelligence")
        evidence.clicked.connect(lambda: self.main_window.show_page("evidence"))
        actions.addWidget(create_case)
        actions.addWidget(media)
        actions.addWidget(evidence)
        actions.addStretch(1)
        layout.addLayout(actions)

        stats = QGridLayout()
        stats.setSpacing(10)
        self.case_count = self._stat_card("ACTIVE CASES", "0", "Cases stored locally")
        self.source_count = self._stat_card("SELECTED SOURCE", "—", "Select media to inspect")
        self.recovery_count = self._stat_card("RECOVERY JOBS", "—", "Job service not connected")
        self.audit_count = self._stat_card("AUDIT EVENTS", "—", "Audit service not connected")
        for index, card in enumerate((self.case_count, self.source_count, self.recovery_count, self.audit_count)):
            stats.addWidget(card, 0, index)
        layout.addLayout(stats)

        lower = QGridLayout()
        lower.setSpacing(12)
        activity, activity_box = self._panel("Workspace activity", "Operation events will appear here when the audit/event provider is connected.")
        self.activity_empty = QLabel("No activity recorded in this session.")
        self.activity_empty.setWordWrap(True)
        self.activity_empty.setStyleSheet("color:#a7a5ac;padding:12px 0;border:none;")
        activity_box.addWidget(self.activity_empty)
        lower.addWidget(activity, 0, 0, 1, 2)

        context, context_box = self._panel("Current context", "The active case and selected source used by downstream pages.")
        self.case_context = QLabel("No case selected")
        self.case_context.setWordWrap(True)
        self.case_context.setStyleSheet("font-size:16px;font-weight:800;border:none;")
        self.device_name_label = QLabel("No media selected")
        self.device_name_label.setWordWrap(True)
        self.device_name_label.setStyleSheet("color:#d4d1d6;border:none;")
        self.device_meta_label = QLabel("Device details will appear after selection.")
        self.device_meta_label.setWordWrap(True)
        self.device_meta_label.setStyleSheet("color:#a7a5ac;font-size:11px;border:none;")
        context_box.addWidget(self.case_context)
        context_box.addWidget(self.device_name_label)
        context_box.addWidget(self.device_meta_label)
        context_box.addStretch(1)
        lower.addWidget(context, 0, 2)
        layout.addLayout(lower, 1)

        recent, recent_box = self._panel("Recent operations", "No sample or fabricated operation records are displayed.")
        self.operations = QTableWidget(0, 4)
        self.operations.setHorizontalHeaderLabels(["TIME", "CASE", "OPERATION", "STATUS"])
        self.operations.setEditTriggers(QTableWidget.NoEditTriggers)
        self.operations.setSelectionMode(QTableWidget.NoSelection)
        self.operations.verticalHeader().setVisible(False)
        self.operations.horizontalHeader().setStretchLastSection(True)
        self.operations.setMinimumHeight(90)
        self.operations.setMaximumHeight(150)
        self.operations.setRowCount(1)
        empty = QTableWidgetItem("No operation records available")
        self.operations.setItem(0, 0, empty)
        self.operations.setSpan(0, 0, 1, 4)
        recent_box.addWidget(self.operations)
        layout.addWidget(recent)
        layout.addStretch(1)

    def _stat_card(self, label, value, foot):
        card = QFrame()
        card.setStyleSheet("QFrame { background:#19191c; border:1px solid #3a3a40; border-radius:8px; }")
        box = QVBoxLayout(card)
        box.setContentsMargins(13, 12, 13, 12)
        title = QLabel(label)
        title.setStyleSheet("font-size:10px;font-weight:800;letter-spacing:.08em;color:#a7a5ac;border:none;")
        number = QLabel(value)
        number.setStyleSheet("font-size:23px;font-weight:900;color:#f3f1ee;border:none;")
        note = QLabel(foot)
        note.setWordWrap(True)
        note.setStyleSheet("font-size:10px;color:#77757e;border:none;")
        box.addWidget(title)
        box.addWidget(number)
        box.addWidget(note)
        card.value_label = number
        return card

    def refresh_device_context(self):
        device = self.main_window.device_manager.get_selected_device()
        case = getattr(self.main_window, "active_case", None)
        case_count = 0
        cases_page = getattr(self.main_window, "pages", {}).get("cases")
        if cases_page is not None:
            case_count = len(getattr(cases_page, "cases", []))
        self.case_count.value_label.setText(str(case_count))
        self.case_context.setText(case.get("name", "Unnamed case") if case else "No case selected")
        if not device:
            self.device_name_label.setText("No media selected")
            self.device_meta_label.setText("Connect or select a source to begin.")
            self.source_count.value_label.setText("—")
            return
        self.device_name_label.setText(device.get("name", "Unnamed media"))
        self.device_meta_label.setText(" · ".join(str(device.get(key, "Unknown")) for key in ("capacity", "interface", "filesystem")))
        self.source_count.value_label.setText("1 selected")

    def on_show(self):
        self.refresh_device_context()
