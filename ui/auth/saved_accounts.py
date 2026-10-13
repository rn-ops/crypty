"""Saved-account helpers for Crypty.

The initial implementation stores usernames only through QSettings.
Do not add plaintext passwords or access tokens to this store.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings


class SavedAccountStore:
    def __init__(self):
        self.settings = QSettings("Crypty", "Crypty")

    def usernames(self) -> list[str]:
        value = self.settings.value("auth/saved_usernames", [], type=list)
        return [name for name in value if isinstance(name, str) and name.strip()]

    def remember(self, username: str, limit: int = 8) -> None:
        username = username.strip()
        if not username:
            return
        names = [name for name in self.usernames() if name != username]
        names.insert(0, username)
        self.settings.setValue("auth/saved_usernames", names[:limit])

    def forget(self, username: str) -> None:
        self.settings.setValue(
            "auth/saved_usernames",
            [name for name in self.usernames() if name != username],
        )
