#!/usr/bin/env python3
"""Contract tests for the streamlined UTM-8 password-change runner."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.utm_8_change_password as runner


TARGET_PASSWORD = "K7mQ9vT2pL6xR4nZy"


class FakeNotion:
    def __init__(self, modified_password: str = TARGET_PASSWORD) -> None:
        self.modified_password = modified_password
        self.field_reads: list[tuple[str, str, str]] = []
        self.parent_checks: list[str] = []

    def verify_parent(self, title: str) -> None:
        self.parent_checks.append(title)

    def read_field(self, title: str, heading: str, label: str) -> str:
        self.field_reads.append((title, heading, label))
        if label == "修改后的密码：":
            return self.modified_password
        if label == "初始密码：":
            return "LegacyInitial9Password"
        raise AssertionError(f"unexpected Notion field read: {label}")


def runner_args() -> SimpleNamespace:
    return SimpleNamespace(
        vm_user="test1",
        vm_ip="192.0.2.10",
        vm_name="test1",
        page_title="DemoApp-test1",
        guest_dir="",
        source_dir=str(ROOT / "scripts"),
    )


class UTM8ChangePasswordTests(unittest.TestCase):
    def test_guest_workflow_recovers_nested_account_page_with_unique_back_button(self) -> None:
        source = (ROOT / "scripts" / "find_system_settings_general.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('"go back"', source)
        self.assertIn("PASSWORD_CHANGE_ROOT_RECOVERY=verified", source)
        self.assertIn("kAXIdentifierAttribute", source)

    def test_reads_only_registered_modified_password_and_sends_it_over_stdin(self) -> None:
        api = FakeNotion()
        captured: dict[str, object] = {}

        def fake_run(command, **kwargs):
            if kwargs.get("input") is not None:
                captured["command"] = command
                captured["payload"] = kwargs["input"]
                return SimpleNamespace(
                    returncode=0,
                    stdout=(
                        "PASSWORD_CHANGE_NAVIGATION=verified\n"
                        "PASSWORD_CHANGE_FIELDS=verified\n"
                        "PASSWORD_CHANGE_BUTTON=enabled\n"
                        "PASSWORD_CHANGE_SUBMISSION=clicked_once\n"
                        "PASSWORD_CHANGE_RESULT=verified\n"
                        "SYSTEM_SETTINGS_CLOSED=verified\n"
                        "PASSWORD_CHANGE=verified\n"
                    ),
                    stderr="",
                )
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        stdout = io.StringIO()
        with patch.object(
            runner, "api_from_env", return_value=api
        ), patch.object(
            runner, "_prepare_shared_helpers"
        ) as prepare_helpers, patch.object(
            runner, "_ensure_remote_pyobjc"
        ) as ensure_pyobjc, patch.object(
            runner, "_ensure_remote_accessibility"
        ) as ensure_accessibility, patch.object(
            runner.subprocess, "run", side_effect=fake_run
        ), contextlib.redirect_stdout(stdout):
            result = runner.run(runner_args())

        self.assertEqual(result, 0)
        self.assertEqual(
            api.field_reads,
            [("DemoApp-test1", "账号信息", "修改后的密码：")],
        )
        payload = json.loads(bytes(captured["payload"]).decode("utf-8"))
        self.assertEqual(payload, {"APPLE_ACCOUNT_NEW_PASSWORD": TARGET_PASSWORD})
        prepare_helpers.assert_called_once_with(
            "test1", "192.0.2.10", runner.GUEST_SHARED_HELPER_DIR
        )
        ensure_pyobjc.assert_called_once_with("test1", "192.0.2.10")
        ensure_accessibility.assert_called_once_with("test1", "192.0.2.10")
        command = " ".join(str(part) for part in captured["command"])
        self.assertIn("AppleAccountScriptsBackup/apple_account_change_password.py", command)
        self.assertNotIn("screen_workflow_router", command)
        self.assertNotIn(TARGET_PASSWORD, stdout.getvalue())
        self.assertIn("PASSWORD_CHANGE=verified", stdout.getvalue())
        self.assertIn("UTM_8=verified", stdout.getvalue())

    def test_zero_exit_with_only_legacy_guest_success_marker_is_blocked(self) -> None:
        api = FakeNotion()
        stderr = io.StringIO()
        with patch.object(runner, "api_from_env", return_value=api), patch.object(
            runner, "_prepare_shared_helpers"
        ), patch.object(runner, "_ensure_remote_pyobjc"), patch.object(
            runner, "_ensure_remote_accessibility"
        ), patch.object(
            runner.subprocess,
            "run",
            return_value=SimpleNamespace(
                returncode=0,
                stdout="PASSWORD_CHANGE=verified\n",
                stderr="",
            ),
        ), contextlib.redirect_stderr(stderr):
            result = runner.run(runner_args())

        self.assertNotEqual(result, 0)
        self.assertIn("guest success markers missing", stderr.getvalue())

    def test_nonzero_guest_exit_reports_non_sensitive_failure_stage(self) -> None:
        api = FakeNotion()
        stderr = io.StringIO()
        with patch.object(runner, "api_from_env", return_value=api), patch.object(
            runner, "_prepare_shared_helpers"
        ), patch.object(runner, "_ensure_remote_pyobjc"), patch.object(
            runner, "_ensure_remote_accessibility"
        ), patch.object(
            runner.subprocess,
            "run",
            return_value=SimpleNamespace(
                returncode=5,
                stdout="PASSWORD_CHANGE_STAGE=password_fields\n",
                stderr="未找到新密码或确认密码输入框。\n",
            ),
        ), contextlib.redirect_stderr(stderr):
            result = runner.run(runner_args())

        self.assertEqual(result, 5)
        self.assertIn(
            "PASSWORD_CHANGE_GUEST_FAILURE=未找到新密码或确认密码输入框。",
            stderr.getvalue(),
        )
        self.assertNotIn(TARGET_PASSWORD, stderr.getvalue())

    def test_empty_modified_password_stops_before_any_ssh_side_effect(self) -> None:
        api = FakeNotion("")
        with patch.object(
            runner, "api_from_env", return_value=api
        ), patch.object(
            runner, "_prepare_shared_helpers"
        ) as prepare_helpers, patch.object(
            runner.subprocess, "run", return_value=SimpleNamespace(returncode=0)
        ) as run_command:
            with self.assertRaisesRegex(
                RuntimeError, "Notion modified Apple Account password is empty"
            ):
                runner.run(runner_args())

        run_command.assert_not_called()
        prepare_helpers.assert_not_called()
        self.assertEqual(
            api.field_reads,
            [("DemoApp-test1", "账号信息", "修改后的密码：")],
        )

    def test_rejects_guest_downloads_override_before_notion_or_ssh(self) -> None:
        api = FakeNotion()
        args = runner_args()
        args.guest_dir = "/Users/test1/Downloads"
        with patch.object(
            runner, "api_from_env", return_value=api
        ), patch.object(runner.subprocess, "run") as run_command:
            with self.assertRaisesRegex(
                RuntimeError, "guest-dir must be the inherited shared helper mount"
            ):
                runner.run(args)

        self.assertEqual(api.field_reads, [])
        run_command.assert_not_called()

    def test_guest_helper_is_project_owned_and_accepts_stdin_json(self) -> None:
        helper = ROOT / "scripts" / "apple_account_change_password.py"
        self.assertTrue(helper.is_file(), "missing project-owned guest helper")
        source = helper.read_text(encoding="utf-8")
        self.assertIn("json.load(sys.stdin)", source)
        self.assertNotIn("screen_workflow_router.py", source)
        self.assertNotIn("run_visual_navigation", source)
        self.assertIn("PASSWORD_CHANGE_NAVIGATION=verified", source)
        self.assertIn('"--change-password"', source)
        self.assertNotIn('"--change-password-form-only"', source)
        self.assertIn("APPLE_ACCOUNT_NEW_PASSWORD", source)
        self.assertIn('print("PASSWORD_CHANGE=verified")', source)
        self.assertNotIn("APPLE_ACCOUNT_CURRENT_PASSWORD", source)

        runner_source = (ROOT / "scripts" / "utm_8_change_password.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("_prepare_shared_helpers", runner_source)
        self.assertIn("_ensure_remote_pyobjc", runner_source)
        self.assertIn("_ensure_remote_accessibility", runner_source)
        self.assertNotIn("_deploy_visual_router", runner_source)
        self.assertNotIn("_prepare_visual_router_runtime", runner_source)
        self.assertNotIn("opencv", runner_source.lower())

        implementation = (ROOT / "scripts" / "find_system_settings_general.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("MINIMUM_GUI_SETTLE_SECONDS = 3.0", implementation)
        self.assertIn('CHANGE_PASSWORD_TEXTS = (', implementation)
        self.assertIn('"Change Password..."', implementation)
        self.assertIn('"Change Password…"', implementation)
        self.assertIn(
            "find_enabled_pressable_text_candidates(\n"
            "                current_search_roots(pid), CHANGE_PASSWORD_TEXTS",
            implementation,
        )
        self.assertIn('print("PASSWORD_CHANGE_FORM=resume_existing")', implementation)
        self.assertIn("def _nearest_password_field_labels(", implementation)
        self.assertIn("PASSWORD_FIELD_TEXTS = (", implementation)
        self.assertIn('    "Verify",', implementation)
        self.assertIn(
            "return run_apple_account_change_password_form(\n"
            "            pid, new_password_variable\n"
            "        )",
            implementation,
        )
        self.assertIn("verify_password_change_result", implementation)
        self.assertIn("PASSWORD_CHANGE_SUBMISSION=clicked_once", implementation)
        self.assertIn(
            'labels = ("Change", "Continue")',
            implementation,
        )
        self.assertIn(
            "new_field = _unique_field_by_labels(roots, NEW_PASSWORD_FIELD_TEXTS)",
            implementation,
        )
        self.assertIn(
            "verify_field = _unique_field_by_labels(roots, VERIFY_PASSWORD_FIELD_TEXTS)",
            implementation,
        )
        self.assertIn("def set_password_change_field(", implementation)
        self.assertIn("CGEventKeyboardSetUnicodeString", implementation)
        self.assertIn("CGEventPost(QUARTZ.kCGHIDEventTap", implementation)
        self.assertIn('print("PASSWORD_CHANGE_BUTTON=enabled")', implementation)
        self.assertIn("def handle_sign_out_other_devices_prompt(", implementation)
        self.assertIn("Don't Sign Out", implementation)
        self.assertIn('TRY_AGAIN_LATER_TEXT = "Try Again Later"', implementation)
        self.assertIn("POST_SUBMIT_STABLE_READS_REQUIRED = 3", implementation)
        self.assertIn('print("SYSTEM_SETTINGS_CLOSED=verified")', implementation)

        prompt_helper = (ROOT / "scripts" / "mac_password_prompt.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("Apple Account wants to make changes.", prompt_helper)
        self.assertIn('"Allow"', prompt_helper)
        self.assertIn("FIXED_VM_PASSWORD_RESULT=verified", prompt_helper)
        self.assertIn("MINIMUM_GUI_SETTLE_SECONDS", prompt_helper)


if __name__ == "__main__":
    unittest.main()
