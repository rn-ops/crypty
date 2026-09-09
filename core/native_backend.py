from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path


class NativeBackend:
    """Python adapter for the portable C++ workflow engine."""

    def __init__(self):
        library_path = self._find_library()
        self._dll_directory = None
        if hasattr(os, "add_dll_directory"):
            self._dll_directory = os.add_dll_directory(str(library_path.parent))
        self._library = ctypes.CDLL(str(library_path))
        self._configure_library()
        self._workflow = self._library.crypty_workflow_create()
        if not self._workflow:
            raise RuntimeError("The Crypty workflow engine could not be created")

    def _find_library(self) -> Path:
        library_name = "crypty_native.dll" if sys.platform == "win32" else "libcrypty_native.so"
        candidates = []
        configured = os.environ.get("CRYPTY_NATIVE_LIBRARY")
        if configured:
            candidates.append(Path(configured))

        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        candidates.extend(
            [
                bundle_root / library_name,
                bundle_root / "_internal" / library_name,
                Path(__file__).resolve().parents[1] / "build" / "Release" / library_name,
                Path(__file__).resolve().parents[1] / "build" / library_name,
            ]
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        searched = "\n".join(str(candidate) for candidate in candidates)
        raise FileNotFoundError(f"Crypty native engine not found. Searched:\n{searched}")

    def _configure_library(self):
        library = self._library
        library.crypty_workflow_create.restype = ctypes.c_void_p
        library.crypty_workflow_destroy.argtypes = [ctypes.c_void_p]
        library.crypty_workflow_select_operation.argtypes = [ctypes.c_void_p, ctypes.c_int]
        library.crypty_workflow_inspect_target.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        library.crypty_workflow_start.argtypes = [ctypes.c_void_p]
        library.crypty_workflow_advance.argtypes = [ctypes.c_void_p, ctypes.c_int]
        library.crypty_workflow_write_report.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        library.crypty_workflow_write_report.restype = ctypes.c_int
        for name in (
            "crypty_workflow_state",
            "crypty_workflow_progress",
            "crypty_workflow_evidence_items",
        ):
            getattr(library, name).argtypes = [ctypes.c_void_p]
            getattr(library, name).restype = ctypes.c_int
        library.crypty_workflow_total_bytes.argtypes = [ctypes.c_void_p]
        library.crypty_workflow_total_bytes.restype = ctypes.c_uint64
        for name in (
            "crypty_workflow_integrity",
            "crypty_workflow_target_path",
        ):
            getattr(library, name).argtypes = [ctypes.c_void_p]
            getattr(library, name).restype = ctypes.c_char_p
        library.crypty_workflow_file_count.argtypes = [ctypes.c_void_p]
        library.crypty_workflow_file_count.restype = ctypes.c_size_t
        for name in ("crypty_workflow_file_name", "crypty_workflow_file_type"):
            getattr(library, name).argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            getattr(library, name).restype = ctypes.c_char_p
        library.crypty_workflow_file_size.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        library.crypty_workflow_file_size.restype = ctypes.c_uint64
        library.crypty_workflow_audit_count.argtypes = [ctypes.c_void_p]
        library.crypty_workflow_audit_count.restype = ctypes.c_size_t
        for name in ("crypty_workflow_audit_code", "crypty_workflow_audit_message"):
            getattr(library, name).argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            getattr(library, name).restype = ctypes.c_char_p
        library.crypty_device_count.restype = ctypes.c_size_t
        for name in (
            "crypty_device_path",
            "crypty_device_name",
            "crypty_device_filesystem",
            "crypty_device_media_type",
            "crypty_device_interface",
            "crypty_device_status",
        ):
            getattr(library, name).argtypes = [ctypes.c_size_t]
            getattr(library, name).restype = ctypes.c_char_p
        library.crypty_device_capacity.argtypes = [ctypes.c_size_t]
        library.crypty_device_capacity.restype = ctypes.c_uint64

    def __del__(self):
        workflow = getattr(self, "_workflow", None)
        library = getattr(self, "_library", None)
        if workflow and library:
            library.crypty_workflow_destroy(workflow)

    def _text(self, name: str) -> str:
        return getattr(self._library, name)(self._workflow).decode("utf-8")

    def _inspect(self, device: dict) -> None:
        self._library.crypty_workflow_inspect_target(
            self._workflow, device.get("path", ".").encode("utf-8")
        )

    def analyze_device(self, device: dict) -> dict:
        self._inspect(device)
        return {
            "filesystem": device["filesystem"],
            "media_type": device["media_type"],
            "status": device["status"],
            "evidence_items": self._library.crypty_workflow_evidence_items(self._workflow),
            "total_bytes": self._library.crypty_workflow_total_bytes(self._workflow),
        }

    def detect_devices(self) -> list[dict]:
        devices = []
        for index in range(self._library.crypty_device_count()):
            text = lambda name: getattr(self._library, name)(index).decode("utf-8")
            capacity = self._library.crypty_device_capacity(index)
            devices.append(
                {
                    "id": text("crypty_device_path"),
                    "name": text("crypty_device_name"),
                    "capacity": self._format_capacity(capacity),
                    "capacity_bytes": capacity,
                    "interface": text("crypty_device_interface"),
                    "media_type": text("crypty_device_media_type"),
                    "filesystem": text("crypty_device_filesystem"),
                    "health": "Available",
                    "mount": text("crypty_device_path"),
                    "path": text("crypty_device_path"),
                    "status": text("crypty_device_status"),
                    "type": text("crypty_device_media_type"),
                }
            )
        return devices

    @staticmethod
    def _format_capacity(value: int) -> str:
        units = ("B", "KB", "MB", "GB", "TB", "PB")
        amount = float(value)
        unit = units[0]
        for unit in units:
            if amount < 1024 or unit == units[-1]:
                break
            amount /= 1024
        return f"{amount:.0f} {unit}"

    def write_report(self, filename: str) -> bool:
        return bool(
            self._library.crypty_workflow_write_report(
                self._workflow, filename.encode("utf-8")
            )
        )

    def recover_files(self, device: dict) -> dict:
        self._library.crypty_workflow_select_operation(self._workflow, 0)
        self._inspect(device)
        count = self._library.crypty_workflow_file_count(self._workflow)
        self._library.crypty_workflow_start(self._workflow)
        for _ in range(5):
            self._library.crypty_workflow_advance(self._workflow, 20)
        return {
            "files_found": count,
            "recoverable": count,
            "needs_review": 0,
            "invalid": 0,
            "integrity": self._text("crypty_workflow_integrity"),
        }

    def recovery_entries(self, device: dict) -> list[dict]:
        self._library.crypty_workflow_select_operation(self._workflow, 0)
        self._inspect(device)
        entries = []
        for index in range(self._library.crypty_workflow_file_count(self._workflow)):
            size = self._library.crypty_workflow_file_size(self._workflow, index)
            entries.append(
                {
                    "file": self._library.crypty_workflow_file_name(self._workflow, index).decode("utf-8"),
                    "type": self._library.crypty_workflow_file_type(self._workflow, index).decode("utf-8"),
                    "size": f"{size:,} B",
                    "method": "Filesystem",
                    "confidence": 100,
                    "status": "Valid",
                }
            )
        return entries

    def audit_events(self) -> list[dict]:
        events = []
        for index in range(self._library.crypty_workflow_audit_count(self._workflow)):
            events.append(
                {
                    "action": self._library.crypty_workflow_audit_code(self._workflow, index).decode("utf-8"),
                    "message": self._library.crypty_workflow_audit_message(self._workflow, index).decode("utf-8"),
                }
            )
        return events