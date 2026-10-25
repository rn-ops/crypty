import os
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from auth_client import AuthClient, AuthSession
from ui.auth.auth_window import AuthWindow
from ui.dashboard.main_window import CryptyMainWindow


# Development convenience only. Keep disabled for real builds.
DEV_AUTH_BYPASS = True

def resource_path(relative_path: str) -> Path:
    bundle_root = Path(
        getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1])
    )
    return bundle_root / relative_path


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Crypty")
    app.setOrganizationName("Crypty")

    icon_path = resource_path("resources/crypty.ico")
    app.setWindowIcon(QIcon(str(icon_path)))

    auth_client = AuthClient()

    auth_window = AuthWindow(auth_client)
    auth_window.setWindowIcon(QIcon(str(icon_path)))

    main_window = None

    def open_workspace(session: AuthSession):
        nonlocal main_window

        main_window = CryptyMainWindow(session)
        main_window.setWindowIcon(QIcon(str(icon_path)))
        main_window.show()

        auth_window.close()

    auth_window.authenticated.connect(open_workspace)

    if DEV_AUTH_BYPASS:
        # Never send hardcoded credentials to the API.
        # Do not enable this in production builds.
        session = AuthSession(
            username="admin1",
            role="admin",
            token="a",
        )
        open_workspace(session)
    else:
        auth_window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
