from __future__ import annotations

class DeviceManager:
    def __init__(self, backend):
        self.backend = backend
        self._devices = backend.detect_devices()
        self._selected_device = self._devices[0] if self._devices else None

    def get_devices(self) -> list[dict]:
        return self._devices

    def get_selected_device(self) -> dict | None:
        return self._selected_device

    def set_selected_device(self, device: dict) -> None:
        self._selected_device = device

    def refresh(self) -> list[dict]:
        """Rescan connected media and retain the current selection if possible."""
        selected_path = (
            self._selected_device.get("path") if self._selected_device else None
        )
        refresh_devices = getattr(self.backend, "refresh_devices", None)
        self._devices = (
            refresh_devices() if refresh_devices else self.backend.detect_devices()
        )
        self._selected_device = next(
            (device for device in self._devices if device.get("path") == selected_path),
            self._devices[0] if self._devices else None,
        )
        return self._devices
