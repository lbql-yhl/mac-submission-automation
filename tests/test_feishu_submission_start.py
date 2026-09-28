from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from services import feishu_bot


PROJECT_CHAT = "project-chat"
LOCAL_HOST = "host-a"
FIXTURE_APP_IDENTIFIER = "fixture-app"
FIXTURE_APP_CREDENTIAL = "fixture-secret"
BASE_RUN_ID = "kf-20260803-fallline"
COMMAND = """<at user_id="ou_bot">GaleOpsBrain</at> /提审 FallLine
执行技能
utm-notion
utm-clash-ip
utm-login
utm-edit
utm-key
utm-apps
utm-business"""
REQUESTED_SKILLS = (
    "utm-notion",
    "utm-clash-ip",
    "utm-login",
    "utm-edit",
    "utm-key",
    "utm-apps",
    "utm-business",
)


def sample_config(**overrides: Any):
    config = feishu_bot.load_config(
        environ={
            "FEISHU_ALLOWED_CHAT_ID": PROJECT_CHAT,
            "SUBMISSION_HOST_MACHINE": LOCAL_HOST,
            "FEISHU_ASSISTANT_ENABLED": "0",
        }
    )
    return replace(config, **overrides)


def test_submission_runner_always_uses_current_repository_entrypoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeProcess:
        pid = 4321

    def popen(command: list[str], **kwargs: Any) -> FakeProcess:
        captured["command"] = command
        captured["cwd"] = kwargs.get("cwd")
        return FakeProcess()

    monkeypatch.setattr(feishu_bot, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(feishu_bot, "mutate_run", lambda *_args: None)
    monkeypatch.setattr(feishu_bot.subprocess, "Popen", popen)
    config = feishu_bot.load_config(
        environ={
            "SUBMISSION_RUNNER_COMMAND": "/tmp/obsolete-submission-runner.py",
        }
    )
    run = {
        "id": "run-1",
        "app_name": "FallLine",
        "chat_id": PROJECT_CHAT,
        "prompt_path": str(tmp_path / "prompt.md"),
        "requested_skills": ["utm-notion"],
    }

    assert feishu_bot.spawn_submission_runner(config, run) == 4321
    assert captured == {
        "command": [
            sys.executable,
            str(feishu_bot.ROOT / "services" / "submission_runner.py"),
        ],
        "cwd": str(feishu_bot.ROOT),
    }


def test_parse_submission_start_request_accepts_exact_multiline_format() -> None:
    request = feishu_bot.parse_submission_start_request(COMMAND)

    assert request is not None
    assert request.app_name == "FallLine"
    assert request.skills == REQUESTED_SKILLS


def test_parse_submission_start_request_accepts_ordered_noncontiguous_skills() -> None:
    request = feishu_bot.parse_submission_start_request(
        "/提审 FallLine\n执行技能\nutm-notion\nutm-key\nutm-business"
    )

    assert request is not None
    assert request.app_name == "FallLine"
    assert request.skills == ("utm-notion", "utm-key", "utm-business")


def test_parse_submission_start_request_accepts_one_skill() -> None:
    request = feishu_bot.parse_submission_start_request(
        "/提审 FallLine\n执行技能\nutm-p8"
    )

    assert request is not None
    assert request.skills == ("utm-p8",)


@pytest.mark.parametrize("skill", ("utm-21", "utm-22", "utm-23", "utm-24"))
def test_parse_submission_start_request_rejects_feishu_disabled_skills(
    skill: str,
) -> None:
    with pytest.raises(feishu_bot.SubmissionStartError, match="暂不支持通过飞书"):
        feishu_bot.parse_submission_start_request(
            f"/提审 FallLine\n执行技能\n{skill}"
        )


def test_start_rejects_feishu_disabled_skill_when_parser_is_bypassed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        feishu_bot,
        "resolve_submission_application",
        lambda *_args: pytest.fail("禁用技能进入了应用解析"),
    )

    with pytest.raises(feishu_bot.SubmissionStartError, match="暂不支持通过飞书"):
        feishu_bot.start_submission_from_request(
            sample_config(),
            feishu_bot.SubmissionStartRequest("FallLine", ("utm-21",)),
            PROJECT_CHAT,
            "test",
        )


