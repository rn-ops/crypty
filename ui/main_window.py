from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crypty.core.backend import SimulatedBackend
from crypty.core.device_manager import DeviceManager
from crypty.core.recovery_engine import RecoveryEngine
from crypty.core.sanitization_engine import SanitizationEngine
from crypty.ui.dashboard import DashboardPage
from crypty.ui.devices import DevicesPage
from crypty.ui.recovery import RecoveryPage
from crypty.ui.sanitization import SanitizationPage
from crypty.ui.reports import ReportsPage
from crypty.ui.styles import APP_STYLESHEET
from crypty.ui.page_header import create_workspace_header


class CryptyMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Crypty")
        self.resize(1400, 850)
        self.setMinimumSize(1200, 760)
        self.setStyleSheet(APP_STYLESHEET)

        self.backend = SimulatedBackend()
        self.device_manager = DeviceManager(self.backend)
        self.recovery_engine = RecoveryEngine(self.backend)
        self.sanitization_engine = SanitizationEngine(self.backend)
        self.active_device = self.device_manager.get_selected_device()

        self.pages = {}
        self.current_page = None

        self._build_ui()
        self.show_page("overview")

    def set_active_device(self, device):
        self.active_device = device
        self.device_manager.set_selected_device(device)

        if "dashboard" in self.pages:
            self.pages["dashboard"] = self.pages["overview"]

        for page in self.pages.values():
            if hasattr(page, "refresh_device_context"):
                page.refresh_device_context()

    def _build_ui(self):
        central = QWidget()
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        self.sidebar = self._create_sidebar()
        central_layout.addWidget(self.sidebar, 0)

        self.content = QFrame()
        self.content.setObjectName("content")
        self.content.setStyleSheet("QFrame#content { background: #111719; }")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        self.topbar = create_workspace_header()
        self.content_layout.addWidget(self.topbar)

        central_layout.addWidget(self.content, 1)
        self.setCentralWidget(central)

        self._build_pages()

    def _create_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setStyleSheet(
            "QFrame#sidebar { background: #141a1d; border: 1px solid #2b363d; border-left: none; }"
        )
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 12, 14, 14)
        sidebar_layout.setSpacing(6)

        self.nav_buttons = {}
        for key, label in [
            ("overview", "Overview"),
            ("devices", "Evidence sources"),
            ("recovery", "Recovery"),
            ("sanitization", "Sanitization"),
            ("reports", "Reports"),
            ("audit", "Audit log"),
        ]:
            button = QPushButton(label)
            button.setProperty("nav", True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, page=key: self.show_page(page))
            button.setStyleSheet(
                "QPushButton { text-align: left; padding: 8px 10px; border: 1px solid transparent; background: transparent; font-size: 12px; font-weight: 500; } "
                "QPushButton:hover { border-color: #303b3d; background: #181e21; } "
                "QPushButton:checked { background: #1b2224; border-color: #303b3d; }"
            )
            self.nav_buttons[key] = button
            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch(1)

        footer = QFrame()
        footer.setStyleSheet("border-top: 1px solid #2b363d; padding-top: 10px;")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(0, 6, 0, 0)
        footer_layout.setSpacing(2)

        footer_layout.addWidget(QLabel("Crypty"))
        footer_layout.addWidget(QLabel("Read-only demonstration environment"))
        footer_layout.addWidget(QLabel("Storage writes disabled"))
        sidebar_layout.addWidget(footer)

        return sidebar

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
            button.setStyleSheet(
                "QPushButton { text-align: left; padding: 8px 10px; border: 1px solid transparent; background: transparent; font-size: 12px; font-weight: 500; } "
                "QPushButton:hover { border-color: #303b3d; background: #181e21; } "
                "QPushButton:checked { background: #1b2224; border-color: #303b3d; }"
            )
            if key == page_name:
                button.setStyleSheet(
                    "QPushButton { text-align: left; padding: 8px 10px; border: 1px solid #303b3d; background: #1b2224; font-size: 12px; font-weight: 500; } "
                    "QPushButton:hover { border-color: #303b3d; background: #1b2224; }"
                )

        if hasattr(self.pages[page_name], "on_show"):
            self.pages[page_name].on_show()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)
    main_window = CryptyMainWindow()
    main_window.show()
    sys.exit(app.exec())
