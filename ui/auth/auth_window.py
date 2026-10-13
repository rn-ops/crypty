from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from auth_client import AuthClient, AuthSession
from ui.styles import APP_STYLESHEET


# Keep these local object-name styles scoped to the authentication window.
# The rest of Crypty continues to use ui/styles.py.
AUTH_STYLESHEET = """
QMainWindow#authWindow { background: #121517; }
QFrame#authShell { background: #171c1f; border: 1px solid #2b363d; }
QFrame#authLeft { background: #171c1f; border: none; }
QFrame#authRight { background: #14191c; border-left: 1px solid #2b363d; }
QFrame#brandMark {
    background: #829b92; border: none; border-radius: 8px;
}
QLabel#brandGlyph { color: #18201f; font-size: 20px; font-weight: 800; }
QLabel#brandName { color: #edf1ef; font-size: 22px; font-weight: 700; }
QLabel#eyebrow { color: #9db2a9; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLabel#heroTitle { color: #edf1ef; font-size: 29px; font-weight: 650; }
QLabel#bodyCopy { color: #9aa5a1; font-size: 12px; }
QLabel#fieldLabel { color: #cbd4d0; font-size: 11px; font-weight: 600; }
QLabel#statusLabel { color: #9aa5a1; font-size: 11px; }
QPushButton#modeButton {
    background: transparent; border: 1px solid #2b363d; color: #9aa5a1;
    padding: 9px 14px; min-height: 22px; font-weight: 600;
}
QPushButton#modeButton:checked {
    background: #222b31; border-color: #829b92; color: #edf1ef;
}
QPushButton#primaryButton {
    background: #829b92; color: #18201f; border: 1px solid #829b92;
    padding: 11px 14px; min-height: 24px; font-weight: 700;
}
QPushButton#primaryButton:hover { background: #9db2a9; border-color: #9db2a9; }
QPushButton#quietButton {
    background: transparent; border: 1px solid #2b363d; color: #cbd4d0;
    padding: 8px 12px; min-height: 22px;
}
QPushButton#quietButton:hover { border-color: #829b92; }
QLineEdit#authInput {
    background: #12191d; border: 1px solid #34434a; border-radius: 4px;
    color: #edf1ef; padding: 10px 11px; min-height: 20px;
}
QLineEdit#authInput:focus { border-color: #829b92; }
QListWidget#savedAccounts {
    background: transparent; border: none; outline: none;
    color: #edf1ef; padding: 0px;
}
QListWidget#savedAccounts::item {
    background: #1a2025; border: 1px solid #2b363d; border-radius: 5px;
    padding: 12px; margin: 4px 0px;
}
QListWidget#savedAccounts::item:selected {
    background: #222b31; border: 1px solid #829b92;
}
QLabel#accountInitial {
    background: #26332f; color: #9db2a9; border: 1px solid #3c5149;
    border-radius: 17px; font-size: 13px; font-weight: 700;
}
QFrame#servicePill { background: #1a2025; border: 1px solid #2b363d; border-radius: 4px; }
"""

