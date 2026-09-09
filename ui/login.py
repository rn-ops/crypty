from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from auth_client import AuthClient, AuthenticationError, AuthSession


class LoginDialog(QDialog):
    def __init__(self, client: AuthClient, parent=None):
        super().__init__(parent)
        self.client = client
        self.session: AuthSession | None = None
        self.setWindowTitle("Crypty sign in")
        self.setModal(True)
        self.setMinimumWidth(360)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Sign in to Crypty")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)

        self.status = QLabel("Use your Crypty account.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #9aa5a1; font-size: 11px;")
        layout.addWidget(self.status)

        form = QFormLayout()
        self.username = QLineEdit()
        self.username.setObjectName("usernameInput")
        self.username.setPlaceholderText("Username")
        self.password = QLineEdit()
        self.password.setObjectName("passwordInput")
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)
        self.password.returnPressed.connect(self._login)
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._login)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.username.setFocus()

    def _login(self):
        username = self.username.text().strip()
        password = self.password.text()
        if not username:
            self.status.setText("Username is required.")
            self.status.setStyleSheet("color: #e5a6a6; font-size: 11px;")
            self.username.setFocus()
            return
        if not password:
            self.status.setText("Password is required.")
            self.status.setStyleSheet("color: #e5a6a6; font-size: 11px;")
            self.password.setFocus()
            return

        self.setEnabled(False)
        self.status.setText("Authenticating...")
        try:
            self.session = self.client.login(username, password)
        except AuthenticationError as error:
            self.status.setText(str(error))
            self.status.setStyleSheet("color: #e5a6a6; font-size: 11px;")
            self.setEnabled(True)
            self.password.setFocus()
            return
        self.accept()