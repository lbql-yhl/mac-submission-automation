from __future__ import annotations

import json
import sqlite3
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from services import feishu_bot


PROJECT_CHAT = "project-chat"
DAILY_CHAT = "daily-chat"
LOCAL_HOST = "host-a"


def sample_config(**overrides: Any) -> SimpleNamespace:
    values = {
        "allowed_chat_id": PROJECT_CHAT,
        "daily_report_chat_id": DAILY_CHAT,
        "submission_host_machine": LOCAL_HOST,
        "assistant_enabled": True,
        "assistant_require_mention": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def install_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    runs: list[dict[str, Any]],
) -> Path:
    path = tmp_path / "feishu-runs.json"
    path.write_text(json.dumps({"runs": runs}), encoding="utf-8")
    path.chmod(0o600)
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", path)
    return path


def create_inventory(tmp_path: Path) -> Path:
    path = tmp_path / "vm-inventory.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """CREATE TABLE vm_inventory (
                vm_name TEXT PRIMARY KEY,
                application_name TEXT,
                available INTEGER,
                status TEXT,
                directory_present INTEGER,
                reusable INTEGER
            )"""
        )
        connection.executemany(
            "INSERT INTO vm_inventory VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("abcd", None, 1, "complete", 1, 0),
                ("wxyz", None, 0, "complete", 1, 0),
            ],
        )
    return path


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("@Bot 正在提审的应用", "applications"),
        ('<at user_id="ou_bot">提审机器人</at> 正在提审的应用', "applications"),
        ("/提审 应用列表", "applications"),
        ("@Bot 可用的虚拟机", "vms"),
        ('<at user_id="ou_bot">提审机器人</at> /提审 可用VM', "vms"),
        ("/提审 资源", "all"),
    ],
)
def test_project_query_intent_strips_mentions_and_supports_exact_phrases(
    text: str, intent: str
) -> None:
    assert feishu_bot.project_query_intent(text) == intent


def test_active_application_query_is_local_started_unfinished_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_registry(
        monkeypatch,
        tmp_path,
        [
            {
                "id": "sensitive-run-id",
                "chat_id": PROJECT_CHAT,
                "project_chat_id": PROJECT_CHAT,
                "source_chat_id": "sensitive-chat-id",
                "app_name": "SampleApp",
                "submission_data": {
                    "host_machine": LOCAL_HOST,
                    "proxy": {"password": "sensitive-password"},
                },
                "lifecycle": {"started_at": "2026-08-26T08:00:00+00:00"},
                "current_skill": "utm-image",
                "prompt_path": "/private/runtime/sensitive-prompt.md",
                "raw_text": "sensitive raw registration data",
            },
            {
                "app_name": "ForeignChat",
                "chat_id": "other-chat",
                "project_chat_id": PROJECT_CHAT,
                "submission_data": {"host_machine": LOCAL_HOST},
                "lifecycle": {"started_at": "2026-08-26T08:00:00+00:00"},
            },
            {
                "app_name": "MissingProjectChat",
                "chat_id": PROJECT_CHAT,
                "submission_data": {"host_machine": LOCAL_HOST},
                "lifecycle": {"started_at": "2026-08-26T08:00:00+00:00"},
            },
            {
                "app_name": "EmptyProjectChat",
                "chat_id": PROJECT_CHAT,
                "project_chat_id": "",
                "submission_data": {"host_machine": LOCAL_HOST},
                "lifecycle": {"started_at": "2026-08-26T08:00:00+00:00"},
            },
            {
                "app_name": "MismatchedProjectChat",
                "chat_id": PROJECT_CHAT,
                "project_chat_id": "other-chat",
                "submission_data": {"host_machine": LOCAL_HOST},
                "lifecycle": {"started_at": "2026-08-26T08:00:00+00:00"},
            },
            {
                "app_name": "OtherHost",
                "submission_data": {"host_machine": "host-b"},
                "lifecycle": {"started_at": "2026-08-26T08:00:00+00:00"},
            },
            {
                "app_name": "NeverStarted",
                "submission_data": {"host_machine": LOCAL_HOST},
                "lifecycle": {},
            },
            {
                "app_name": "AlreadyFinished",
                "submission_data": {"host_machine": LOCAL_HOST},
                "lifecycle": {
                    "started_at": "2026-08-26T08:00:00+00:00",
                    "finished_at": "2026-08-26T09:00:00+00:00",
                },
            },
        ],
    )

    reply = feishu_bot.handle_project_query(
        sample_config(), "@Bot 正在提审的应用", PROJECT_CHAT
    )

    assert reply is not None
    assert "SampleApp" in reply
    assert "utm-image" in reply
    assert "OtherHost" not in reply
    assert "ForeignChat" not in reply
    assert "MissingProjectChat" not in reply
    assert "EmptyProjectChat" not in reply
    assert "MismatchedProjectChat" not in reply
    assert "NeverStarted" not in reply
    assert "AlreadyFinished" not in reply
    for secret in (
        "sensitive-run-id",
        "sensitive-chat-id",
        "/private/runtime",
        "sensitive-password",
        "sensitive raw registration data",
    ):
        assert secret not in reply


def test_foreign_project_runs_are_excluded_without_mutating_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    registry = install_registry(
        monkeypatch,
        tmp_path,
        [
            {
                "app_name": "ForeignOnly",
                "chat_id": "other-chat",
                "project_chat_id": "other-chat",
                "submission_data": {"host_machine": LOCAL_HOST},
                "lifecycle": {"started_at": "2026-08-26T08:00:00+00:00"},
            }
        ],
    )
    before = registry.read_bytes()

    assert feishu_bot.handle_project_query(
        sample_config(), "/提审 应用列表", PROJECT_CHAT
    ) == "正在提审的应用（0）：无"
    assert registry.read_bytes() == before


def test_query_dispatches_before_generic_assistant(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_registry(monkeypatch, tmp_path, [])
    monkeypatch.setattr(
        feishu_bot,
        "ask_assistant",
        lambda *_args: pytest.fail("deterministic query must precede assistant fallback"),
    )

    assert feishu_bot.handle_incoming_text(
        sample_config(), "/提审 应用列表", PROJECT_CHAT, source="test"
    ) == "正在提审的应用（0）：无"


def test_vm_query_reads_inventory_without_mutating_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database = create_inventory(tmp_path)
    database.chmod(0o400)
    monkeypatch.setattr(feishu_bot, "VM_INVENTORY_DATABASE", database)
    before = (
        database.read_bytes(),
        database.stat().st_mtime_ns,
        stat.S_IMODE(database.stat().st_mode),
    )

    reply = feishu_bot.handle_project_query(
        sample_config(), "@Bot 可用的虚拟机", PROJECT_CHAT
    )

    assert reply == "可用虚拟机（1）：abcd"
    assert (
        database.read_bytes(),
        database.stat().st_mtime_ns,
        stat.S_IMODE(database.stat().st_mode),
    ) == before
    assert not Path(f"{database}-wal").exists()
    assert not Path(f"{database}-shm").exists()


@pytest.mark.parametrize("host", ["", "   "])
@pytest.mark.parametrize("query", ["/提审 应用列表", "/提审 资源"])
def test_application_queries_fail_when_exact_local_host_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    host: str,
    query: str,
) -> None:
    install_registry(monkeypatch, tmp_path, [])
    database = create_inventory(tmp_path)
    monkeypatch.setattr(feishu_bot, "VM_INVENTORY_DATABASE", database)

    assert feishu_bot.handle_project_query(
        sample_config(submission_host_machine=host), query, PROJECT_CHAT
    ) == "查询失败"


@pytest.mark.parametrize("host", ["", "   "])
def test_vm_only_query_does_not_require_submission_host(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    host: str,
) -> None:
    database = create_inventory(tmp_path)
    monkeypatch.setattr(feishu_bot, "VM_INVENTORY_DATABASE", database)

    assert feishu_bot.handle_project_query(
        sample_config(submission_host_machine=host), "/提审 可用VM", PROJECT_CHAT
    ) == "可用虚拟机（1）：abcd"


@pytest.mark.parametrize("failure", ["missing", "corrupt", "wrong-shape", "symlink"])
def test_strict_run_registry_failures_are_not_reported_as_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure: str,
) -> None:
    path = tmp_path / "feishu-runs.json"
    if failure == "corrupt":
        path.write_text("{not-json", encoding="utf-8")
    elif failure == "wrong-shape":
        path.write_text('{"runs": {}}', encoding="utf-8")
    elif failure == "symlink":
        target = tmp_path / "target.json"
        target.write_text('{"runs": []}', encoding="utf-8")
        path.symlink_to(target)
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", path)

    assert feishu_bot.handle_project_query(
        sample_config(), "/提审 应用列表", PROJECT_CHAT
    ) == "查询失败"


def test_unauthorized_or_unconfigured_chats_receive_no_query_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        feishu_bot,
        "ask_assistant",
        lambda *_args: pytest.fail("unauthorized query must not reach assistant"),
    )

    assert feishu_bot.handle_project_query(
        sample_config(), "@Bot 可用的虚拟机", "other-chat"
    ) is None
    assert feishu_bot.handle_project_query(
        sample_config(allowed_chat_id=""), "@Bot 可用的虚拟机", PROJECT_CHAT
    ) is None
    assert feishu_bot.handle_incoming_text(
        sample_config(), "@Bot 可用的虚拟机", "other-chat", source="test"
    ) == ""
    assert feishu_bot.handle_incoming_text(
        sample_config(allowed_chat_id=""),
        "/提审 可用VM",
        PROJECT_CHAT,
        source="test",
    ) == ""
