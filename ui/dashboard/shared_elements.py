import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

class WorkspaceHeader(QFrame):
    page_selected = Signal(str)
    media_explorer_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("pageHeader")
        self.setStyleSheet("QFrame#pageHeader { background: #151517; border-bottom: 1px solid #3a3a40; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 8)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(12)
        brand = QLabel("C  CRYPTY")
        brand.setStyleSheet("color: #f3f1ee; font-size: 20px; font-weight: 900; letter-spacing: .02em; padding-right: 8px;")
        top.addWidget(brand)
        caption = QLabel("AVANT  /  FORENSICS WORKBENCH")
        caption.setStyleSheet("color: #a7a5ac; font-size: 10px; letter-spacing: .12em;")
        top.addWidget(caption)
        top.addStretch(1)

        self.case_label = QLabel("NO ACTIVE CASE")
        self.case_label.setStyleSheet("background: #202024; color: #d4d1d6; border: 1px solid #414149; padding: 6px 9px; font-size: 10px; font-weight: 700;")
        top.addWidget(self.case_label)

        self.media_button = QPushButton("▤  Media Explorer")
        self.media_button.setCursor(Qt.PointingHandCursor)
        self.media_button.clicked.connect(self.media_explorer_requested.emit)
        top.addWidget(self.media_button)
        layout.addLayout(top)

        nav = QHBoxLayout()
        nav.setSpacing(4)
        self.nav_buttons = {}
        labels = [
            ("overview", "Overview"),
            ("cases", "Cases"),
            ("devices", "Devices"),
            ("recovery", "Recovery"),
            ("sanitization", "Sanitization"),
            ("evidence", "Evidence"),
            ("reports", "Reports & Audit"),
            ("settings", "Settings"),
        ]
        for key, label in labels:
            button = QPushButton(label)
            button.setObjectName("headerNav")
            button.setCursor(Qt.PointingHandCursor)
            button.setCheckable(False)
            button.clicked.connect(lambda checked=False, page=key: self.page_selected.emit(page))
            nav.addWidget(button)
            self.nav_buttons[key] = button
        nav.addStretch(1)
        layout.addLayout(nav)

    def set_active_case(self, case_name=None):
        if case_name:
            self.case_label.setText("CASE  ·  " + case_name.upper())
            self.case_label.setToolTip(case_name)
        else:
            self.case_label.setText("NO ACTIVE CASE")
            self.case_label.setToolTip("Create or select a case to establish investigation context")


class MediaSidebar(QSplitter):
    device_selected = Signal(object)

    def __init__(self, session, device_manager, active_device=None):
        super().__init__(Qt.Vertical)

        self.session = session
        self.device_manager = device_manager
        self.active_device = active_device

        self.setObjectName("mediaSidebar")
        self.setChildrenCollapsible(False)
        self.setHandleWidth(6)

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        explorer_panel = QFrame()
        explorer_layout = QVBoxLayout(explorer_panel)
        explorer_layout.setContentsMargins(10, 12, 10, 8)
        explorer_layout.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(0)

        title = QLabel("MEDIA EXPLORER")
        title.setObjectName("panelEyebrow")
        title.setStyleSheet(
            "color: #94a3b8; font-size: 12px; margin-top: 2px;"
        )
        header_row.addWidget(title)
        header_row.addStretch(1)

        self.refresh_explorer_btn = QPushButton("↻")
        self.refresh_explorer_btn.setToolTip(
            "Rescan hardware and hot-load new media drives"
        )
        self.refresh_explorer_btn.setFixedSize(24, 14)
        self.refresh_explorer_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_explorer_btn.setStyleSheet("""
            QPushButton {
                background: #1e292b;
                color: #64748b;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #2a3b3d;
                border-radius: 3px;
                padding: 0px;
                margin: 0px;
            }
            QPushButton:hover {
                background-color: #2a3b3d;
                color: #38bdf8;
                border-color: #38bdf8;
            }
        """)
        self.refresh_explorer_btn.clicked.connect(self.refresh)
        header_row.addWidget(self.refresh_explorer_btn)
        explorer_layout.addLayout(header_row)

        self.device_state = QLabel("Detected Media")
        self.device_state.setStyleSheet(
            "color: #94a3b8; font-size: 14px; "
            "margin-top: 2px; margin-bottom: 4px;"
        )
        explorer_layout.addWidget(self.device_state)

        self.media_tree = QTreeWidget()
        self.media_tree.setHeaderHidden(True)
        self.media_tree.setObjectName("mediaTree")
        self.media_tree.setIndentation(16)
        self.media_tree.itemClicked.connect(self._select_media)
        self.media_tree.itemExpanded.connect(self._populate_expanded_folder)

        self.media_tree.setStyleSheet("""
            QTreeView#mediaTree {
                background-color: transparent;
                outline: 0;
            }
            QTreeView#mediaTree::item {
                padding-top: 5px;
                padding-bottom: 5px;
                padding-left: 4px;
                border-bottom: 1px solid #1e292b;
            }
            QTreeView#mediaTree::branch {
                background: transparent;
                width: 16px;
                border-bottom: 1px solid #1e292b;
            }
            QTreeView#mediaTree::branch:has-siblings:!adjoins-item,
            QTreeView#mediaTree::branch:has-siblings:adjoins-item,
            QTreeView#mediaTree::branch:!has-siblings:adjoins-item {
                border-right: 1px dotted #334155;
            }
            QTreeView#mediaTree::branch:has-children:closed {
                image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='9 18 15 12 9 6'%3E%3C/polyline%3E%3C/svg%3E");
            }
            QTreeView#mediaTree::branch:has-children:open {
                image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
            }
        """)

        explorer_layout.addWidget(self.media_tree, 1)
        self.addWidget(explorer_panel)

        details = QFrame()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setSpacing(7)

        self.case_context_title = QLabel("ACTIVE CASE")
        self.case_context_title.setObjectName("panelEyebrow")
        details_layout.addWidget(self.case_context_title)
        self.case_context_label = QLabel("No case selected")
        self.case_context_label.setWordWrap(True)
        details_layout.addWidget(self.case_context_label)
        self.device_context_label = QLabel("No media selected")
        self.device_context_label.setWordWrap(True)
        details_layout.addWidget(self.device_context_label)
        details_layout.addSpacing(6)

        account_title = QLabel("ACCOUNT")
        account_title.setObjectName("panelEyebrow")
        details_layout.addWidget(account_title)
        details_layout.addWidget(
            QLabel(f"{self.session.username}\n{self.session.role}")
        )

        account_button = QPushButton("Accounts (coming soon)")
        account_button.setEnabled(False)
        details_layout.addWidget(account_button)
        details_layout.addStretch(1)

        self.addWidget(details)
        self.setStretchFactor(0, 7)
        self.setStretchFactor(1, 3)
        self.setSizes([560, 240])

    def set_active_device(self, device):
        self.active_device = device
        self.refresh()
        self.device_context_label.setText(device.get("name", "Selected media") if device else "No media selected")

    def set_case_context(self, case_name=None):
        self.case_context_label.setText(case_name or "No case selected")

    def refresh(self):
        self.device_manager.refresh()
        self._populate_media_explorer()

    def _populate_media_explorer(self):
        self.media_tree.clear()
        devices = self.device_manager.get_devices()
        self.device_state.setText(f"Detected Media ({len(devices)})")

        for device in devices:
            media = QTreeWidgetItem([
                f"{device['name']} ({device['filesystem']})"
            ])
            media.setData(0, Qt.UserRole, device)
            media.setExpanded(device == self.active_device)

            self.media_tree.addTopLevelItem(media)
            self._populate_media_children(media, device["path"])

    def _populate_media_children(self, parent_item, current_path):
        parent_item.takeChildren()

        try:
            with os.scandir(current_path) as entries:
                for entry in list(entries)[:60]:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    label = entry.name + ("/" if is_dir else "")
                    child = QTreeWidgetItem([label])
                    child.setToolTip(0, entry.path)
                    child.setData(0, Qt.UserRole + 1, entry.path)
                    parent_item.addChild(child)

                    if is_dir:
                        child.addChild(QTreeWidgetItem(["Expand to inspect"]))

        except (OSError, KeyError):
            parent_item.addChild(
                QTreeWidgetItem(["Access denied or unavailable"])
            )

    def _populate_expanded_folder(self, item):
        path = item.data(0, Qt.UserRole + 1)

        if not path or item.data(0, Qt.UserRole + 2):
            return

        item.setData(0, Qt.UserRole + 2, True)
        self._populate_media_children(item, path)

    def _select_media(self, item, _column):
        device = item.data(0, Qt.UserRole)

        if device:
            self.device_selected.emit(device)


class WorkspaceFooter(QFrame):
    def __init__(self, active_device=None):
        super().__init__()

        self.setObjectName("globalFooter")
        self.setFixedHeight(40)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 3, 14, 3)

        self.ready_label = QLabel("Ready")
        self.device_label = QLabel("No media selected")
        self.hash_label = QLabel("Integrity: not calculated")
        self.event_label = QLabel("No active operations")

        for widget in (
            self.ready_label,
            self.device_label,
            self.hash_label,
            self.event_label,
        ):
            widget.setObjectName("globalFooterText")

        row.addWidget(self.ready_label)
        row.addStretch(1)
        row.addWidget(self.device_label)
        row.addWidget(QLabel(" | "))
        row.addWidget(self.hash_label)
        row.addStretch(1)
        row.addWidget(self.event_label)

        self.update_status(device=active_device, event="Ready")

    def update_status(self, device=None, event=None, page_hash=None):
        if device:
            self.device_label.setText(
                f"{device['name']} | {device['capacity']} | "
                f"{device.get('filesystem', 'Filesystem pending')}"
            )

        if event:
            self.ready_label.setText(
                "Working" if event.endswith("...") else "Ready"
            )
            self.event_label.setText(event)

        if page_hash is not None:
            self.hash_label.setText(f"SHA-256: {page_hash[:12]}...")
