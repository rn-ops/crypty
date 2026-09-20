from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget)

from auth_client import AuthSession
from core.native_backend import NativeBackend
from core.device_manager import DeviceManager
from core.recovery_engine import RecoveryEngine
from core.sanitization_engine import SanitizationEngine
from ui.dashboard import DashboardPage
from ui.devices import DevicesPage
from ui.recovery import RecoveryPage
from ui.sanitization import SanitizationPage
from ui.reports import ReportsPage
from ui.styles import APP_STYLESHEET
from ui.page_header import create_workspace_header


class CryptyMainWindow(QMainWindow):
    def __init__(self, session: AuthSession):
        super().__init__()
        self.session = session
        self.setWindowTitle("Crypty")
        self.resize(1400, 850)
        self.setMinimumSize(1200, 760)
        self.setStyleSheet(APP_STYLESHEET)
        self.backend = NativeBackend()
        self.device_manager = DeviceManager(self.backend)
        self.recovery_engine = RecoveryEngine(self.backend)
        self.sanitization_engine = SanitizationEngine(self.backend)
        self.active_device = self.device_manager.get_selected_device()
        self.pages, self.nav_buttons, self.current_page = {}, {}, None
        self._build_ui()
        self.show_page("overview")

    def set_active_device(self, device):
        self.active_device = device
        self.device_manager.set_selected_device(device)
        self._update_footer(device=device, event="Device selected")
        self._populate_media_explorer()
        for page in self.pages.values():
            if hasattr(page, "refresh_device_context"):
                page.refresh_device_context()

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.topbar = create_workspace_header()
        root.addWidget(self.topbar)
        self._add_header_navigation()
        body = QSplitter(Qt.Horizontal)
        body.setChildrenCollapsible(False)
        body.setHandleWidth(6)
        self.sidebar = self._create_media_sidebar()
        body.addWidget(self.sidebar)
        self.content = QFrame()
        self.content.setObjectName("content")
        self.content.setStyleSheet("QFrame#content { background: #111719; }")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        body.addWidget(self.content)
        body.setStretchFactor(0, 1)
        body.setStretchFactor(1, 5)
        body.setSizes([180, 1220])
        root.addWidget(body, 1)
        self.footer = self._create_footer()
        root.addWidget(self.footer)
        self.setCentralWidget(central)
        self._build_pages()

    def _create_footer(self):
        footer = QFrame()
        footer.setObjectName("globalFooter")
        footer.setFixedHeight(40)
        row = QHBoxLayout(footer)
        row.setContentsMargins(14, 3, 14, 3)
        self.footer_ready = QLabel("Ready")
        self.footer_device = QLabel("No media selected")
        self.footer_hash = QLabel("SHA-256: pending")
        self.footer_event = QLabel("No active operations")
        for widget in (self.footer_ready, self.footer_device, self.footer_hash, self.footer_event):
            widget.setObjectName("globalFooterText")
        row.addWidget(self.footer_ready)
        row.addStretch(1)
        row.addWidget(self.footer_device)
        row.addWidget(QLabel(" | "))
        row.addWidget(self.footer_hash)
        row.addStretch(1)
        row.addWidget(self.footer_event)
        self._update_footer(device=self.active_device, event="Ready")
        return footer

    def _update_footer(self, device=None, event=None, page_hash=None):
        if device:
            self.footer_device.setText(
                f"{device['name']} | {device['capacity']} | {device['filesystem']} | Read-only"
            )
        if event:
            self.footer_ready.setText("Working" if event.endswith("...") else "Ready")
            self.footer_event.setText(event)
        if page_hash is not None:
            self.footer_hash.setText(f"SHA-256: {page_hash[:12]}...")

    def report_evidence_page(self, page_hash, event):
        self._update_footer(event=event, page_hash=page_hash)

    def _add_header_navigation(self):
        labels = [("overview", "Overview"), ("devices", "Evidence"),
                  ("recovery", "Recovery"), ("sanitization", "Sanitization"),
                  ("reports", "Reports"), ("audit", "Audit")]
        header_layout = self.topbar.layout()
        for key, label in reversed(labels):
            button = QPushButton(label)
            button.setObjectName("headerNav")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, page=key: self.show_page(page))
            header_layout.insertWidget(1, button)
            self.nav_buttons[key] = button

    def _create_media_sidebar(self):
        sidebar = QSplitter(Qt.Vertical)
        sidebar.setObjectName("mediaSidebar")
        sidebar.setChildrenCollapsible(False)
        sidebar.setHandleWidth(6)
        
        explorer_panel = QFrame()
        explorer_layout = QVBoxLayout(explorer_panel)
        explorer_layout.setContentsMargins(10, 12, 10, 8)
        explorer_layout.setSpacing(6)
        
        # --- NEW ROW: MEDIA EXPLORER LABEL + STICKY REFRESH BUTTON ---
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(0)
        
        title = QLabel("MEDIA EXPLORER")
        title.setObjectName("panelEyebrow")
        title.setStyleSheet("color: #94a3b8; font-size: 12px; margin-top: 2px;")
        header_row.addWidget(title)
        
        # Pushes the button to the absolute right of the header line
        header_row.addStretch(1)
        
        # Small working reload button attached to the right edge of the header row
        self.refresh_explorer_btn = QPushButton("↻")
        self.refresh_explorer_btn.setToolTip("Rescan hardware and hot-load new media drives")
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
        self.refresh_explorer_btn.clicked.connect(self._handle_media_refresh)
        header_row.addWidget(self.refresh_explorer_btn)
        explorer_layout.addLayout(header_row)
        
        # --- SECOND ROW: DETECTED MEDIA SUB-LABEL ---
        self.device_state = QLabel("Detected Media")
        self.device_state.setStyleSheet("color: #94a3b8; font-size: 14px; margin-top: 2px; margin-bottom: 4px;")
        explorer_layout.addWidget(self.device_state)
        # --------------------------------------------------------------
        
        self.media_tree = QTreeWidget()
        self.media_tree.setHeaderHidden(True)
        self.media_tree.setObjectName("mediaTree")
        self.media_tree.itemClicked.connect(self._select_media)
        self.media_tree.itemExpanded.connect(self._populate_expanded_folder)
        
        # Compact tree overrides with fully restored XML namespace strings
        self.media_tree.setIndentation(16)
        self.media_tree.setStyleSheet("""
            QTreeView#mediaTree { background-color: transparent; outline: 0; }
            QTreeView#mediaTree::item { padding-top: 5px; padding-bottom: 5px; padding-left: 4px; border-bottom: 1px solid #1e292b; }
            QTreeView#mediaTree::branch { background: transparent; width: 16px; border-bottom: 1px solid #1e292b; }
            QTreeView#mediaTree::branch:has-siblings:!adjoins-item { border-right: 1px dotted #334155; }
            QTreeView#mediaTree::branch:has-siblings:adjoins-item { border-right: 1px dotted #334155; }
            QTreeView#mediaTree::branch:!has-siblings:adjoins-item { border-right: 1px dotted #334155; }
            
            QTreeView#mediaTree::branch:has-children:closed {
                image: url("data:image/svg+xml,%3Csvg xmlns='http://w3.org' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='9 18 15 12 9 6'%3E%3C/polyline%3E%3C/svg%3E");
            }
            QTreeView#mediaTree::branch:has-children:open {
                image: url("data:image/svg+xml,%3Csvg xmlns='http://w3.org' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%2364748b' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
            }
        """)
        
        explorer_layout.addWidget(self.media_tree, 1)
        sidebar.addWidget(explorer_panel)
        
        details = QFrame()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setSpacing(7)
        
        case_title = QLabel("CASE PROPERTIES")
        case_title.setObjectName("panelEyebrow")
        details_layout.addWidget(case_title)
        details_layout.addWidget(QLabel("Case: CRYPTY-001"))
        details_layout.addWidget(QLabel("Status: Open"))
        details_layout.addWidget(QLabel("Evidence: Read-only"))
        details_layout.addSpacing(6)
        
        account_title = QLabel("ACCOUNT")
        account_title.setObjectName("panelEyebrow")
        details_layout.addWidget(account_title)
        details_layout.addWidget(QLabel(f"{self.session.username}\n{self.session.role}"))
        
        account_button = QPushButton("Accounts (coming soon)")
        account_button.setEnabled(False)
        details_layout.addWidget(account_button)
        details_layout.addStretch(1)
        
        sidebar.addWidget(details)
        sidebar.setStretchFactor(0, 7)
        sidebar.setStretchFactor(1, 3)
        sidebar.setSizes([560, 240])
        
        self._populate_media_explorer()
        return sidebar

    def _handle_media_refresh(self):
        """Flushes current items, prompts backend hardware scan, and updates the explorer UI tree."""
        self.media_tree.clear()
        if hasattr(self, 'device_manager') and hasattr(self.device_manager, 'refresh'):
            self.device_manager.refresh()
        elif hasattr(self, 'main_window') and hasattr(self.main_window, 'device_manager'):
            if hasattr(self.main_window.device_manager, 'refresh'):
                self.main_window.device_manager.refresh()
        self._populate_media_explorer()

    def _populate_media_explorer(self):
        """Builds top-level container node and enumerates active device elements."""
        if not hasattr(self, "media_tree"):
            return
        self.media_tree.clear()
        
        devices = self.device_manager.get_devices() if hasattr(self, 'device_manager') else []
        if not devices and hasattr(self, 'main_window') and hasattr(self.main_window, 'device_manager'):
            devices = self.main_window.device_manager.get_devices()
            
        self.device_state.setText(f"Detected Media ({len(devices)})")
        
        for device in devices:
            media = QTreeWidgetItem([f"{device['name']} ({device['filesystem']})"])
            media.setData(0, Qt.UserRole, device)
            
            has_active = hasattr(self, 'active_device') and device == self.active_device
            media.setExpanded(has_active)
            
            self.media_tree.addTopLevelItem(media)
            self._populate_media_children(media, device["path"])

    def _populate_media_children(self, parent_item, current_path):
        """Populate exactly one folder level; deeper levels load on expansion."""
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
            parent_item.addChild(QTreeWidgetItem(["Access denied or unavailable"]))


    def _populate_expanded_folder(self, item):
        """Load a directory only when the examiner asks to expand it."""
        path = item.data(0, Qt.UserRole + 1)
        if not path or item.data(0, Qt.UserRole + 2):
            return
        item.setData(0, Qt.UserRole + 2, True)
        self._populate_media_children(item, path)

    def _select_media(self, item, _column):
        device = item.data(0, Qt.UserRole)
        if device:
            self.set_active_device(device)

    def _build_pages(self):
        self.pages["overview"] = DashboardPage(self)
        self.pages["devices"] = DevicesPage(self)
        self.pages["recovery"] = RecoveryPage(self)
        self.pages["sanitization"] = SanitizationPage(self)
        self.pages["reports"] = ReportsPage(self)
        self.pages["audit"] = ReportsPage(self, audit_only=True)
        for page in self.pages.values():
            self.content_layout.addWidget(page)
            page.hide()

    def show_page(self, page_name: str):
        if page_name not in self.pages:
            return
        for name, page in self.pages.items():
            page.setVisible(name == page_name)
        self.current_page = page_name
        for key, button in self.nav_buttons.items():
            button.setProperty("active", key == page_name)
            button.style().unpolish(button)
            button.style().polish(button)
        if hasattr(self.pages[page_name], "on_show"):
            self.pages[page_name].on_show()


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    raise SystemExit(app.exec())
