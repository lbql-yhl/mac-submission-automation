#!/usr/bin/env python3
"""Contract tests for UTM-8 password writeback ordering."""

from __future__ import annotations

import tempfile
import unittest
import os
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT))

import scripts.utm_8_change_password as runner


class FakeNotion:
    def __init__(self) -> None:
        self.section = "用户名：Test User\n修改后的密码：\n邮箱：test@example.test"
        self.parent_checks = 0
        self.values = {"修改后的密码：": "", "初始密码：": "Current9Password"}
        self.field_reads: list[str] = []

    def verify_parent(self, title: str) -> str:
        self.parent_checks += 1
        return title

    def read_section(self, title: str, heading: str) -> str:
        return self.section

    def set_field(self, title, heading, label, value, *, replace_existing=False):
        lines = self.section.splitlines()
        index = next(i for i, line in enumerate(lines) if line.startswith(label))
        lines[index] = label + value
        self.section = "\n".join(lines)
        return True

    def read_field(self, title, heading, label):
        self.field_reads.append(label)
        if label == "初始密码：":
            return self.values[label]
        return next(line[len(label):] for line in self.section.splitlines() if line.startswith(label))


class UTM8ChangePasswordTests(unittest.TestCase):
    def test_generated_candidate_has_required_trailing_y(self) -> None:
        for _ in range(20):
            candidate = runner.generate_password()
            self.assertEqual(len(candidate), 17)
            self.assertTrue(candidate.endswith("y"))
            self.assertTrue(any(char.isupper() for char in candidate))
            self.assertTrue(any(char.islower() for char in candidate))
            self.assertTrue(any(char.isdigit() for char in candidate))

    def test_writes_notion_only_after_guest_success(self) -> None:
        api = FakeNotion()
        captured: dict[str, object] = {}

        def fake_run(command, **kwargs):
            if kwargs.get("input") is not None:
                captured["payload"] = kwargs["input"]
                captured["notion_before_guest"] = api.read_field(
                    "test1", "账号信息", "修改后的密码："
                )
            return SimpleNamespace(returncode=0, stdout="")

        with tempfile.NamedTemporaryFile() as key_file, patch.dict(
            os.environ, {"SUBMISSION_HOST_MACHINE": "海淋"}, clear=False
        ), patch.object(
            runner, "api_from_env", return_value=api
        ), patch.object(runner, "generate_password", return_value="K7mQ9vT2pL6xR4nZy"), patch.object(
            runner, "_scp_file"
        ), patch.object(runner, "_verify_remote_files"), patch.object(
            runner, "_verify_remote_compilation"
        ), patch.object(runner.subprocess, "run", side_effect=fake_run
        ):
            result = runner.run(
                SimpleNamespace(
                    ssh_key=key_file.name,
                    vm_user="demo",
                    vm_ip="192.0.2.10",
                    vm_name="test1",
                    guest_dir="/Users/demo/Downloads",
                    source_dir=str(Path.home() / "Downloads"),
                )
            )

        self.assertEqual(result, 0)
        self.assertGreaterEqual(api.parent_checks, 2)
        self.assertEqual(api.read_field("test1", "账号信息", "修改后的密码："), "K7mQ9vT2pL6xR4nZy")
        payload = json.loads(bytes(captured["payload"]).decode("utf-8"))
        self.assertEqual(payload["APPLE_ACCOUNT_CURRENT_PASSWORD"], "Current9Password")
        self.assertEqual(captured["notion_before_guest"], "K7mQ9vT2pL6xR4nZy")

    def test_guest_failure_does_not_write_notion(self) -> None:
        api = FakeNotion()

        def fake_run(command, **kwargs):
            if kwargs.get("input") is not None:
                return SimpleNamespace(returncode=5, stdout="")
            return SimpleNamespace(returncode=0, stdout="")

        with tempfile.NamedTemporaryFile() as key_file, patch.dict(
            os.environ, {"SUBMISSION_HOST_MACHINE": "海淋"}, clear=False
        ), patch.object(
            runner, "api_from_env", return_value=api
        ), patch.object(runner, "_scp_file"), patch.object(
            runner, "_verify_remote_files"
        ), patch.object(runner, "_verify_remote_compilation"), patch.object(
            runner.subprocess, "run", side_effect=fake_run
        ):
            result = runner.run(
                SimpleNamespace(
                    ssh_key=key_file.name,
                    vm_user="demo",
                    vm_ip="192.0.2.10",
                    vm_name="test1",
                    guest_dir="/Users/demo/Downloads",
                    source_dir=str(Path.home() / "Downloads"),
                )
            )

        self.assertEqual(result, 5)
        self.assertEqual(api.read_field("test1", "账号信息", "修改后的密码："), "")
        self.assertEqual(api.parent_checks, 2)


if __name__ == "__main__":
    unittest.main()
