from __future__ import annotations

import os
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class AuthSession:
    username: str
    role: str
    token: str


class AuthenticationError(RuntimeError):
    pass


class AuthClient:
    def __init__(self, base_url: str | None = None, timeout: float = 5.0):
        self.base_url = (base_url or os.environ.get("CRYPTY_AUTH_URL", "http://127.0.0.1:5000")).rstrip("/")
        self.timeout = timeout

    def login(self, username: str, password: str) -> AuthSession:
        try:
            response = requests.post(
                f"{self.base_url}/api/auth/login",
                json={"username": username, "password": password},
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise AuthenticationError(
                "Authentication service is unavailable. Start auth/api/app.py and try again."
            ) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise AuthenticationError("Authentication service returned an invalid response.") from error

        if response.status_code != 200:
            raise AuthenticationError(payload.get("error", "Authentication failed."))

        token = payload.get("token")
        role = payload.get("role")
        if not token or not role:
            raise AuthenticationError("Authentication response did not contain a session.")
        return AuthSession(username=username, role=role, token=token)