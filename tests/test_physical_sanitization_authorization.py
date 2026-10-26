"""Regression tests for physical-device authorization forwarding.

These tests use a fake native library; they never open or write to a real device.
Run from the repository root with: python -m unittest discover -s tests -v
"""
import ctypes
import unittest

from core.native_backend import NativeBackend
from core.sanitization_engine import SanitizationEngine, SanitizationTarget


class FakeFunction:
    def __init__(self, result):
        self.result = result
        self.argtypes = None
        self.restype = None
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


class FakeNativeLibrary:
    def __init__(self, native_execute_result=1, result_successful=1):
        self.crypty_sanitization_execute_physical_device = FakeFunction(native_execute_result)
        self.crypty_sanitization_result_executed = FakeFunction(1)
        self.crypty_sanitization_result_successful = FakeFunction(result_successful)
        self.crypty_sanitization_result_execution_status = FakeFunction(2)
        self.crypty_sanitization_result_validation_status = FakeFunction(1)
        self.crypty_sanitization_result_bytes_processed = FakeFunction(4096)
        self.crypty_sanitization_result_error_code = FakeFunction(b"")
        self.crypty_sanitization_result_error_message = FakeFunction(b"")


class PhysicalAuthorizationForwardingTests(unittest.TestCase):
    def make_backend(self, native_result=1, successful=1):
        backend = NativeBackend.__new__(NativeBackend)
        backend._library = FakeNativeLibrary(native_result, successful)
        return backend

    def test_explicit_confirmation_is_forwarded_as_true(self):
        backend = self.make_backend()
        result = backend.execute_sanitization_plan_for_target(
            1234,
            {
                "confirmed": True,
                "confirmed_target_path": r"\\.\PhysicalDrive7",
                "confirmed_target_capacity_bytes": 4096,
                "confirmation_phrase": "SANITIZE THIS PHYSICAL DEVICE",
            },
        )
        args = backend._library.crypty_sanitization_execute_physical_device.calls[0]
        self.assertEqual(args[1], 1)
        self.assertEqual(args[2], br"\\.\PhysicalDrive7")
        self.assertEqual(args[3], 4096)
        self.assertEqual(args[4], b"SANITIZE THIS PHYSICAL DEVICE")
        self.assertTrue(result["successful"])

    def test_missing_or_false_confirmation_is_not_promoted_to_true(self):
        for authorization in ({}, {"confirmed": False}):
            with self.subTest(authorization=authorization):
                backend = self.make_backend()
                payload = {
                    "confirmed_target_path": r"\\.\PhysicalDrive7",
                    "confirmed_target_capacity_bytes": 4096,
                    "confirmation_phrase": "SANITIZE THIS PHYSICAL DEVICE",
                    **authorization,
                }
                backend.execute_sanitization_plan_for_target(1234, payload)
                args = backend._library.crypty_sanitization_execute_physical_device.calls[0]
                self.assertEqual(args[1], 0)

    def test_native_rejection_cannot_be_reported_as_success(self):
        backend = self.make_backend(native_result=0, successful=0)
        result = backend.execute_sanitization_plan_for_target(
            1234,
            {
                "confirmed": True,
                "confirmed_target_path": r"\\.\PhysicalDrive7",
                "confirmed_target_capacity_bytes": 4096,
                "confirmation_phrase": "wrong phrase",
            },
        )
        self.assertFalse(result["successful"])

    def test_physical_plan_uses_native_required_confirmation_phrase(self):
        engine = SanitizationEngine(backend=object())
        target = SanitizationTarget(
            kind="physical_device",
            target_id="serial:test-device",
            label="Disposable test device",
            selector="device",
            path=r"\\.\PhysicalDrive7",
            capacity_bytes=4096,
        )
        plan = engine._wrap_native_plan(
            {
                "_handle": 7,
                "status": 0,
                "status_name": "Ready",
                "target_path": target.path,
                "capacity_bytes": target.capacity_bytes,
            },
            target=target,
            method_id="physical_device_zero_overwrite",
            method_label="Physical-device zero overwrite",
        )
        self.assertEqual(plan.confirmation_phrase, "SANITIZE THIS PHYSICAL DEVICE")

    def test_incomplete_discovery_and_identity_gates_remain_in_native_executor(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        source = (root / "core/sanitization/execution/device_native_executor.cpp").read_text(
            encoding="utf-8"
        )
        self.assertIn("!found->protection_discovery_complete", source)
        self.assertIn("found->capacity_bytes != plan.target_capacity_bytes", source)
        self.assertIn("authorization.confirmed_target_path != plan.target_path", source)
        self.assertIn("authorization.confirmation_phrase != \"SANITIZE THIS PHYSICAL DEVICE\"", source)
        self.assertIn("DEVICE_IDENTITY_MISMATCH", source)

    def test_native_result_failure_cannot_be_reported_as_success(self):
        backend = self.make_backend(native_result=1, successful=0)
        result = backend.execute_sanitization_plan_for_target(
            1234,
            {
                "confirmed": True,
                "confirmed_target_path": r"\\.\PhysicalDrive7",
                "confirmed_target_capacity_bytes": 4096,
                "confirmation_phrase": "SANITIZE THIS PHYSICAL DEVICE",
            },
        )
        self.assertFalse(result["successful"])


if __name__ == "__main__":
    unittest.main()