@pytest.mark.parametrize(
    "text",
    (
        "/提审 FallLine\n执行技能",
        "/提审 FallLine\n执行技能\nutm-notion\nutm-notion",
        "/提审 FallLine\n执行技能\nutm-clash-ip\nutm-notion",
        "/提审 FallLine\n执行技能\nunknown-skill",
        "/提审 FallLine 开始\n执行技能\nutm-notion",
        "/提审 FallLine\n请执行技能\nutm-notion",
        "/提审 Bad'App\n执行技能\nutm-notion",
    ),
)
def test_parse_submission_start_request_rejects_malformed_or_unsafe_ranges(
    text: str,
) -> None:
    with pytest.raises(feishu_bot.SubmissionStartError):
        feishu_bot.parse_submission_start_request(text)


def test_non_start_commands_are_not_claimed_by_start_parser() -> None:
    assert feishu_bot.parse_submission_start_request("/提审 可用VM") is None
    assert feishu_bot.parse_submission_start_request("正在提审的应用") is None


def test_start_command_routes_exact_request_to_real_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_start(config: object, request: object, chat_id: str, source: str):
        captured.update(
            config=config,
            request=request,
            chat_id=chat_id,
            source=source,
        )
        return {
            "app_name": "FallLine",
            "requested_skills": list(REQUESTED_SKILLS),
            "status": "runner_started",
        }

    monkeypatch.setattr(feishu_bot, "start_submission_from_request", fake_start)

    reply = feishu_bot.handle_incoming_text(
        sample_config(), COMMAND, PROJECT_CHAT, source="test"
    )

    assert reply == (
        "已启动 FallLine 提审。\n执行技能："
        + "、".join(REQUESTED_SKILLS)
    )
    request = captured["request"]
    assert getattr(request, "app_name") == "FallLine"
    assert getattr(request, "skills") == REQUESTED_SKILLS
    assert captured["chat_id"] == PROJECT_CHAT
    assert captured["source"] == "test"


@pytest.mark.parametrize(
    ("allowed_chat_id", "submission_host_machine", "incoming_chat"),
    (
        ("", LOCAL_HOST, PROJECT_CHAT),
        (PROJECT_CHAT, "", PROJECT_CHAT),
        (PROJECT_CHAT, LOCAL_HOST, "other-chat"),
    ),
)
def test_start_command_fails_closed_outside_exact_project_owner(
    monkeypatch: pytest.MonkeyPatch,
    allowed_chat_id: str,
    submission_host_machine: str,
    incoming_chat: str,
) -> None:
    monkeypatch.setattr(
        feishu_bot,
        "start_submission_from_request",
        lambda *_args, **_kwargs: pytest.fail("unauthorized start reached dispatcher"),
    )
    config = sample_config(
        allowed_chat_id=allowed_chat_id,
        submission_host_machine=submission_host_machine,
    )

    assert feishu_bot.handle_incoming_text(
        config, COMMAND, incoming_chat, source="test"
    ) == ""


