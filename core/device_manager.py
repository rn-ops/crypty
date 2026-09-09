from __future__ import annotations

from crypty.data.demo_data import DEMO_DEVICES


class DeviceManager:
    def __init__(self, backend):
        self.backend = backend
        self._devices = list(DEMO_DEVICES)
        self._selected_device = self._devices[0]

    def get_devices(self) -> list[dict]:
        return self._devices

    def get_selected_device(self) -> dict:
        return self._selected_device

    def set_selected_device(self, device: dict) -> None:
        self._selected_device = device