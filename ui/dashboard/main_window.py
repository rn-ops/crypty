from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from auth_client import AuthSession
from core.native_backend import NativeBackend
from core.device_manager import DeviceManager
from core.recovery_engine import RecoveryEngine
from core.sanitization_engine import SanitizationEngine
from ui.dashboard.dashboard import DashboardPage
from ui.dashboard.devices import DevicesPage
from ui.dashboard.recovery import RecoveryPage
from ui.dashboard.sanitization import SanitizationPage
from ui.dashboard.reports import ReportsPage
from ui.styles import APP_STYLESHEET
from ui.dashboard.shared_elements import (
    WorkspaceHeader,
    MediaSidebar,
    WorkspaceFooter,
)
"""
`__init__()`
Keep
Initializes the window and its dependencies.

`_build_ui()`
Keep
Assembles the shared components into the application layout.

`_build_pages()`
Keep
Registers and places the feature pages in the content area.

`show_page()`
Keep
Controls which page is visible. This is application-level navigation.

`set_active_device()`
Keep for now
Coordinates a global selection change across the sidebar, footer, and pages.
    I would keep this method exactly where it is for now.
    Why? Selecting a device affects several parts of the application:
        - DeviceManager stores the selection.
        - WorkspaceFooter displays the selected device.
        - MediaSidebar updates its expanded device.
        - Pages such as DashboardPage and DevicesPage refresh their displayed information.
    The main window coordinates these changes.
    That is a legitimate responsibility for an application shell, not unnecessary complexity.
    There is one possible improvement: the method refreshes every page, including hidden pages.
                                        But that is not automatically a problem, and changing it now could introduce stale information when switching pages.
                                        Let's leave it alone.

`report_evidence_page()`
Investigate
A callback for reporting operation status. Its callers determine where it belongs.
"""
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

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.topbar = WorkspaceHeader()
        self.topbar.page_selected.connect(self.show_page)
        self.nav_buttons = self.topbar.nav_buttons
        root.addWidget(self.topbar)
        body = QSplitter(Qt.Horizontal)
        body.setChildrenCollapsible(False)
        body.setHandleWidth(6)
        self.sidebar = MediaSidebar(
            self.session,
            self.device_manager,
            self.active_device,
        )
        self.sidebar.device_selected.connect(self.set_active_device)
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
        self.footer = WorkspaceFooter(self.active_device)
        root.addWidget(self.footer)
        self.setCentralWidget(central)
        self._build_pages()

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

    def set_active_device(self, device):
        self.active_device = device
        self.device_manager.set_selected_device(device)
        self.footer.update_status(
            device=device,
            event="Device selected",
        )
        self.sidebar.set_active_device(device)

        for page in self.pages.values():
            if hasattr(page, "refresh_device_context"):
                page.refresh_device_context()

    def report_evidence_page(self, page_hash, event):
        self.footer.update_status(
            event=event,
            page_hash=page_hash,
        )

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
