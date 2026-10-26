from __future__ import annotations

import hashlib
import os
import re
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

    def _request(self, session: AuthSession, method: str, path: str, payload=None):
        try:
            response = requests.request(
                method,
                f"{self.base_url}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {session.token}"},
                timeout=self.timeout,
            )
        except requests.RequestException as error:
            raise AuthenticationError(
                "The Crypty account service is unavailable. Check the connection and try again."
            ) from error
        try:
            data = response.json()
        except ValueError as error:
            raise AuthenticationError(
                "The Crypty account service returned an invalid response."
            ) from error
        if not response.ok:
            raise AuthenticationError(data.get("error", "The account service rejected the request."))
        return data

    @staticmethod
    def device_fingerprint(device: dict) -> str:
        identity = device.get("stable_id") or device.get("id") or device.get("path")
        if not identity:
            raise ValueError("Selected device does not expose a stable identity.")
        return hashlib.sha256(
            f"crypty-device-v1:{identity}".encode("utf-8")
        ).hexdigest()

    def list_cases(self, session: AuthSession) -> list[dict]:
        return self._request(session, "GET", "/api/cases")

    def get_account_profile(self, session: AuthSession) -> dict:
        return self._request(session, "GET", "/api/account/me")

    def create_case(self, session: AuthSession, case: dict) -> dict:
        return self._request(session, "POST", "/api/cases", case)

    def attach_device(
        self, session: AuthSession, case_id: str, device: dict, fingerprint: str
    ) -> dict:
        payload = {
            "device_fingerprint": fingerprint,
            "name": device.get("name", ""),
            "filesystem": device.get("filesystem", ""),
            "capacity": device.get("capacity", ""),
        }
        return self._request(
            session, "POST", f"/api/cases/{case_id}/devices", payload
        )

    def record_audit_event(
        self,
        session: AuthSession,
        action: str,
        details: str = "",
        case: dict | None = None,
        device_fingerprint: str | None = None,
    ) -> None:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", action):
            raise ValueError("Audit action must be an uppercase action code.")
        payload = {"action": action, "details": details}
        if case:
            payload["case_id"] = case["id"]
        if device_fingerprint:
            payload["device_fingerprint"] = device_fingerprint
        self._request(session, "POST", "/api/audit/events", payload)

    def get_audit_logs(self, session: AuthSession) -> list[dict]:
        return self._request(session, "GET", "/api/audit/logs")

    def verify_audit_log(self, session: AuthSession) -> dict:
        return self._request(session, "GET", "/api/audit/verify")

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