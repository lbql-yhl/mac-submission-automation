from __future__ import annotations

import stat
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from services import feishu_bot, submission_runner
from services.host_config import ConfigurationError
from services.submission_observability import build_submission_end_card


PROJECT_CHAT = "project-chat"
REPORT_CHAT = "report-chat"
LOCAL_HOST = "host-a"


def sample_run(
    *,
    run_id: str = "run-1",
    chat_id: str = PROJECT_CHAT,
    host: str = LOCAL_HOST,
) -> dict[str, Any]:
    return {
        "id": run_id,
        "chat_id": chat_id,
        "app_name": "SampleApp",
        "submission_data": {"host_machine": host},
        "status": "queued",
        "created_at": "2026-08-26T08:00:00+00:00",
        "updated_at": "2026-08-26T08:00:00+00:00",
        "events": [],
    }


def sample_config(**overrides: Any) -> SimpleNamespace:
    values = {
        "allowed_chat_id": PROJECT_CHAT,
        "daily_report_chat_id": REPORT_CHAT,
        "submission_host_machine": LOCAL_HOST,
        "host": "127.0.0.1",
        "port": 8787,
        "poll_interval_seconds": 15,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def lifecycle_args(**overrides: Any) -> SimpleNamespace:
    values = {
        "run_id": "run-1",
        "chat_id": "",
        "skill": "",
        "stage": "",
        "outcome": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def install_registry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *runs: dict[str, Any],
) -> Path:
    runs_file = tmp_path / "feishu-runs.json"
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", runs_file)
    feishu_bot.write_json(runs_file, {"runs": list(runs)})
    return runs_file


def card_lines(card: dict[str, Any]) -> list[str]:
    return card["body"]["elements"][0]["text"]["content"].splitlines()


def test_run_start_binds_exact_project_group_and_confirms_delivery(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run = sample_run()
    install_registry(monkeypatch, tmp_path, run)
    sent: list[tuple[str, dict[str, Any], str]] = []

    def send_card(
        _client: Any,
        chat_id: str,
        card: dict[str, Any],
        *,
        message_uuid: str = "",
    ) -> dict[str, Any]:
        sent.append((chat_id, card, message_uuid))
        return {"data": {"message_id": "start-message"}}

    monkeypatch.setattr(feishu_bot.FeishuClient, "send_card", send_card)

    assert feishu_bot.notify_run_start(lifecycle_args(), sample_config()) == 0
    first = feishu_bot.find_run(run["id"])
    assert first is not None
    assert first["project_chat_id"] == PROJECT_CHAT
    assert first["lifecycle"]["started_at"]
    assert first["lifecycle"]["start_message_uuid"]
    assert first["lifecycle"]["start_message_id"] == "start-message"
    assert sent[0][0] == PROJECT_CHAT
    assert sent[0][2] == first["lifecycle"]["start_message_uuid"]
    assert card_lines(sent[0][1])[:2] == [
        "**应用**：SampleApp",
        "**宿主**：host-a",
    ]

    assert feishu_bot.notify_run_start(lifecycle_args(), sample_config()) == 0
    assert len(sent) == 1
    assert feishu_bot.find_run(run["id"])["lifecycle"] == first["lifecycle"]


def test_run_start_reuses_uuid_until_message_id_is_confirmed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_registry(monkeypatch, tmp_path, sample_run())
    sent_uuids: list[str] = []
    responses = iter(({"data": {}}, {"data": {"message_id": "confirmed-start"}}))

    def send_card(_client: Any, _chat: str, _card: dict[str, Any], *, message_uuid: str = ""):
        sent_uuids.append(message_uuid)
        return next(responses)

    monkeypatch.setattr(feishu_bot.FeishuClient, "send_card", send_card)

    assert feishu_bot.notify_run_start(lifecycle_args(), sample_config()) == 2
    pending = feishu_bot.find_run("run-1")
    assert pending is not None
    assert pending["lifecycle"]["started_at"]
    assert pending["lifecycle"]["start_message_uuid"] == sent_uuids[0]
    assert not pending["lifecycle"].get("start_message_id")

    assert feishu_bot.notify_run_start(lifecycle_args(), sample_config()) == 0
    confirmed = feishu_bot.find_run("run-1")
    assert confirmed is not None
    assert sent_uuids == [sent_uuids[0], sent_uuids[0]]
    assert confirmed["lifecycle"]["start_message_id"] == "confirmed-start"


@pytest.mark.parametrize(
    ("run_changes", "config_changes", "requested"),
    [
        ({"chat_id": "other-chat"}, {}, ""),
        ({"submission_data": {"host_machine": "other-host"}}, {}, ""),
        ({}, {"submission_host_machine": "other-host"}, ""),
        ({}, {"allowed_chat_id": ""}, ""),
        ({}, {"allowed_chat_id": REPORT_CHAT}, ""),
        ({"project_chat_id": "other-chat"}, {}, ""),
        ({}, {}, "other-chat"),
    ],
)
def test_run_start_rejects_wrong_host_chat_report_route_or_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    run_changes: dict[str, Any],
    config_changes: dict[str, Any],
    requested: str,
) -> None:
    run = sample_run()
    run.update(run_changes)
    install_registry(monkeypatch, tmp_path, run)
    monkeypatch.setattr(
        feishu_bot.FeishuClient,
        "send_card",
        lambda *_args, **_kwargs: pytest.fail("rejected route must not send"),
    )

    assert (
        feishu_bot.notify_run_start(
            lifecycle_args(chat_id=requested), sample_config(**config_changes)
        )
        == 2
    )
    stored = feishu_bot.find_run("run-1")
    assert stored is not None
    assert "lifecycle" not in stored
    if "project_chat_id" not in run_changes:
        assert "project_chat_id" not in stored


def test_skill_attempts_are_ordered_retriable_and_close_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run = sample_run()
    run.update(
        {
            "project_chat_id": PROJECT_CHAT,
            "lifecycle": {
                "started_at": "2026-08-26T08:00:00+00:00",
                "start_message_uuid": "stable-start",
                "start_message_id": "start-message",
            },
        }
    )
    install_registry(monkeypatch, tmp_path, run)

    failure_args = lifecycle_args(
        skill="utm-vm-clone",
        stage="boot verification",
        evidence="must-not-be-persisted",
        fault="must-not-be-persisted",
    )
    assert feishu_bot.record_skill_lifecycle(failure_args, sample_config(), "started") == 0
    assert feishu_bot.record_skill_lifecycle(failure_args, sample_config(), "failed") == 0
    assert feishu_bot.record_skill_lifecycle(failure_args, sample_config(), "failed") == 2

    assert feishu_bot.record_skill_lifecycle(failure_args, sample_config(), "started") == 0
    assert feishu_bot.record_skill_lifecycle(failure_args, sample_config(), "succeeded") == 0
    notion_args = lifecycle_args(skill="utm-notion", stage="field verification")
    assert feishu_bot.record_skill_lifecycle(notion_args, sample_config(), "started") == 0
    assert feishu_bot.record_skill_lifecycle(notion_args, sample_config(), "succeeded") == 0

    stored = feishu_bot.find_run("run-1")
    assert stored is not None
    attempts = stored["skill_attempts"]
    assert [(item["skill"], item["status"]) for item in attempts] == [
        ("utm-vm-clone", "failed"),
        ("utm-vm-clone", "succeeded"),
        ("utm-notion", "succeeded"),
    ]
    assert all(item["started_at"] and item["finished_at"] for item in attempts)
    assert attempts[0]["stage"] == "boot verification"
    assert "evidence" not in attempts[0]
    assert "fault" not in attempts[0]
    assert card_lines(
        build_submission_end_card(
            {
                **stored,
                "lifecycle": {
                    **stored["lifecycle"],
                    "outcome": "success",
                    "duration_seconds": 1,
                },
            }
        )
    )[3:5] == [
        "**执行技能**：utm-vm-clone、utm-notion",
        "**流程故障次数**：1",
    ]


def test_skill_lifecycle_requires_confirmed_start_valid_skill_and_open_match(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_registry(monkeypatch, tmp_path, sample_run())
    assert (
        feishu_bot.record_skill_lifecycle(
            lifecycle_args(skill="utm-vm-clone"), sample_config(), "started"
        )
        == 2
    )

    run = sample_run()
    run.update(
        {
            "project_chat_id": PROJECT_CHAT,
            "lifecycle": {
                "started_at": "2026-08-26T08:00:00+00:00",
                "start_message_uuid": "stable-start",
                "start_message_id": "start-message",
            },
        }
    )
    install_registry(monkeypatch, tmp_path, run)
    assert (
        feishu_bot.record_skill_lifecycle(
            lifecycle_args(skill="not-a-mainline-skill"), sample_config(), "started"
        )
        == 2
    )
    assert (
        feishu_bot.record_skill_lifecycle(
            lifecycle_args(skill="utm-notion"), sample_config(), "succeeded"
        )
        == 2
    )
    assert (
        feishu_bot.record_skill_lifecycle(
            lifecycle_args(skill="utm-vm-clone"), sample_config(), "started"
        )
        == 0
    )
    assert (
        feishu_bot.record_skill_lifecycle(
            lifecycle_args(skill="utm-notion"), sample_config(), "failed"
        )
        == 2
    )


def test_run_finish_freezes_terminal_state_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run = sample_run()
    run.update(
        {
            "project_chat_id": PROJECT_CHAT,
            "lifecycle": {
                "started_at": "2026-08-26T08:00:00+00:00",
                "start_message_uuid": "stable-start",
                "start_message_id": "start-message",
            },
            "skill_attempts": [
                {
                    "skill": "utm-vm-clone",
                    "started_at": "2026-08-26T08:00:01+00:00",
                    "finished_at": "2026-08-26T08:00:02+00:00",
                    "status": "succeeded",
                }
            ],
        }
    )
    install_registry(monkeypatch, tmp_path, run)
    monkeypatch.setattr(feishu_bot, "utc_now", lambda: "2026-08-26T08:01:05+00:00")
    sent: list[str] = []

    def send_card(_client: Any, _chat: str, _card: dict[str, Any], *, message_uuid: str = ""):
        sent.append(message_uuid)
        return {"data": {"message_id": "end-message"}}

    monkeypatch.setattr(feishu_bot.FeishuClient, "send_card", send_card)
    finish = lifecycle_args(outcome="success")

    assert feishu_bot.notify_run_finish(finish, sample_config()) == 0
    terminal = feishu_bot.find_run("run-1")
    assert terminal is not None
    lifecycle = terminal["lifecycle"]
    assert lifecycle["finished_at"] == "2026-08-26T08:01:05+00:00"
    assert lifecycle["duration_seconds"] == 65
    assert lifecycle["outcome"] == "success"
    assert lifecycle["end_message_id"] == "end-message"
    assert lifecycle["end_message_uuid"] == sent[0]
    assert datetime.fromisoformat(lifecycle["finished_at"]).tzinfo is not None

    assert feishu_bot.notify_run_finish(finish, sample_config()) == 0
    assert feishu_bot.notify_run_finish(lifecycle_args(outcome="failed"), sample_config()) == 2
    assert sent == [sent[0]]
    assert feishu_bot.find_run("run-1")["lifecycle"] == lifecycle


def test_run_finish_reuses_uuid_after_unconfirmed_delivery_and_rejects_conflict(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run = sample_run()
    run.update(
        {
            "project_chat_id": PROJECT_CHAT,
            "lifecycle": {
                "started_at": "2026-08-26T08:00:00+00:00",
                "start_message_uuid": "stable-start",
                "start_message_id": "start-message",
            },
        }
    )
    install_registry(monkeypatch, tmp_path, run)
    sent_uuids: list[str] = []
    responses = iter(({"data": {}}, {"data": {"message_id": "confirmed-end"}}))

    def send_card(_client: Any, _chat: str, _card: dict[str, Any], *, message_uuid: str = ""):
        sent_uuids.append(message_uuid)
        return next(responses)

    monkeypatch.setattr(feishu_bot.FeishuClient, "send_card", send_card)
    finish = lifecycle_args(outcome="stopped")
    assert feishu_bot.notify_run_finish(finish, sample_config()) == 2
    assert feishu_bot.notify_run_finish(lifecycle_args(outcome="failed"), sample_config()) == 2
    assert feishu_bot.notify_run_finish(finish, sample_config()) == 0
    assert sent_uuids == [sent_uuids[0], sent_uuids[0]]
    assert feishu_bot.find_run("run-1")["lifecycle"]["end_message_id"] == "confirmed-end"


def test_run_finish_success_rejects_an_open_skill_attempt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run = sample_run()
    run.update(
        {
            "project_chat_id": PROJECT_CHAT,
            "lifecycle": {
                "started_at": "2026-08-26T08:00:00+00:00",
                "start_message_uuid": "stable-start",
                "start_message_id": "start-message",
            },
            "skill_attempts": [
                {
                    "skill": "utm-vm-clone",
                    "started_at": "2026-08-26T08:00:01+00:00",
                    "status": "started",
                }
            ],
        }
    )
    install_registry(monkeypatch, tmp_path, run)
    monkeypatch.setattr(
        feishu_bot.FeishuClient,
        "send_card",
        lambda *_args, **_kwargs: pytest.fail("invalid success must not send"),
    )

    assert (
        feishu_bot.notify_run_finish(
            lifecycle_args(outcome="success"), sample_config()
        )
        == 2
    )
    stored = feishu_bot.find_run("run-1")
    assert stored is not None
    assert stored["skill_attempts"][0]["status"] == "started"
    assert "finished_at" not in stored["skill_attempts"][0]
    assert "outcome" not in stored["lifecycle"]


@pytest.mark.parametrize(
    ("outcome", "attempt_status", "failure_count"),
    [("failed", "failed", 1), ("stopped", "stopped", 0)],
)
def test_run_finish_closes_one_open_attempt_before_terminal_card(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    outcome: str,
    attempt_status: str,
    failure_count: int,
) -> None:
    run = sample_run()
    run.update(
        {
            "project_chat_id": PROJECT_CHAT,
            "lifecycle": {
                "started_at": "2026-08-26T08:00:00+00:00",
                "start_message_uuid": "stable-start",
                "start_message_id": "start-message",
            },
            "skill_attempts": [
                {
                    "skill": "utm-vm-clone",
                    "started_at": "2026-08-26T08:00:01+00:00",
                    "status": "started",
                }
            ],
        }
    )
    install_registry(monkeypatch, tmp_path, run)
    monkeypatch.setattr(feishu_bot, "utc_now", lambda: "2026-08-26T08:01:05+00:00")
    sent_cards: list[dict[str, Any]] = []

    def send_card(
        _client: Any,
        _chat: str,
        card: dict[str, Any],
        *,
        message_uuid: str = "",
    ) -> dict[str, Any]:
        persisted = feishu_bot.find_run("run-1")
        assert persisted is not None
        assert persisted["skill_attempts"][0]["status"] == attempt_status
        assert persisted["skill_attempts"][0]["finished_at"] == (
            "2026-08-26T08:01:05+00:00"
        )
        assert persisted["lifecycle"]["outcome"] == outcome
        sent_cards.append(card)
        return {"data": {"message_id": "end-message"}}

    monkeypatch.setattr(feishu_bot.FeishuClient, "send_card", send_card)
    finish = lifecycle_args(outcome=outcome)

    assert feishu_bot.notify_run_finish(finish, sample_config()) == 0
    assert feishu_bot.notify_run_finish(finish, sample_config()) == 0
    assert len(sent_cards) == 1
    assert f"**流程故障次数**：{failure_count}" in card_lines(sent_cards[0])


@pytest.mark.parametrize(
    "attempts",
    [
        "not-a-list",
        [
            {
                "skill": "utm-vm-clone",
                "started_at": "2026-08-26T08:00:01+00:00",
                "status": "started",
            },
            {
                "skill": "utm-notion",
                "started_at": "2026-08-26T08:00:02+00:00",
                "status": "started",
            },
        ],
        [{"skill": "utm-vm-clone", "status": "started"}],
        [
            {
                "skill": "not-a-mainline-skill",
                "started_at": "2026-08-26T08:00:01+00:00",
                "status": "started",
            }
        ],
    ],
)
def test_run_finish_rejects_malformed_or_multiple_open_attempts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    attempts: Any,
) -> None:
    run = sample_run()
    run.update(
        {
            "project_chat_id": PROJECT_CHAT,
            "lifecycle": {
                "started_at": "2026-08-26T08:00:00+00:00",
                "start_message_uuid": "stable-start",
                "start_message_id": "start-message",
            },
            "skill_attempts": attempts,
        }
    )
    install_registry(monkeypatch, tmp_path, run)
    monkeypatch.setattr(
        feishu_bot.FeishuClient,
        "send_card",
        lambda *_args, **_kwargs: pytest.fail("malformed finish must not send"),
    )

    assert (
        feishu_bot.notify_run_finish(
            lifecycle_args(outcome="failed"), sample_config()
        )
        == 2
    )
    stored = feishu_bot.find_run("run-1")
    assert stored is not None
    assert "outcome" not in stored["lifecycle"]


def test_cli_accepts_and_dispatches_all_lifecycle_modes_and_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = sample_config()
    monkeypatch.setattr(feishu_bot.os, "umask", lambda _value: None)
    monkeypatch.setattr(feishu_bot, "harden_runtime_metadata", lambda: None)
    monkeypatch.setattr(feishu_bot, "load_config", lambda: config)
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        feishu_bot,
        "notify_run_start",
        lambda args, _config: calls.append((args.mode, args.skill, args.outcome)) or 0,
    )
    monkeypatch.setattr(
        feishu_bot,
        "notify_run_finish",
        lambda args, _config: calls.append((args.mode, args.skill, args.outcome)) or 0,
    )
    monkeypatch.setattr(
        feishu_bot,
        "record_skill_lifecycle",
        lambda args, _config, state: calls.append((state, args.skill, args.outcome)) or 0,
    )

    invocations = [
        ["feishu_bot", "run-start"],
        ["feishu_bot", "skill-start", "--skill", "utm-vm-clone"],
        ["feishu_bot", "skill-success", "--skill", "utm-vm-clone"],
        ["feishu_bot", "skill-failure", "--skill", "utm-vm-clone"],
        ["feishu_bot", "run-finish", "--outcome", "stopped"],
    ]
    for argv in invocations:
        monkeypatch.setattr(sys, "argv", argv)
        assert feishu_bot.main() == 0

    assert calls == [
        ("run-start", "", ""),
        ("started", "utm-vm-clone", ""),
        ("succeeded", "utm-vm-clone", ""),
        ("failed", "utm-vm-clone", ""),
        ("run-finish", "", "stopped"),
    ]


def test_all_bot_registry_writers_use_one_lock_and_lock_is_user_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run = sample_run()
    install_registry(monkeypatch, tmp_path, run)
    real_lock = feishu_bot.locked_run_registry
    entries: list[str] = []

    @contextmanager
    def observed_lock():
        entries.append("entered")
        with real_lock():
            yield

    monkeypatch.setattr(feishu_bot, "locked_run_registry", observed_lock)
    feishu_bot.save_run(sample_run(run_id="run-2"))
    assert feishu_bot.mutate_run("run-1", lambda item: item.update(marker="mutated"))
    assert feishu_bot.update_latest_run(PROJECT_CHAT, "updated", "safe note")
    assert entries == ["entered", "entered", "entered"]

    lock_file = Path(f"{feishu_bot.RUNS_FILE}.lock")
    assert stat.S_IMODE(lock_file.stat().st_mode) == 0o600
    outside = tmp_path / "outside.lock"
    outside.write_text("outside", encoding="utf-8")
    lock_file.unlink()
    lock_file.symlink_to(outside)
    with pytest.raises(ConfigurationError):
        feishu_bot.save_run(sample_run(run_id="run-3"))
    assert outside.read_text(encoding="utf-8") == "outside"


def test_legacy_append_event_uses_shared_mutation_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = sample_run()
    calls: list[str] = []

    def mutate(run_id: str, mutator: Any) -> dict[str, Any]:
        calls.append(run_id)
        mutator(run)
        return run

    monkeypatch.setattr(submission_runner.feishu_bot, "mutate_run", mutate)
    submission_runner.append_run_event("run-1", "running", "safe note", output="path")

    assert calls == ["run-1"]
    assert run["status"] == "running"
    assert run["output"] == "path"
    assert run["events"][-1]["status"] == "running"


def test_legacy_runner_claim_is_atomic_and_rejects_later_claims(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run = sample_run()
    run.update(
        {
            "project_chat_id": PROJECT_CHAT,
            "lifecycle": {
                "started_at": "2026-08-26T08:00:00+00:00",
                "start_message_uuid": "stable-start",
                "start_message_id": "start-message",
            },
        }
    )
    install_registry(monkeypatch, tmp_path, run)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(submission_runner.claim_legacy_runner, ["run-1"] * 2))

    assert sorted(results) == [False, True]
    assert submission_runner.claim_legacy_runner("run-1") is False
    stored = feishu_bot.find_run("run-1")
    assert stored is not None
    assert set(stored["legacy_runner_claim"]) == {"claimed_at", "generation"}
    assert stored["legacy_runner_claim"]["claimed_at"]
    assert stored["legacy_runner_claim"]["generation"]


def test_legacy_runner_terminal_restart_is_rejected_before_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run = sample_run(run_id="sensitive-run-id")
    run.update(
        {
            "project_chat_id": PROJECT_CHAT,
            "lifecycle": {
                "started_at": "2026-08-26T08:00:00+00:00",
                "start_message_uuid": "stable-start",
                "start_message_id": "start-message",
                "finished_at": "2026-08-26T08:01:00+00:00",
                "outcome": "success",
                "duration_seconds": 60,
                "end_message_uuid": "stable-end",
                "end_message_id": "end-message",
            },
        }
    )
    install_registry(monkeypatch, tmp_path, run)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe prompt", encoding="utf-8")
    monkeypatch.setenv("SUBMISSION_RUN_ID", "sensitive-run-id")
    monkeypatch.setenv("SUBMISSION_PROMPT_PATH", str(prompt))
    monkeypatch.setattr(submission_runner.feishu_bot, "load_config", sample_config)
    monkeypatch.setattr(
        submission_runner.feishu_bot, "notify_run_start", lambda *_args: 0
    )
    monkeypatch.setattr(
        submission_runner.feishu_bot,
        "notify_run_finish",
        lambda *_args: pytest.fail("a rejected restart cannot finish the run"),
    )
    monkeypatch.setattr(
        submission_runner,
        "append_run_event",
        lambda *_args, **_kwargs: pytest.fail("a rejected restart cannot record events"),
    )
    monkeypatch.setattr(
        submission_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("a rejected restart cannot spawn Codex"),
    )

    assert submission_runner.main() == 2
    diagnostic = capsys.readouterr().err
    assert "claim was refused" in diagnostic
    assert "sensitive-run-id" not in diagnostic


@pytest.mark.parametrize(
    ("runner_result", "expected_code", "expected_outcome"),
    [(0, 0, "success"), (7, 7, "failed")],
)
def test_legacy_runner_confirms_start_before_spawn_and_finishes_terminal_branches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    runner_result: int,
    expected_code: int,
    expected_outcome: str,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe prompt", encoding="utf-8")
    monkeypatch.setenv("SUBMISSION_RUN_ID", "run-1")
    monkeypatch.setenv("SUBMISSION_PROMPT_PATH", str(prompt))
    monkeypatch.setattr(submission_runner, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(submission_runner.feishu_bot, "load_config", lambda: sample_config())
    order: list[str] = []
    monkeypatch.setattr(
        submission_runner.feishu_bot,
        "notify_run_start",
        lambda _args, _config: order.append("start") or 0,
    )
    monkeypatch.setattr(
        submission_runner.feishu_bot,
        "notify_run_finish",
        lambda args, _config: order.append(f"finish:{args.outcome}") or 0,
    )
    monkeypatch.setattr(
        submission_runner,
        "claim_legacy_runner",
        lambda _run_id: order.append("claim") or True,
        raising=False,
    )
    monkeypatch.setattr(submission_runner, "append_run_event", lambda *_args, **_kwargs: None)

    def run_codex(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        order.append("spawn")
        return SimpleNamespace(returncode=runner_result, stdout="")

    monkeypatch.setattr(submission_runner.subprocess, "run", run_codex)

    assert submission_runner.main() == expected_code
    assert order == ["start", "claim", "spawn", f"finish:{expected_outcome}"]


def test_legacy_runner_refuses_spawn_without_confirmed_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe prompt", encoding="utf-8")
    monkeypatch.setenv("SUBMISSION_RUN_ID", "run-1")
    monkeypatch.setenv("SUBMISSION_PROMPT_PATH", str(prompt))
    monkeypatch.setattr(submission_runner.feishu_bot, "load_config", lambda: sample_config())
    monkeypatch.setattr(
        submission_runner.feishu_bot, "notify_run_start", lambda *_args: 2
    )
    monkeypatch.setattr(
        submission_runner,
        "claim_legacy_runner",
        lambda _run_id: pytest.fail("an unconfirmed run cannot be claimed"),
        raising=False,
    )
    monkeypatch.setattr(
        submission_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("Codex must not spawn before confirmed start"),
    )

    assert submission_runner.main() == 2


def test_legacy_runner_finishes_failed_when_prompt_read_fails_after_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompt = tmp_path / "sensitive-prompt"
    prompt.write_bytes(b"\xff")

    monkeypatch.setenv("SUBMISSION_RUN_ID", "sensitive-run-id")
    monkeypatch.setenv("SUBMISSION_PROMPT_PATH", str(prompt))
    monkeypatch.setattr(submission_runner, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(submission_runner.feishu_bot, "load_config", sample_config)
    outcomes: list[str] = []
    monkeypatch.setattr(
        submission_runner.feishu_bot, "notify_run_start", lambda *_args: 0
    )
    monkeypatch.setattr(
        submission_runner.feishu_bot,
        "notify_run_finish",
        lambda args, _config: outcomes.append(args.outcome) or 0,
    )
    monkeypatch.setattr(
        submission_runner, "claim_legacy_runner", lambda _run_id: True, raising=False
    )
    monkeypatch.setattr(submission_runner, "append_run_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        submission_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("Codex must not spawn without a prompt"),
    )

    with pytest.raises(UnicodeDecodeError):
        submission_runner.main()

    assert outcomes == ["failed"]
    diagnostic = capsys.readouterr().err
    assert "failed after confirmed start" in diagnostic
    assert "sensitive-run-id" not in diagnostic
    assert str(prompt) not in diagnostic


def test_legacy_runner_finishes_failed_when_initial_event_mutation_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe prompt", encoding="utf-8")
    failure = RuntimeError("sensitive-registry-details")
    monkeypatch.setenv("SUBMISSION_RUN_ID", "sensitive-run-id")
    monkeypatch.setenv("SUBMISSION_PROMPT_PATH", str(prompt))
    monkeypatch.setattr(submission_runner, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(submission_runner.feishu_bot, "load_config", sample_config)
    outcomes: list[str] = []
    monkeypatch.setattr(
        submission_runner.feishu_bot, "notify_run_start", lambda *_args: 0
    )
    monkeypatch.setattr(
        submission_runner.feishu_bot,
        "notify_run_finish",
        lambda args, _config: outcomes.append(args.outcome) or 0,
    )
    monkeypatch.setattr(
        submission_runner, "claim_legacy_runner", lambda _run_id: True, raising=False
    )
    monkeypatch.setattr(
        submission_runner, "append_run_event", lambda *_args, **_kwargs: (_ for _ in ()).throw(failure)
    )
    monkeypatch.setattr(
        submission_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("Codex must not spawn after registry failure"),
    )

    with pytest.raises(RuntimeError) as captured:
        submission_runner.main()

    assert captured.value is failure
    assert outcomes == ["failed"]
    diagnostic = capsys.readouterr().err
    assert "failed after confirmed start" in diagnostic
    assert "sensitive-registry-details" not in diagnostic
    assert "sensitive-run-id" not in diagnostic


def test_legacy_runner_returns_two_for_prestart_configuration_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe prompt", encoding="utf-8")
    failure = RuntimeError("sensitive-config-details")
    monkeypatch.setenv("SUBMISSION_RUN_ID", "sensitive-run-id")
    monkeypatch.setenv("SUBMISSION_PROMPT_PATH", str(prompt))
    monkeypatch.setattr(
        submission_runner.feishu_bot,
        "load_config",
        lambda: (_ for _ in ()).throw(failure),
    )
    monkeypatch.setattr(
        submission_runner.feishu_bot,
        "notify_run_start",
        lambda *_args: pytest.fail("start cannot be confirmed without configuration"),
    )
    monkeypatch.setattr(
        submission_runner.feishu_bot,
        "notify_run_finish",
        lambda *_args: pytest.fail("an unstarted run cannot be finished"),
    )

    assert submission_runner.main() == 2
    diagnostic = capsys.readouterr().err
    assert "configuration is unavailable" in diagnostic
    assert "sensitive-config-details" not in diagnostic
    assert "sensitive-run-id" not in diagnostic


def test_legacy_runner_success_notification_exception_does_not_change_outcome(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe prompt", encoding="utf-8")
    monkeypatch.setenv("SUBMISSION_RUN_ID", "sensitive-run-id")
    monkeypatch.setenv("SUBMISSION_PROMPT_PATH", str(prompt))
    monkeypatch.setattr(submission_runner, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(submission_runner.feishu_bot, "load_config", sample_config)
    monkeypatch.setattr(
        submission_runner.feishu_bot, "notify_run_start", lambda *_args: 0
    )
    monkeypatch.setattr(
        submission_runner, "claim_legacy_runner", lambda _run_id: True, raising=False
    )
    outcomes: list[str] = []

    def fail_success_delivery(args: SimpleNamespace, _config: Any) -> int:
        outcomes.append(args.outcome)
        raise RuntimeError("sensitive-delivery-details")

    monkeypatch.setattr(
        submission_runner.feishu_bot, "notify_run_finish", fail_success_delivery
    )
    statuses: list[str] = []
    monkeypatch.setattr(
        submission_runner,
        "append_run_event",
        lambda _run_id, status, _note, **_fields: statuses.append(status),
    )
    monkeypatch.setattr(
        submission_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=""),
    )

    assert submission_runner.main() == 2
    assert outcomes == ["success"]
    assert statuses == ["running", "runner_completed"]
    diagnostic = capsys.readouterr().err
    assert "terminal delivery failed" in diagnostic
    assert "sensitive-delivery-details" not in diagnostic
    assert "sensitive-run-id" not in diagnostic


def test_legacy_runner_success_event_failure_preserves_success_outcome(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe prompt", encoding="utf-8")
    monkeypatch.setenv("SUBMISSION_RUN_ID", "sensitive-run-id")
    monkeypatch.setenv("SUBMISSION_PROMPT_PATH", str(prompt))
    monkeypatch.setattr(submission_runner, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(submission_runner.feishu_bot, "load_config", sample_config)
    monkeypatch.setattr(
        submission_runner.feishu_bot, "notify_run_start", lambda *_args: 0
    )
    monkeypatch.setattr(
        submission_runner, "claim_legacy_runner", lambda _run_id: True, raising=False
    )
    outcomes: list[str] = []
    monkeypatch.setattr(
        submission_runner.feishu_bot,
        "notify_run_finish",
        lambda args, _config: outcomes.append(args.outcome) or 0,
    )
    statuses: list[str] = []

    def record_event(_run_id: str, status: str, _note: str, **_fields: str) -> None:
        statuses.append(status)
        if status == "runner_completed":
            raise RuntimeError("sensitive-completion-event-details")

    monkeypatch.setattr(submission_runner, "append_run_event", record_event)
    monkeypatch.setattr(
        submission_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=""),
    )

    assert submission_runner.main() == 0
    assert outcomes == ["success"]
    assert statuses == ["running", "runner_completed"]
    diagnostic = capsys.readouterr().err
    assert "terminal event could not be persisted" in diagnostic
    assert "sensitive-completion-event-details" not in diagnostic
    assert "sensitive-run-id" not in diagnostic


@pytest.mark.parametrize("terminal_exception", ("timeout", "interrupt"))
def test_legacy_runner_preserves_stopped_outcome_when_event_logging_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    terminal_exception: str,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("safe prompt", encoding="utf-8")
    monkeypatch.setenv("SUBMISSION_RUN_ID", "run-1")
    monkeypatch.setenv("SUBMISSION_PROMPT_PATH", str(prompt))
    monkeypatch.setattr(submission_runner, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(submission_runner.feishu_bot, "load_config", sample_config)
    outcomes: list[str] = []
    monkeypatch.setattr(
        submission_runner.feishu_bot, "notify_run_start", lambda *_args: 0
    )
    monkeypatch.setattr(
        submission_runner, "claim_legacy_runner", lambda _run_id: True, raising=False
    )
    monkeypatch.setattr(
        submission_runner.feishu_bot,
        "notify_run_finish",
        lambda args, _config: outcomes.append(args.outcome) or 0,
    )
    event_calls = 0

    def record_event(*_args: Any, **_kwargs: Any) -> None:
        nonlocal event_calls
        event_calls += 1
        if event_calls > 1:
            raise RuntimeError("sensitive-terminal-event-details")

    monkeypatch.setattr(submission_runner, "append_run_event", record_event)
    if terminal_exception == "timeout":
        failure: BaseException = submission_runner.subprocess.TimeoutExpired("codex", 1)
    else:
        failure = KeyboardInterrupt()
    monkeypatch.setattr(
        submission_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(failure),
    )

    if terminal_exception == "timeout":
        assert submission_runner.main() == 124
    else:
        with pytest.raises(KeyboardInterrupt):
            submission_runner.main()
    assert outcomes == ["stopped"]
