from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from services import feishu_bot


def run(run_id: str, app_name: str, host: str, status: str = "runner_started") -> dict[str, Any]:
    return {
        "id": run_id,
        "app_name": app_name,
        "chat_id": "project-chat",
        "project_chat_id": "project-chat",
        "submission_data": {"app_name": app_name, "host_machine": host},
        "status": status,
        "created_at": "2026-08-26T00:00:00+00:00",
        "updated_at": "2026-08-26T00:00:00+00:00",
        "events": [],
    }


def test_second_application_on_same_host_is_rejected_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", tmp_path / "runs.json")
    feishu_bot._save_structured_start_run(run("run-a", "AppA", "host-a"))

    with pytest.raises(
        feishu_bot.SubmissionStartError, match="当前宿主已有应用正在提审"
    ):
        feishu_bot._save_structured_start_run(run("run-b", "AppB", "host-a"))

    stored = json.loads(feishu_bot.RUNS_FILE.read_text(encoding="utf-8"))["runs"]
    assert [item["app_name"] for item in stored] == ["AppA"]


def test_active_application_on_another_host_does_not_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", tmp_path / "runs.json")
    feishu_bot._save_structured_start_run(run("run-a", "AppA", "host-a"))

    feishu_bot._save_structured_start_run(run("run-b", "AppB", "host-b"))

    stored = json.loads(feishu_bot.RUNS_FILE.read_text(encoding="utf-8"))["runs"]
    assert [item["app_name"] for item in stored] == ["AppA", "AppB"]


@pytest.mark.parametrize(
    "terminal",
    (
        {"status": "completed"},
        {"status": "runner_failed"},
        {"status": "stopped"},
        {
            "status": "running",
            "lifecycle": {
                "finished_at": "2026-08-26T01:00:00+00:00",
                "outcome": "success",
            },
        },
    ),
)
def test_terminal_application_on_same_host_allows_next(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    terminal: dict[str, Any],
) -> None:
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", tmp_path / "runs.json")
    first = run("run-a", "AppA", "host-a")
    first.update(terminal)
    feishu_bot._save_structured_start_run(first)

    feishu_bot._save_structured_start_run(run("run-b", "AppB", "host-a"))

    stored = json.loads(feishu_bot.RUNS_FILE.read_text(encoding="utf-8"))["runs"]
    assert [item["app_name"] for item in stored] == ["AppA", "AppB"]


def test_two_simultaneous_starts_on_same_host_only_store_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", tmp_path / "runs.json")
    barrier = threading.Barrier(2)
    accepted: list[str] = []
    rejected: list[str] = []

    def save(item: dict[str, Any]) -> None:
        barrier.wait()
        try:
            feishu_bot._save_structured_start_run(item)
            accepted.append(item["app_name"])
        except feishu_bot.SubmissionStartError:
            rejected.append(item["app_name"])

    threads = [
        threading.Thread(target=save, args=(run("run-a", "AppA", "host-a"),)),
        threading.Thread(target=save, args=(run("run-b", "AppB", "host-a"),)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert len(accepted) == 1
    assert len(rejected) == 1
    stored = json.loads(feishu_bot.RUNS_FILE.read_text(encoding="utf-8"))["runs"]
    assert len(stored) == 1
