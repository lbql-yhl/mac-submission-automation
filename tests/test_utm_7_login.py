#!/usr/bin/env python3
"""Contract tests for the non-visual UTM-7 Apple Account runner."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

import scripts.utm_7_login as runner


class FakeNotion:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.values = {
            "邮箱：": "account@example.test",
            "修改后的密码：": "",
            "初始密码：": "initial-secret",
            "电话：": "+1 555 0100",
            "电话短信接收平台：": "https://sms.example.test/latest",
        }

    def verify_parent(self, title: str) -> str:
        self.calls.append(("verify-parent", title))
        return "parent-id"

    def read_field(self, title: str, heading: str, label: str) -> str:
        self.calls.append(("read-field", label))
        return self.values[label]


class UTM7LoginRunnerTests(unittest.TestCase):
    def test_reads_modified_password_then_falls_back_to_initial(self) -> None:
        api = FakeNotion()
        captured: dict[str, object] = {}

        def fake_run(command, **kwargs):
            captured.setdefault("commands", []).append(command)
            if kwargs.get("input") is not None:
                captured["payload"] = kwargs["input"]
                return SimpleNamespace(returncode=0)
            return SimpleNamespace(returncode=0)

        with tempfile.NamedTemporaryFile() as key_file, patch.object(
            runner, "api_from_env", return_value=api
        ), patch.object(runner, "_scp_file"), patch.object(
            runner, "_verify_remote_hashes"
        ), patch.object(runner, "_verify_remote_compilation"), patch.object(
            runner.subprocess, "run", side_effect=fake_run
        ):
            args = SimpleNamespace(
                ssh_key=key_file.name,
                vm_user="test1",
                vm_ip="192.0.2.10",
                parent_title="Host",
                page_title="App-test1",
                guest_dir="/Users/test1/Downloads",
            )
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = runner.run(args)

        self.assertEqual(result, 0)
        self.assertIn(("read-field", "修改后的密码："), api.calls)
        self.assertIn(("read-field", "初始密码："), api.calls)
        payload = json.loads(bytes(captured["payload"]).decode("utf-8"))
        self.assertEqual(payload["APPLE_ACCOUNT_PASSWORD"], "initial-secret")
        self.assertEqual(payload["APPLE_ACCOUNT_EMAIL"], "account@example.test")
        final_command = next(
            command for command in captured["commands"] if "--stdin-json" in command
        )
        command_text = " ".join(final_command)
        self.assertNotIn("account@example.test", command_text)
        self.assertNotIn("initial-secret", command_text)
        self.assertIn("APPLE_ACCOUNT=verified", stdout.getvalue())
        self.assertIn("UTM_7=verified", stdout.getvalue())

    def test_rejects_non_regular_ssh_key_before_notion_reads(self) -> None:
        api = FakeNotion()
        with patch.object(runner, "api_from_env", return_value=api):
            args = SimpleNamespace(
                ssh_key="/dev/null",
                vm_user="test1",
                vm_ip="192.0.2.10",
                parent_title="Host",
                page_title="App-test1",
                guest_dir="",
            )
            with self.assertRaisesRegex(RuntimeError, "regular file"):
                runner.run(args)
        self.assertEqual(api.calls, [])


if __name__ == "__main__":
    unittest.main()