class AuthWindow(QMainWindow):
    """Single-window Crypty authentication experience.

    Emits ``authenticated(AuthSession)`` after a successful API login.
    Saved accounts store usernames only; passwords and JWTs are never persisted.
    """

    authenticated = Signal(object)

    def __init__(self, client: AuthClient, parent=None):
        super().__init__(parent)
        self.client = client
        self.session: AuthSession | None = None
        self.settings = QSettings("Crypty", "Crypty")
        self.setObjectName("authWindow")
        self.setWindowTitle("Crypty · Sign in")
        self.setMinimumSize(980, 650)
        self.resize(1120, 720)
        self.setStyleSheet(APP_STYLESHEET + AUTH_STYLESHEET)
        self._build_ui()
        self._load_saved_accounts()
        self._set_mode("login")

    def _build_ui(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("authShell")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        # Left: authentication forms.
        left = QFrame()
        left.setObjectName("authLeft")
        left.setMinimumWidth(520)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(46, 36, 46, 34)
        left_layout.setSpacing(0)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        mark = QFrame()
        mark.setObjectName("brandMark")
        mark.setFixedSize(42, 42)
        mark_layout = QVBoxLayout(mark)
        mark_layout.setContentsMargins(0, 0, 0, 0)
        glyph = QLabel("C")
        glyph.setObjectName("brandGlyph")
        glyph.setAlignment(Qt.AlignCenter)
        mark_layout.addWidget(glyph)
        brand_row.addWidget(mark)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        brand = QLabel("CRYPTY")
        brand.setObjectName("brandName")
        tagline = QLabel("DIGITAL FORENSICS WORKSPACE")
        tagline.setObjectName("eyebrow")
        brand_text.addWidget(brand)
        brand_text.addWidget(tagline)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        left_layout.addLayout(brand_row)
        left_layout.addSpacing(54)

        eyebrow = QLabel("SECURE WORKSPACE ACCESS")
        eyebrow.setObjectName("eyebrow")
        left_layout.addWidget(eyebrow)
        left_layout.addSpacing(10)

        self.hero_title = QLabel("Welcome back.")
        self.hero_title.setObjectName("heroTitle")
        left_layout.addWidget(self.hero_title)
        left_layout.addSpacing(7)

        self.hero_copy = QLabel("Sign in to continue to your forensic workspace.")
        self.hero_copy.setObjectName("bodyCopy")
        self.hero_copy.setWordWrap(True)
        left_layout.addWidget(self.hero_copy)
        left_layout.addSpacing(27)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        self.login_mode_button = QPushButton("Sign in")
        self.login_mode_button.setObjectName("modeButton")
        self.login_mode_button.setCheckable(True)
        self.register_mode_button = QPushButton("Register")
        self.register_mode_button.setObjectName("modeButton")
        self.register_mode_button.setCheckable(True)
        self.login_mode_button.clicked.connect(lambda: self._set_mode("login"))
        self.register_mode_button.clicked.connect(lambda: self._set_mode("register"))
        mode_row.addWidget(self.login_mode_button)
        mode_row.addWidget(self.register_mode_button)
        mode_row.addStretch(1)
        left_layout.addLayout(mode_row)
        left_layout.addSpacing(23)

        self.forms = QStackedWidget()
        self.forms.addWidget(self._build_login_form())
        self.forms.addWidget(self._build_register_form())
        left_layout.addWidget(self.forms)
        left_layout.addStretch(1)

        self.status_label = QLabel("AUTH SERVICE  ·  Waiting for sign-in")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        left_layout.addWidget(self.status_label)

        # Right: saved accounts and service status.
        right = QFrame()
        right.setObjectName("authRight")
        right.setMinimumWidth(300)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(28, 36, 28, 30)
        right_layout.setSpacing(0)

        right_eyebrow = QLabel("QUICK ACCESS")
        right_eyebrow.setObjectName("eyebrow")
        right_layout.addWidget(right_eyebrow)
        right_layout.addSpacing(10)

        saved_title = QLabel("Saved accounts")
        saved_title.setStyleSheet("font-size: 20px; font-weight: 650;")
        right_layout.addWidget(saved_title)
        right_layout.addSpacing(6)

        saved_copy = QLabel("Choose an account to fill its username.")
        saved_copy.setObjectName("bodyCopy")
        saved_copy.setWordWrap(True)
        right_layout.addWidget(saved_copy)
        right_layout.addSpacing(20)

        self.saved_accounts = QListWidget()
        self.saved_accounts.setObjectName("savedAccounts")
        self.saved_accounts.itemClicked.connect(self._select_saved_account)
        right_layout.addWidget(self.saved_accounts, 1)

        self.no_accounts_label = QLabel("No saved accounts yet.\nSuccessful sign-ins appear here.")
        self.no_accounts_label.setObjectName("bodyCopy")
        self.no_accounts_label.setAlignment(Qt.AlignCenter)
        self.no_accounts_label.setWordWrap(True)
        right_layout.addWidget(self.no_accounts_label)
        right_layout.addSpacing(24)

        service_pill = QFrame()
        service_pill.setObjectName("servicePill")
        service_layout = QVBoxLayout(service_pill)
        service_layout.setContentsMargins(12, 11, 12, 11)
        service_layout.setSpacing(5)
        service_head = QLabel("SERVICE ENDPOINT")
        service_head.setObjectName("eyebrow")
        service_value = QLabel(self.client.base_url)
        service_value.setStyleSheet("font-family: Consolas; font-size: 11px; color: #cbd4d0;")
        service_value.setWordWrap(True)
        service_layout.addWidget(service_head)
        service_layout.addWidget(service_value)
        right_layout.addWidget(service_pill)
        right_layout.addSpacing(14)

        footer = QLabel("CRYPTY  /  AUTHENTICATION")
        footer.setObjectName("eyebrow")
        right_layout.addWidget(footer)

        shell_layout.addWidget(left, 3)
        shell_layout.addWidget(right, 2)
        outer.addWidget(shell)
        self.setCentralWidget(central)

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setObjectName("fieldLabel")
        return label

    def _build_login_form(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)

        layout.addWidget(self._field_label("Username"))
        self.username_input = QLineEdit()
        self.username_input.setObjectName("authInput")
        self.username_input.setPlaceholderText("Enter your username")
        self.username_input.setClearButtonEnabled(True)
        layout.addWidget(self.username_input)
        layout.addSpacing(8)

        layout.addWidget(self._field_label("Password"))
        self.password_input = QLineEdit()
        self.password_input.setObjectName("authInput")
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self._login)
        layout.addWidget(self.password_input)
        layout.addSpacing(20)

        self.login_button = QPushButton("Sign in to Crypty  →")
        self.login_button.setObjectName("primaryButton")
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.clicked.connect(self._login)
        layout.addWidget(self.login_button)

        hint = QLabel("Your credentials are sent to the configured Crypty auth service.")
        hint.setObjectName("bodyCopy")
        hint.setWordWrap(True)
        layout.addSpacing(9)
        layout.addWidget(hint)
        return page

    def _build_register_form(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)

        notice = QFrame()
        notice.setObjectName("servicePill")
        notice_layout = QVBoxLayout(notice)
        notice_layout.setContentsMargins(14, 13, 14, 13)
        notice_layout.setSpacing(6)
        notice_title = QLabel("Administrator-managed accounts")
        notice_title.setStyleSheet("font-size: 13px; font-weight: 650;")
        notice_text = QLabel(
            "Crypty's current API exposes account creation through an admin-only "
            "endpoint. Sign in with an administrator account to provision users; "
            "public self-registration is not enabled."
        )
        notice_text.setObjectName("bodyCopy")
        notice_text.setWordWrap(True)
        notice_layout.addWidget(notice_title)
        notice_layout.addWidget(notice_text)
        layout.addWidget(notice)
        layout.addSpacing(8)

        self.register_username = QLineEdit()
        self.register_username.setObjectName("authInput")
        self.register_username.setPlaceholderText("New username")
        layout.addWidget(self._field_label("New username"))
        layout.addWidget(self.register_username)

        self.register_password = QLineEdit()
        self.register_password.setObjectName("authInput")
        self.register_password.setPlaceholderText("New password")
        self.register_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self._field_label("New password"))
        layout.addWidget(self.register_password)

        self.register_button = QPushButton("Account creation requires admin API integration")
        self.register_button.setObjectName("quietButton")
        self.register_button.setEnabled(False)
        layout.addSpacing(10)
        layout.addWidget(self.register_button)
        return page

    def _set_mode(self, mode: str):
        is_login = mode == "login"
        self.forms.setCurrentIndex(0 if is_login else 1)
        self.login_mode_button.setChecked(is_login)
        self.register_mode_button.setChecked(not is_login)

        self.hero_title.setText("Welcome back." if is_login else "Create an account.")
        self.hero_copy.setText(
            "Sign in to continue to your forensic workspace."
            if is_login
            else "User accounts are provisioned by an authenticated administrator."
        )
        self.status_label.setText(
            "AUTH SERVICE  ·  Ready for sign-in"
            if is_login
            else "ACCOUNT PROVISIONING  ·  Admin authorization required"
        )
        if is_login:
            self.username_input.setFocus()

    def _login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username:
            self._set_status("Enter your username.", error=True)
            self.username_input.setFocus()
            return
        if not password:
            self._set_status("Enter your password.", error=True)
            self.password_input.setFocus()
            return

        self.login_button.setEnabled(False)
        self.login_button.setText("Authenticating…")
        self._set_status("Contacting authentication service…")

        try:
            session = self.client.login(username, password)
        except Exception as error:
            # AuthClient raises AuthenticationError for expected API/network failures.
            self._set_status(str(error), error=True)
            self.password_input.clear()
            self.password_input.setFocus()
            return
        finally:
            self.login_button.setEnabled(True)
            self.login_button.setText("Sign in to Crypty  →")

        self.session = session
        self._remember_account(username)
        self._set_status(f"Authenticated as {session.username} · {session.role}", success=True)
        self.authenticated.emit(session)

    def _set_status(self, message: str, *, error=False, success=False):
        color = "#d77c69" if error else "#7db88a" if success else "#9aa5a1"
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.status_label.setText(message)

    def _load_saved_accounts(self):
        accounts = self.settings.value("auth/saved_usernames", [], type=list)
        self.saved_accounts.clear()
        for username in accounts:
            if not isinstance(username, str) or not username.strip():
                continue
            item = QListWidgetItem()
            item.setText(f"  {username}\n  Saved Crypty account")
            item.setData(Qt.UserRole, username)
            self.saved_accounts.addItem(item)
            item.setSizeHint(item.sizeHint())
        self.no_accounts_label.setVisible(self.saved_accounts.count() == 0)

    def _remember_account(self, username: str):
        accounts = self.settings.value("auth/saved_usernames", [], type=list)
        accounts = [item for item in accounts if isinstance(item, str) and item != username]
        accounts.insert(0, username)
        self.settings.setValue("auth/saved_usernames", accounts[:8])
        self._load_saved_accounts()

    def _select_saved_account(self, item: QListWidgetItem):
        username = item.data(Qt.UserRole)
        if not username:
            return
        self._set_mode("login")
        self.username_input.setText(username)
        self.password_input.setFocus()
