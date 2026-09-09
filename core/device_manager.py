from __future__ import annotations

class DeviceManager:
    def __init__(self, backend):
        self.backend = backend
        self._devices = backend.detect_devices()
        self._selected_device = self._devices[0] if self._devices else None

    def get_devices(self) -> list[dict]:
        return self._devices

    def get_selected_device(self) -> dict:
        return self._selected_device

    def set_selected_device(self, device: dict) -> None:
        self._selected_device = device