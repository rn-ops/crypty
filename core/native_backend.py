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
        project_root = Path(__file__).resolve().parents[1]
        if sys.platform == "win32":
            library_names = ("crypty_native.dll",)
        elif sys.platform == "darwin":
            library_names = ("libcrypty_native.dylib",)
        else:
            library_names = ("libcrypty_native.so",)

        candidates = []
        configured = os.environ.get("CRYPTY_NATIVE_LIBRARY")
        if configured:
            candidates.append(Path(configured))

        for library_name in library_names:
            candidates.extend([
                project_root / library_name,
                project_root / "build" / "Release" / library_name,
                project_root / "build" / "Debug" / library_name,
                project_root / "build" / library_name,
            ])

        if hasattr(sys, "_MEIPASS"):
            bundle_root = Path(sys._MEIPASS)
            for library_name in library_names:
                candidates.extend([
                    bundle_root / library_name,
                    bundle_root / "_internal" / library_name,
                ])

        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()

        searched = "\n".join(str(p.resolve()) for p in candidates)
        raise FileNotFoundError(
            f"Crypty native engine not found. Searched:\n{searched}"
        )

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

        library.crypty_workflow_scan_ntfs.argtypes = [
            ctypes.c_void_p
        ]
        library.crypty_workflow_scan_ntfs.restype = ctypes.c_size_t

        for name in (
            "crypty_workflow_file_name",
            "crypty_workflow_file_type",
            "crypty_workflow_file_path",
        ):
            getattr(library, name).argtypes = [
                ctypes.c_void_p,
                ctypes.c_size_t,
            ]
            getattr(library, name).restype = ctypes.c_char_p

        library.crypty_workflow_file_size.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        library.crypty_workflow_file_size.restype = ctypes.c_uint64
        library.crypty_workflow_scan_fat32_deleted.argtypes = [ctypes.c_void_p]
        library.crypty_workflow_scan_fat32_deleted.restype = ctypes.c_size_t
        library.crypty_workflow_recover_fat32_file.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
        library.crypty_workflow_recover_fat32_file.restype = ctypes.c_uint64


        library.crypty_workflow_recover_ntfs_file.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_int),
        ]

        library.crypty_workflow_recover_ntfs_file.restype = ctypes.c_uint64

        for name in (
            "crypty_workflow_file_offset",
            "crypty_workflow_file_confidence",
            "crypty_workflow_file_deleted",
        ):
            getattr(library, name).argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        library.crypty_workflow_file_offset.restype = ctypes.c_uint64
        library.crypty_workflow_file_confidence.restype = ctypes.c_int
        library.crypty_workflow_file_deleted.restype = ctypes.c_int
        library.crypty_workflow_file_method.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        library.crypty_workflow_file_method.restype = ctypes.c_char_p
        library.crypty_workflow_read_media.argtypes = [
            ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_size_t,
        ]

        library.crypty_workflow_read_media.restype = ctypes.c_size_t
        library.crypty_workflow_audit_count.argtypes = [ctypes.c_void_p]
        library.crypty_workflow_audit_count.restype = ctypes.c_size_t
        for name in ("crypty_workflow_audit_code", "crypty_workflow_audit_message"):
            getattr(library, name).argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            getattr(library, name).restype = ctypes.c_char_p
        library.crypty_device_count.restype = ctypes.c_size_t
        library.crypty_devices_refresh.restype = None
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

        # Native sanitization plan/execution API. The opaque handle owns the
        # immutable target plan and its eventual execution result.
        library.crypty_sanitization_plan_image_file.argtypes = [ctypes.c_char_p]
        library.crypty_sanitization_plan_image_file.restype = ctypes.c_void_p
        library.crypty_sanitization_plan_destroy.argtypes = [ctypes.c_void_p]
        library.crypty_sanitization_plan_status.argtypes = [ctypes.c_void_p]
        library.crypty_sanitization_plan_status.restype = ctypes.c_int
        for name in ("crypty_sanitization_plan_reason", "crypty_sanitization_plan_path"):
            getattr(library, name).argtypes = [ctypes.c_void_p]
            getattr(library, name).restype = ctypes.c_char_p
        library.crypty_sanitization_plan_capacity.argtypes = [ctypes.c_void_p]
        library.crypty_sanitization_plan_capacity.restype = ctypes.c_uint64
        library.crypty_sanitization_execute_image_file.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p,
            ctypes.c_uint64, ctypes.c_char_p,
        ]
        library.crypty_sanitization_execute_image_file.restype = ctypes.c_int
        for name in (
            "crypty_sanitization_result_executed",
            "crypty_sanitization_result_successful",
            "crypty_sanitization_result_execution_status",
            "crypty_sanitization_result_validation_status",
        ):
            getattr(library, name).argtypes = [ctypes.c_void_p]
            getattr(library, name).restype = ctypes.c_int
        library.crypty_sanitization_result_bytes_processed.argtypes = [ctypes.c_void_p]
        library.crypty_sanitization_result_bytes_processed.restype = ctypes.c_uint64
        for name in (
            "crypty_sanitization_result_error_code",
            "crypty_sanitization_result_error_message",
        ):
            getattr(library, name).argtypes = [ctypes.c_void_p]
            getattr(library, name).restype = ctypes.c_char_p

        library.crypty_workflow_file_created.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        library.crypty_workflow_file_created.restype = ctypes.c_char_p

        library.crypty_workflow_file_modified.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        library.crypty_workflow_file_modified.restype = ctypes.c_char_p

        library.crypty_workflow_file_accessed.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        library.crypty_workflow_file_accessed.restype = ctypes.c_char_p


        library.crypty_workflow_recover_ntfs_file.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_int),
        ]

        library.crypty_workflow_recover_ntfs_file.restype = ctypes.c_uint64


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
        self._active_target = device.get("path", ".")

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

    def refresh_devices(self) -> list[dict]:
        self._library.crypty_devices_refresh()
        return self.detect_devices()

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

    def create_sanitization_plan(self, path: str) -> dict:
        handle = self._library.crypty_sanitization_plan_image_file(
            str(path).encode("utf-8")
        )
        if not handle:
            raise RuntimeError("The native sanitization planner could not create a plan")

        status = int(self._library.crypty_sanitization_plan_status(handle))
        decode = lambda name: getattr(self._library, name)(handle).decode(
            "utf-8", errors="replace"
        )
        return {
            "_handle": int(handle),
            "status": status,
            "status_name": {0: "Ready", 1: "Unsupported", 2: "RequiresUserConfirmation", 3: "Blocked"}.get(status, "Unknown"),
            "reason": decode("crypty_sanitization_plan_reason"),
            "target_path": decode("crypty_sanitization_plan_path"),
            "capacity_bytes": int(self._library.crypty_sanitization_plan_capacity(handle)),
        }

    def execute_sanitization_plan(
        self,
        plan_handle: int,
        confirmed_path: str,
        capacity_bytes: int,
        confirmation_phrase: str,
    ) -> dict:
        handle = ctypes.c_void_p(plan_handle)
        successful = bool(self._library.crypty_sanitization_execute_image_file(
            handle,
            1,
            confirmed_path.encode("utf-8"),
            capacity_bytes,
            confirmation_phrase.encode("utf-8"),
        ))
        decode = lambda name: getattr(self._library, name)(handle).decode(
            "utf-8", errors="replace"
        )
        return {
            "executed": bool(self._library.crypty_sanitization_result_executed(handle)),
            "successful": successful and bool(self._library.crypty_sanitization_result_successful(handle)),
            "execution_status": int(self._library.crypty_sanitization_result_execution_status(handle)),
            "validation_status": int(self._library.crypty_sanitization_result_validation_status(handle)),
            "bytes_processed": int(self._library.crypty_sanitization_result_bytes_processed(handle)),
            "error_code": decode("crypty_sanitization_result_error_code"),
            "error_message": decode("crypty_sanitization_result_error_message"),
        }

    def destroy_sanitization_plan(self, plan_handle: int) -> None:
        if plan_handle:
            self._library.crypty_sanitization_plan_destroy(ctypes.c_void_p(plan_handle))

    def write_report(self, filename: str) -> bool:
        return bool(
            self._library.crypty_workflow_write_report(
                self._workflow, filename.encode("utf-8")
            )
        )


    def _recovery_entries_from_native(self) -> list[dict]:
        entries = []

        count = self._library.crypty_workflow_file_count(self._workflow)

        for index in range(count):
            size = self._library.crypty_workflow_file_size(
                self._workflow, index
            )
            deleted = bool(
                self._library.crypty_workflow_file_deleted(
                    self._workflow, index
                )
            )
            confidence = self._library.crypty_workflow_file_confidence(
                self._workflow, index
            )

            method = self._library.crypty_workflow_file_method(
                self._workflow, index
            ).decode("utf-8")

            name = self._library.crypty_workflow_file_name(
                self._workflow, index
            ).decode("utf-8")

            path = self._library.crypty_workflow_file_path(
                self._workflow, index
            ).decode("utf-8")

            file_type = self._library.crypty_workflow_file_type(
                self._workflow, index
            ).decode("utf-8")

            created = self._library.crypty_workflow_file_created(
                self._workflow, index
            ).decode("utf-8")

            modified = self._library.crypty_workflow_file_modified(
                self._workflow, index
            ).decode("utf-8")

            accessed = self._library.crypty_workflow_file_accessed(
                self._workflow, index
            ).decode("utf-8")

            entries.append({
                "native_index": index,
                "file": name,
                "path": path,
                "type": file_type,
                "size": f"{size:,} B",
                "size_bytes": size,
                "recoverable": size if deleted else 0,
                "method": method,
                "confidence": confidence,
                "status": "Traced" if deleted else "Existing",
                "deleted": deleted,
                "created": created,
                "modified": modified,
                "accessed": accessed,
            })
            

        return entries


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





    def recover_fat32_file(self, entry: dict, destination: str) -> tuple[int, bool]:
            complete = ctypes.c_int()
            written = self._library.crypty_workflow_recover_fat32_file(
                self._workflow, entry["native_index"], destination.encode("utf-8"), ctypes.byref(complete)
            )
            return written, bool(complete.value)


    def recover_ntfs_file(
        self,
        entry: dict,
        destination: str,
    ) -> tuple[int, bool]:

        complete = ctypes.c_int(0)

        written = (
            self._library.crypty_workflow_recover_ntfs_file(
                self._workflow,
                entry["native_index"],
                os.fsencode(destination),
                ctypes.byref(complete),
            )
        )

        return int(written), bool(complete.value)



    def scan_fat32_deleted_files(self, device: dict) -> list[dict]:
        self._prepare_recovery_scan(device)

        self._library.crypty_workflow_scan_fat32_deleted(
            self._workflow
        )

        return self._recovery_entries_from_native()

    def scan_ntfs_files(self, device: dict) -> list[dict]:
        self._prepare_recovery_scan(device)

        count = self._library.crypty_workflow_scan_ntfs(self._workflow)

        print(f"Python: native NTFS scan returned {count} entries")

        entries = self._recovery_entries_from_native()

        print(f"Python: workflow contains {len(entries)} entries")

        return entries
    
    def recover_ntfs_file(self, index, destination):
        complete = ctypes.c_int(0)

        bytes_recovered = (
            self._library.crypty_workflow_recover_ntfs_file(
                self._workflow,
                index,
                os.fsencode(destination),
                ctypes.byref(complete),
            )
        )

        return int(bytes_recovered), bool(complete.value)

    def scan_exfat_deleted_files(self, device: dict) -> list[dict]:
        self._prepare_recovery_scan(device)

        self._library.crypty_workflow_scan_exfat_deleted(
            self._workflow
        )

        return self._recovery_entries_from_native()


    def _prepare_recovery_scan(self, device: dict):
        self._library.crypty_workflow_select_operation(
            self._workflow,
            0
        )

        if (
            getattr(self, "_active_target", None)
            != device.get("path", ".")
        ):
            self._inspect(device)














    def read_media(self, device: dict, offset: int, length: int = 512) -> bytes:
        """Read one bounded page of evidence bytes; the native handle is read-only."""
        if offset < 0 or length < 1 or length > 1024 * 1024:
            raise ValueError("Evidence reads must be between 1 byte and 1 MiB")
        if getattr(self, "_active_target", None) != device.get("path", "."):
            self._inspect(device)
        buffer = (ctypes.c_ubyte * length)()
        read = self._library.crypty_workflow_read_media(
            self._workflow, offset, buffer, length
        )
        return bytes(buffer[:read])
    
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
