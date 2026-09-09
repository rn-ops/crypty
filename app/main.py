import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from auth_client import AuthClient
from ui.login import LoginDialog
from ui.main_window import CryptyMainWindow


def resource_path(relative_path: str) -> Path:
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return bundle_root / relative_path


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Crypty")
    app.setOrganizationName("Crypty")
    icon_path = resource_path("resources/crypty.ico")
    app.setWindowIcon(QIcon(str(icon_path)))

    login = LoginDialog(AuthClient())
    if login.exec() != LoginDialog.Accepted or login.session is None:
        return 0

    window = CryptyMainWindow(login.session)
    window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