def test_start_persists_exact_scope_then_confirms_card_before_spawning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", tmp_path / "runs.json")
    monkeypatch.setattr(feishu_bot, "PROMPTS_DIR", tmp_path / "prompts")
    monkeypatch.setattr(feishu_bot, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(
        feishu_bot,
        "resolve_submission_application",
        lambda app_name, _config: (
            events.append("resolve")
            or {"app_name": app_name, "run_id": BASE_RUN_ID, "vm_name": ""}
        ),
    )
    monkeypatch.setattr(
        feishu_bot,
        "notify_run_start",
        lambda args, _config: events.append("start-card") or 0,
    )

    def fake_spawn(config: object, run: dict[str, Any]) -> int:
        stored = feishu_bot.find_run(run["id"])
        assert stored is not None
        assert stored["requested_skills"] == list(REQUESTED_SKILLS)
        assert stored["status"] == "start_confirmed"
        events.append("spawn")
        return 4321

    monkeypatch.setattr(feishu_bot, "spawn_submission_runner", fake_spawn)

    run = feishu_bot.start_submission_from_request(
        sample_config(),
        feishu_bot.SubmissionStartRequest("FallLine", REQUESTED_SKILLS),
        PROJECT_CHAT,
        "test",
    )

    assert events == ["resolve", "start-card", "spawn"]
    assert run["app_name"] == "FallLine"
    assert run["id"] == BASE_RUN_ID
    assert run["requested_skills"] == list(REQUESTED_SKILLS)
    assert run["chat_id"] == PROJECT_CHAT
    assert run["project_chat_id"] == PROJECT_CHAT
    assert run["submission_data"] == {
        "app_name": "FallLine",
        "host_machine": LOCAL_HOST,
    }
    assert run["status"] == "runner_started"
    assert "runner_pid" not in run
    prompt = Path(run["prompt_path"]).read_text(encoding="utf-8")
    assert "utm-notion -> utm-clash-ip -> utm-login" in prompt
    assert "只执行上述 7 个技能" in prompt
    assert "scripts/utm_notion.py" in prompt
    assert f"--run-id '{BASE_RUN_ID}'" in prompt
    assert "sync-run-vm" in prompt


def test_start_card_failure_never_spawns_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", tmp_path / "runs.json")
    monkeypatch.setattr(feishu_bot, "PROMPTS_DIR", tmp_path / "prompts")
    monkeypatch.setattr(feishu_bot, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(
        feishu_bot,
        "resolve_submission_application",
        lambda app_name, _config: {
            "app_name": app_name,
            "run_id": BASE_RUN_ID,
            "vm_name": "",
        },
    )
    monkeypatch.setattr(feishu_bot, "notify_run_start", lambda *_args: 2)
    monkeypatch.setattr(
        feishu_bot,
        "spawn_submission_runner",
        lambda *_args: pytest.fail("runner spawned without confirmed start card"),
    )

    with pytest.raises(feishu_bot.SubmissionStartError, match="开始卡"):
        feishu_bot.start_submission_from_request(
            sample_config(),
            feishu_bot.SubmissionStartRequest("FallLine", REQUESTED_SKILLS),
            PROJECT_CHAT,
            "test",
        )


def test_active_application_cannot_be_started_twice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", tmp_path / "runs.json")
    monkeypatch.setattr(feishu_bot, "PROMPTS_DIR", tmp_path / "prompts")
    monkeypatch.setattr(feishu_bot, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(
        feishu_bot,
        "resolve_submission_application",
        lambda app_name, _config: {
            "app_name": app_name,
            "run_id": BASE_RUN_ID,
            "vm_name": "",
        },
    )
    monkeypatch.setattr(feishu_bot, "notify_run_start", lambda *_args: 0)
    monkeypatch.setattr(feishu_bot, "spawn_submission_runner", lambda *_args: 4321)
    request = feishu_bot.SubmissionStartRequest("FallLine", REQUESTED_SKILLS)

    feishu_bot.start_submission_from_request(
        sample_config(), request, PROJECT_CHAT, "test"
    )
    with pytest.raises(feishu_bot.SubmissionStartError, match="正在提审"):
        feishu_bot.start_submission_from_request(
            sample_config(), request, PROJECT_CHAT, "test"
        )


def test_skill_lifecycle_rejects_skills_outside_requested_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = {
        "id": "run-1",
        "app_name": "FallLine",
        "chat_id": PROJECT_CHAT,
        "project_chat_id": PROJECT_CHAT,
        "submission_data": {"host_machine": LOCAL_HOST, "app_name": "FallLine"},
        "requested_skills": ["utm-notion", "utm-clash-ip"],
        "lifecycle": {
            "started_at": "2026-08-26T08:00:00+00:00",
            "start_message_id": "message-1",
        },
        "skill_attempts": [],
    }
    path = tmp_path / "runs.json"
    feishu_bot.write_json(path, {"runs": [run]})
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", path)
    config = sample_config()

    args = SimpleNamespace(
        run_id="run-1",
        chat_id=PROJECT_CHAT,
        skill="utm-login",
        stage="entry",
    )
    assert feishu_bot.record_skill_lifecycle(args, config, "started") == 2
    assert feishu_bot.find_run("run-1")["skill_attempts"] == []


def test_skill_lifecycle_rejects_out_of_order_skill_inside_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = {
        "id": "run-1",
        "app_name": "FallLine",
        "chat_id": PROJECT_CHAT,
        "project_chat_id": PROJECT_CHAT,
        "submission_data": {"host_machine": LOCAL_HOST, "app_name": "FallLine"},
        "requested_skills": ["utm-notion", "utm-clash-ip"],
        "lifecycle": {
            "started_at": "2026-08-26T08:00:00+00:00",
            "start_message_uuid": "generation-1",
            "start_message_id": "message-1",
        },
        "skill_attempts": [],
    }
    path = tmp_path / "runs.json"
    feishu_bot.write_json(path, {"runs": [run]})
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", path)

    args = SimpleNamespace(
        run_id="run-1",
        chat_id=PROJECT_CHAT,
        skill="utm-clash-ip",
        stage="entry",
    )
    assert feishu_bot.record_skill_lifecycle(
        args, sample_config(), "started"
    ) == 2


def test_skill_lifecycle_accepts_ordered_noncontiguous_requested_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = {
        "id": "run-1",
        "app_name": "FallLine",
        "chat_id": PROJECT_CHAT,
        "project_chat_id": PROJECT_CHAT,
        "submission_data": {"host_machine": LOCAL_HOST, "app_name": "FallLine"},
        "requested_skills": ["utm-notion", "utm-key", "utm-business"],
        "lifecycle": {
            "started_at": "2026-08-26T08:00:00+00:00",
            "start_message_uuid": "generation-1",
            "start_message_id": "message-1",
        },
        "skill_attempts": [],
    }
    path = tmp_path / "runs.json"
    feishu_bot.write_json(path, {"runs": [run]})
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", path)
    config = sample_config()

    notion = SimpleNamespace(
        run_id="run-1",
        chat_id=PROJECT_CHAT,
        skill="utm-notion",
        stage="entry",
    )
    key = SimpleNamespace(
        run_id="run-1",
        chat_id=PROJECT_CHAT,
        skill="utm-key",
        stage="entry",
    )

    assert feishu_bot.record_skill_lifecycle(notion, config, "started") == 0
    assert feishu_bot.record_skill_lifecycle(notion, config, "succeeded") == 0
    assert feishu_bot.record_skill_lifecycle(key, config, "started") == 0


def test_success_finish_requires_every_requested_skill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = {
        "id": "run-1",
        "app_name": "FallLine",
        "chat_id": PROJECT_CHAT,
        "project_chat_id": PROJECT_CHAT,
        "submission_data": {"host_machine": LOCAL_HOST, "app_name": "FallLine"},
        "requested_skills": ["utm-notion", "utm-clash-ip"],
        "lifecycle": {
            "started_at": "2026-08-26T08:00:00+00:00",
            "start_message_uuid": "generation-1",
            "start_message_id": "message-1",
        },
        "skill_attempts": [
            {
                "skill": "utm-notion",
                "status": "succeeded",
                "started_at": "2026-08-26T08:01:00+00:00",
                "finished_at": "2026-08-26T08:02:00+00:00",
            }
        ],
    }
    path = tmp_path / "runs.json"
    feishu_bot.write_json(path, {"runs": [run]})
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", path)
    monkeypatch.setattr(
        feishu_bot.FeishuClient,
        "send_card",
        lambda *_args, **_kwargs: pytest.fail(
            "incomplete requested scope sent a success card"
        ),
    )

    args = SimpleNamespace(
        run_id="run-1", chat_id=PROJECT_CHAT, outcome="success"
    )
    assert feishu_bot.notify_run_finish(args, sample_config()) == 2
    assert not feishu_bot.find_run("run-1")["lifecycle"].get("finished_at")


def test_service_syncs_vm_from_base_after_utm_notion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "runs.json"
    feishu_bot.write_json(
        path,
        {
            "runs": [
                    {
                        "id": "run-1",
                        "app_name": "FallLine",
                        "vm_name": "",
                        "chat_id": PROJECT_CHAT,
                        "project_chat_id": PROJECT_CHAT,
                        "submission_data": {
                        "app_name": "FallLine",
                        "host_machine": LOCAL_HOST,
                    },
                }
            ]
        },
    )
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", path)
    monkeypatch.setattr(
        feishu_bot,
        "resolve_submission_application",
        lambda app_name, _config: {
            "app_name": app_name,
            "run_id": "run-1",
            "vm_name": "abcd",
        },
    )

    updated = feishu_bot.sync_submission_vm_from_base(
        "run-1", sample_config(), PROJECT_CHAT
    )

    assert updated["vm_name"] == "abcd"
    assert feishu_bot.find_run("run-1")["vm_name"] == "abcd"


def test_service_vm_sync_rejects_application_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "runs.json"
    feishu_bot.write_json(
        path,
        {
            "runs": [
                    {
                        "id": "run-1",
                        "app_name": "FallLine",
                        "vm_name": "",
                        "chat_id": PROJECT_CHAT,
                        "project_chat_id": PROJECT_CHAT,
                        "submission_data": {
                        "app_name": "FallLine",
                        "host_machine": LOCAL_HOST,
                    },
                }
            ]
        },
    )
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", path)
    monkeypatch.setattr(
        feishu_bot,
        "resolve_submission_application",
        lambda _app_name, _config: {
            "app_name": "OtherApp",
            "run_id": "run-1",
            "vm_name": "abcd",
        },
    )

    with pytest.raises(feishu_bot.SubmissionStartError, match="应用身份"):
        feishu_bot.sync_submission_vm_from_base(
            "run-1", sample_config(), PROJECT_CHAT
        )


def test_sync_run_vm_cli_reports_only_verified_vm_marker(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        feishu_bot,
        "sync_submission_vm_from_base",
        lambda run_id, _config, chat_id: {
            "id": run_id,
            "chat_id": chat_id,
            "vm_name": "abcd",
        },
    )
    args = SimpleNamespace(run_id="run-1", chat_id=PROJECT_CHAT)

    assert feishu_bot.sync_submission_vm_cli(args, sample_config()) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "SUBMISSION_VM=abcd"
    assert captured.err == ""


def test_main_dispatches_sync_run_vm_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}
    config = sample_config()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "feishu_bot.py",
            "sync-run-vm",
            "--run-id",
            BASE_RUN_ID,
            "--chat-id",
            PROJECT_CHAT,
        ],
    )
    monkeypatch.setattr(feishu_bot, "harden_runtime_metadata", lambda: None)
    monkeypatch.setattr(feishu_bot, "load_config", lambda: config)

    def fake_sync(args: SimpleNamespace, _config: object) -> int:
        captured["run_id"] = args.run_id
        captured["chat_id"] = args.chat_id
        return 0

    monkeypatch.setattr(feishu_bot, "sync_submission_vm_cli", fake_sync)

    assert feishu_bot.main() == 0
    assert captured == {"run_id": BASE_RUN_ID, "chat_id": PROJECT_CHAT}


