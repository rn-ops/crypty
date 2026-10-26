from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QScrollArea,
    QSizePolicy,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class DevicesPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(self.scroll)
        page = QWidget()
        self.scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 18, 24, 24)
        layout.setSpacing(14)

        title_row = QHBoxLayout()
        title = QLabel("Evidence sources")
        title.setStyleSheet("font-size: 21px; font-weight: 600;")
        title_row.addWidget(title)
        title_row.addStretch(1)
        hint = QLabel("SOURCE INTELLIGENCE")
        hint.setStyleSheet("color: #9aa5a1; font-size: 11px;")
        title_row.addWidget(hint)
        layout.addLayout(title_row)

        content = QHBoxLayout()
        content.setSpacing(12)

        left = QFrame()
        left.setStyleSheet("background: #171c1f; border: 1px solid #2b363d;")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 10, 12, 10)
        left_layout.setSpacing(6)

        heading = QLabel("ATTACHED MEDIA")
        heading.setStyleSheet("color: #9aa5a1; font-size: 10px; letter-spacing: 0.12em;")
        left_layout.addWidget(heading)

        self.device_list = QListWidget()
        self.device_list.setStyleSheet(
            "QListWidget { background: transparent; border: none; } "
            "QListWidget::item { padding: 8px 6px; border-bottom: 1px solid #263034; } "
            "QListWidget::item:selected { background: #202a2b; color: #edf1ef; }"
        )
        self.device_list.itemClicked.connect(self._on_device_selected)
        left_layout.addWidget(self.device_list)
        content.addWidget(left, 1)

        right = QFrame()
        right.setStyleSheet("background: #171c1f; border: 1px solid #2b363d;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(14, 10, 14, 10)
        right_layout.setSpacing(8)

        detail_row = QHBoxLayout()
        detail_label = QLabel("SOURCE DETAILS")
        detail_label.setStyleSheet("color: #9aa5a1; font-size: 10px; letter-spacing: 0.12em;")
        detail_row.addWidget(detail_label)
        detail_row.addStretch(1)
        self.device_status = QLabel("CONNECTED")
        self.device_status.setStyleSheet(
            "background: #1e2d2a; color: #a8d9d3; border: 1px solid #334642; "
            "padding: 2px 7px; font-size: 10px;"
        )
        detail_row.addWidget(self.device_status)
        right_layout.addLayout(detail_row)

        self.device_name = QLabel("Select an evidence source")
        self.device_name.setStyleSheet("font-size: 18px; font-weight: 600;")
        right_layout.addWidget(self.device_name)

        properties = QFrame()
        properties.setStyleSheet("background: #121719; border: none;")
        properties_layout = QGridLayout(properties)
        properties_layout.setContentsMargins(10, 8, 10, 8)
        properties_layout.setHorizontalSpacing(24)
        properties_layout.setVerticalSpacing(5)
        self.property_labels = {}
        property_rows = [
            ("interface", "Interface"),
            ("capacity", "Capacity"),
            ("media_type", "Media"),
            ("filesystem", "Filesystem"),
            ("health", "Health"),
            ("mount", "Mount"),
        ]
        for row, (key, label) in enumerate(property_rows):
            key_label = QLabel(label)
            key_label.setStyleSheet("color: #8f9b96; font-size: 10px;")
            value_label = QLabel()
            value_label.setStyleSheet("color: #e0e7e3; font-size: 11px;")
            properties_layout.addWidget(key_label, row // 2, (row % 2) * 2)
            properties_layout.addWidget(value_label, row // 2, (row % 2) * 2 + 1)
            self.property_labels[key] = value_label
        right_layout.addWidget(properties)

        self.analysis_status = QLabel("Connect or select a source to populate metadata and analysis tools.")
        self.analysis_status.setWordWrap(True)
        self.analysis_status.setStyleSheet("color: #a8d9d3; font-size: 11px; padding-top: 2px;")
        right_layout.addWidget(self.analysis_status)

        action_row = QHBoxLayout()
        self.analyze_button = QPushButton("Inspect metadata")
        self.analyze_button.setProperty("class", "primary")
        self.analyze_button.clicked.connect(self._analyze_device)
        action_row.addWidget(self.analyze_button)
        action_row.addStretch(1)
        right_layout.addLayout(action_row)

        content.addWidget(right, 2)
        layout.addLayout(content)

        # Feature placeholders are deliberately data-free until their engines are wired in.
        intelligence_title = QLabel("EVIDENCE INTELLIGENCE")
        intelligence_title.setStyleSheet("font-size: 12px; font-weight: 700; letter-spacing: 0.14em; color: #ff777e; padding-top: 8px;")
        layout.addWidget(intelligence_title)
        intelligence_subtitle = QLabel("Analytical workspaces · populated when evidence is indexed")
        intelligence_subtitle.setStyleSheet("color: #b4b4bf; font-size: 12px;")
        layout.addWidget(intelligence_subtitle)
        feature_grid = QGridLayout()
        feature_grid.setSpacing(12)
        features = [
            ("01", "Cross-Artifact Timeline Reconstruction", "Correlate filesystem events, metadata, and recovered artifacts into a reviewable timeline."),
            ("02", "Evidence Relationship Graph", "Explore links between files, paths, devices, hashes, and related artifacts."),
            ("03", "Evidence-Backed Conclusions Engine", "Build traceable findings with references to supporting evidence and confidence notes."),
            ("04", "Deleted-Data Intelligence", "Surface deleted-data patterns, recoverability signals, and carving results."),
        ]
        self.feature_cards = []
        for index, (number, name, description) in enumerate(features):
            card = QFrame()
            card.setObjectName("evidenceFeatureCard")
            card.setStyleSheet("QFrame#evidenceFeatureCard { background: #1b1b20; border: 1px solid #414149; } QFrame#evidenceFeatureCard:hover { border: 1px solid #e04b54; background: #202025; }")
            card.setMinimumHeight(132)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.setSpacing(8)
            num = QLabel(number)
            num.setStyleSheet("color: #ff777e; font-size: 10px; font-weight: 700; letter-spacing: 0.12em;")
            name_label = QLabel(name)
            name_label.setWordWrap(True)
            name_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #f5f5f7;")
            description_label = QLabel(description)
            description_label.setWordWrap(True)
            description_label.setStyleSheet("font-size: 11px; color: #b4b4bf; line-height: 1.4;")
            state = QLabel("AWAITING EVIDENCE")
            state.setStyleSheet("color: #92929e; font-size: 9px; font-weight: 700; letter-spacing: 0.1em;")
            card_layout.addWidget(num)
            card_layout.addWidget(name_label)
            card_layout.addWidget(description_label, 1)
            card_layout.addWidget(state)
            feature_grid.addWidget(card, index // 2, index % 2)
            self.feature_cards.append(card)
        layout.addLayout(feature_grid)

        self.populate_devices()

    def populate_devices(self):
        devices = self.main_window.device_manager.get_devices()
        self.device_list.clear()
        for device in devices:
            item = QListWidgetItem(f"{device['name']}\n{device['capacity']} · {device['interface']}")
            item.setData(Qt.UserRole, device)
            self.device_list.addItem(item)

        if devices:
            self.device_list.setCurrentRow(0)
            self._update_selected_device(devices[0])
        else:
            self.device_name.setText("No evidence source selected")
            self.device_status.setText("WAITING")
            for value_label in self.property_labels.values():
                value_label.setText("—")
            self.analysis_status.setText("No media detected. Connect a source, then refresh the media explorer.")

    def _on_device_selected(self, item):
        self._update_selected_device(item.data(Qt.UserRole))

    def _update_selected_device(self, device):
        self.main_window.set_active_device(device)
        self._render_device(device)

    def _render_device(self, device):
        if not device:
            self.device_name.setText("No evidence source selected")
            self.device_status.setText("WAITING")
            for value_label in self.property_labels.values():
                value_label.setText("—")
            self.analysis_status.setText("No source selected. Connect media or refresh the explorer.")
            self.analyze_button.setEnabled(False)
            return
        self.analyze_button.setEnabled(True)
        self.device_name.setText(device["name"])
        self.device_status.setText(device["status"])
        for key, value_label in self.property_labels.items():
            value_label.setText(str(device[key]))
        self.analysis_status.setText("Source selected. Inspect metadata to populate this workspace.")

    def refresh_device_context(self):
        self._render_device(self.main_window.device_manager.get_selected_device())

    def _analyze_device(self):
        device = self.main_window.device_manager.get_selected_device()
        if not device:
            self.analysis_status.setText("Select a detected source before inspecting metadata.")
            return
        self.analyze_button.setEnabled(False)
        self.analysis_status.setText("Inspecting device metadata...")

        self.timer = QTimer(self)
        self.timer.setInterval(800)
        self.timer.timeout.connect(lambda: self._finish_analysis(device))
        self.timer.start()

    def _finish_analysis(self, device):
        result = self.main_window.backend.analyze_device(device)
        self.analysis_status.setText(
            f"Inspection complete  ·  {result['filesystem']}  ·  {result['media_type']}"
        )
        self.analyze_button.setEnabled(True)
        self.timer.stop()

        QMessageBox.information(
            self,
            "Metadata inspection",
            f"Analysis complete\nFilesystem detected: {result['filesystem']}\n"
            f"Media type: {result['media_type']}\n"
            f"Evidence entries: {result['evidence_items']}\n"
            f"Total bytes: {result['total_bytes']:,}\n\n"
            "Metadata analysis completed.",
        )
