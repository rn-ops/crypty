from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFrame, QMainWindow, QMessageBox, QSplitter, QVBoxLayout, QWidget

from auth_client import AuthClient, AuthSession, AuthenticationError
from core.native_backend import NativeBackend
from core.device_manager import DeviceManager
from core.recovery_engine import RecoveryEngine
from core.sanitization_engine import SanitizationEngine
from ui.dashboard.dashboard import DashboardPage
from ui.dashboard.devices import DevicesPage
from ui.dashboard.recovery import RecoveryPage
from ui.dashboard.sanitization import SanitizationPage
from ui.dashboard.reports import ReportsPage
from ui.dashboard.cases import CasesPage
from ui.dashboard.evidence import EvidencePage
from ui.dashboard.settings import SettingsPage
from ui.styles import APP_STYLESHEET
from ui.dashboard.shared_elements import WorkspaceHeader, MediaSidebar, WorkspaceFooter


class CryptyMainWindow(QMainWindow):
    def __init__(self, session: AuthSession):
        super().__init__()
        self.session = session
        self.setWindowTitle("Crypty — Avant Forensics Workbench")
        self.resize(1450, 900)
        self.setMinimumSize(900, 620)
        self.setStyleSheet(APP_STYLESHEET)

        self.auth_client = AuthClient()
        self.backend = NativeBackend()
        self.device_manager = DeviceManager(self.backend)
        self.recovery_engine = RecoveryEngine(self.backend)
        self.sanitization_engine = SanitizationEngine(self.backend)
        self.active_device = self.device_manager.get_selected_device()
        self.active_case = None
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
        self.topbar.media_explorer_requested.connect(self.toggle_media_explorer)
        self.nav_buttons = self.topbar.nav_buttons
        root.addWidget(self.topbar)

        body = QSplitter(Qt.Horizontal)
        body.setChildrenCollapsible(False)
        body.setHandleWidth(5)
        self.body_splitter = body
        self.sidebar = MediaSidebar(
            self.session,
            self.device_manager,
            self.active_device,
            self.auth_client,
        )
        self.sidebar.device_selected.connect(self.set_active_device)
        self.sidebar.hide()
        body.addWidget(self.sidebar)

        self.content = QFrame()
        self.content.setObjectName("content")
        self.content.setStyleSheet("QFrame#content { background: #111112; }")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        body.addWidget(self.content)
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 1)
        body.setSizes([320, 1130])
        root.addWidget(body, 1)

        self.footer = WorkspaceFooter(self.active_device)
        root.addWidget(self.footer)
        self.setCentralWidget(central)
        self._build_pages()

    def _build_pages(self):
        self.pages["overview"] = DashboardPage(self)
        self.pages["cases"] = CasesPage(self)
        self.pages["devices"] = DevicesPage(self)
        self.pages["recovery"] = RecoveryPage(self)
        self.pages["sanitization"] = SanitizationPage(self)
        self.pages["evidence"] = EvidencePage(self)
        self.pages["settings"] = SettingsPage(self)
        self.pages["reports"] = ReportsPage(self)
        self.pages["audit"] = ReportsPage(self, audit_only=True)
        for page in self.pages.values():
            self.content_layout.addWidget(page)
            page.hide()

    def toggle_media_explorer(self):
        if self.sidebar.isVisible():
            self.sidebar.hide()
            return
        self.sidebar.refresh()
        self.sidebar.set_active_device(self.active_device)
        self.sidebar.set_case_context(self.active_case.get("name") if self.active_case else None)
        self.sidebar.show()
        self.body_splitter.setSizes([320, max(900, self.width() - 320)])

    def set_active_case(self, case):
        self.active_case = case
        name = case.get("name") if case else None
        self.topbar.set_active_case(name)
        self.sidebar.set_case_context(name)
        if "cases" in self.pages and hasattr(self.pages["cases"], "_sync_context"):
            self.pages["cases"]._sync_context()
        if "evidence" in self.pages and hasattr(self.pages["evidence"], "on_show"):
            self.pages["evidence"].on_show()
        if case:
            self._record_audit_event("CASE_SELECTED", f"Selected case '{name}'.", case=case)

    def set_active_device(self, device):
        self.active_device = device
        self.device_manager.set_selected_device(device)
        self.footer.update_status(device=device, event="Device selected")
        self.sidebar.set_active_device(device)
        cases_page = self.pages.get("cases")
        if cases_page and hasattr(cases_page, "_sync_context"):
            cases_page._sync_context()
        for page in self.pages.values():
            if hasattr(page, "refresh_device_context"):
                page.refresh_device_context()
        if device and self.active_case:
            try:
                fingerprint = self.auth_client.device_fingerprint(device)
                attached = {
                    item.get("identity")
                    for item in self.active_case.get("devices", [])
                }
                if fingerprint in attached:
                    self._record_audit_event(
                        "DEVICE_SELECTED",
                        f"Selected device '{device.get('name', 'Unnamed media')}'.",
                        case=self.active_case,
                        device_fingerprint=fingerprint,
                    )
            except ValueError as error:
                QMessageBox.warning(self, "Audit event not recorded", str(error))

    def _record_audit_event(
        self,
        action: str,
        details: str,
        case: dict | None = None,
        device_fingerprint: str | None = None,
    ):
        try:
            self.record_audit_event(
                action, details, case=case, device_fingerprint=device_fingerprint
            )
        except (AuthenticationError, ValueError) as error:
            QMessageBox.warning(
                self,
                "Audit event not recorded",
                str(error),
            )

    def record_audit_event(
        self,
        action: str,
        details: str,
        case: dict | None = None,
        device_fingerprint: str | None = None,
    ):
        self.auth_client.record_audit_event(
            self.session,
            action,
            details,
            case=case,
            device_fingerprint=device_fingerprint,
        )

    def report_evidence_page(self, page_hash, event):
        self.footer.update_status(event=event, page_hash=page_hash)

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