def test_application_resolution_returns_base_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import utm_notion

    runtime_config = SimpleNamespace(
        host_title=LOCAL_HOST,
        feishu_app_id=FIXTURE_APP_IDENTIFIER,
        feishu_app_secret=FIXTURE_APP_CREDENTIAL,
        configured_source=("direct", "base-token", "table-id", "view-id"),
    )
    monkeypatch.setattr(utm_notion, "load_runtime_config", lambda: runtime_config)
    monkeypatch.setattr(feishu_bot, "get_tenant_access_token", lambda *_args: "token")
    monkeypatch.setattr(
        utm_notion,
        "resolve_utm_notion_source",
        lambda *_args: ("base-token", "table-id", "view-id"),
    )
    monkeypatch.setattr(
        utm_notion,
        "build_registration_fields",
        lambda _fields, **_kwargs: ({}, {}),
    )

    class FakeClient:
        def __init__(self, *_args: object) -> None:
            pass

        def find_exact_record(self, *, app_name: str) -> dict[str, object]:
            assert app_name == "FallLine"
            return {
                "fields": {
                    "应用名": "FallLine",
                    "Run ID": BASE_RUN_ID,
                    "虚拟机": "",
                }
            }

    monkeypatch.setattr(utm_notion, "FeishuBitableClient", FakeClient)

    assert feishu_bot.resolve_submission_application(
        "FallLine", sample_config()
    ) == {
        "app_name": "FallLine",
        "run_id": BASE_RUN_ID,
        "vm_name": "",
    }
