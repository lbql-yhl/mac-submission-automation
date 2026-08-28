from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from services import feishu_bot


PROJECT_CHAT = "project-chat"
OTHER_CHAT = "other-chat"
DAILY_CHAT = "daily-chat"
LOCAL_HOST = "host-a"
APP_NAME = "FallLine"
VM_NAME = "abcd"
RUN_ID = "compact-run-1"
FEISHU_MENTION = '<at user_id="ou_bot">GaleOpsBrain</at>'
REQUESTED_SKILLS = (
    "utm-notion",
    "utm-clash-ip",
    "utm-login",
    "utm-edit",
    "utm-key",
    "utm-apps",
    "utm-business",
)


def compact_request(
    skills: tuple[str, ...] = REQUESTED_SKILLS,
    *,
    app_name: str = APP_NAME,
    label: str = "执行技能",
    mention: str = FEISHU_MENTION,
    extra_lines: tuple[str, ...] = (),
) -> str:
    return "\n".join(
        (
            f"{mention} /提审 {app_name}".rstrip(),
            label,
            *skills,
            *extra_lines,
        )
    )


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


def resolved_run(**overrides: Any) -> dict[str, Any]:
    run: dict[str, Any] = {
        "id": RUN_ID,
        "app_name": APP_NAME,
        "vm_name": VM_NAME,
        "chat_id": PROJECT_CHAT,
        "project_chat_id": PROJECT_CHAT,
        "raw_text": compact_request(),
        "submission_data": {
            "app_name": APP_NAME,
            "host_machine": LOCAL_HOST,
        },
        "requested_skills": REQUESTED_SKILLS,
        "status": "compact_start_claimed",
        "events": [],
    }
    run.update(overrides)
    return run


def lifecycle_args(skill: str) -> SimpleNamespace:
    return SimpleNamespace(
        run_id=RUN_ID,
        chat_id="",
        skill=skill,
        stage="contract test",
        outcome="",
    )


def install_started_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    path = tmp_path / "feishu-runs.json"
    run = resolved_run(
        status="running",
        lifecycle={
            "started_at": "2026-08-26T08:00:00+00:00",
            "start_message_uuid": "start-uuid",
            "start_message_id": "start-message",
        },
    )
    feishu_bot.write_json(path, {"runs": [run]})
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", path)
    return path


def reject_assistant(*_args: Any, **_kwargs: Any) -> str:
    pytest.fail("compact submission commands must never fall through to GPT")


def assert_not_started(reply: str) -> None:
    assert "准备开始" not in reply
    assert "已启动" not in reply


@pytest.mark.parametrize(
    "mention",
    (
        FEISHU_MENTION,
        "@_user_1",
    ),
)
def test_parse_compact_start_after_feishu_mention_returns_exact_request(
    mention: str,
) -> None:
    request = feishu_bot.parse_submission_start_request(
        compact_request(mention=mention)
    )

    assert request == {
        "app_name": APP_NAME,
        "requested_skills": REQUESTED_SKILLS,
    }


@pytest.mark.parametrize(
    ("case", "text"),
    (
        ("empty app", compact_request(("utm-notion",), app_name="")),
        ("empty skills", compact_request(())),
        (
            "unknown skill",
            compact_request(("utm-notion", "utm-unknown")),
        ),
        (
            "duplicate skill",
            compact_request(("utm-notion", "utm-notion")),
        ),
        (
            "out of order",
            compact_request(("utm-clash-ip", "utm-notion")),
        ),
        (
            "non-contiguous",
            compact_request(("utm-notion", "utm-login")),
        ),
        (
            "inexact heading",
            compact_request(("utm-notion",), label="执行技能："),
        ),
        (
            "extra body",
            compact_request(extra_lines=("请立即执行",)),
        ),
    ),
    ids=lambda value: value if isinstance(value, str) and "\n" not in value else None,
)
def test_parse_compact_start_rejects_invalid_or_ambiguous_requests(
    case: str,
    text: str,
) -> None:
    del case

    with pytest.raises(ValueError):
        feishu_bot.parse_submission_start_request(text)


def test_parse_compact_start_ignores_non_start_conversation() -> None:
    assert feishu_bot.parse_submission_start_request(
        f"{FEISHU_MENTION} 查看当前可用虚拟机"
    ) is None


def test_authorized_compact_start_passes_exact_request_and_resolved_run_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = resolved_run()
    resolver_calls: list[tuple[Any, dict[str, Any], str, str]] = []
    dispatcher_calls: list[tuple[Any, dict[str, Any]]] = []

    def resolve(
        config: Any,
        request: dict[str, Any],
        chat_id: str,
        source: str,
    ) -> dict[str, Any]:
        resolver_calls.append((config, request, chat_id, source))
        return run

    def dispatch(config: Any, resolved: dict[str, Any]) -> dict[str, Any]:
        dispatcher_calls.append((config, resolved))
        return resolved

    monkeypatch.setattr(
        feishu_bot, "resolve_compact_submission_start", resolve, raising=False
    )
    monkeypatch.setattr(
        feishu_bot, "dispatch_compact_submission_start", dispatch, raising=False
    )
    monkeypatch.setattr(feishu_bot, "ask_assistant", reject_assistant)
    config = sample_config()

    reply = feishu_bot.handle_incoming_text(
        config,
        compact_request(),
        PROJECT_CHAT,
        source="test",
    )

    assert len(resolver_calls) == 1
    assert resolver_calls[0] == (
        config,
        {
            "app_name": APP_NAME,
            "requested_skills": REQUESTED_SKILLS,
        },
        PROJECT_CHAT,
        "test",
    )
    assert dispatcher_calls == [(config, run)]
    assert dispatcher_calls[0][1] is run
    assert dispatcher_calls[0][1]["requested_skills"] == REQUESTED_SKILLS
    assert APP_NAME in reply
    assert "开始" in reply or "启动" in reply


@pytest.mark.parametrize(
    ("config_overrides", "incoming_chat"),
    (
        ({}, OTHER_CHAT),
        ({"allowed_chat_id": ""}, PROJECT_CHAT),
        ({"submission_host_machine": ""}, PROJECT_CHAT),
    ),
    ids=("wrong-chat", "empty-project-chat-config", "empty-host"),
)
def test_compact_start_boundary_rejections_have_zero_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    config_overrides: dict[str, str],
    incoming_chat: str,
) -> None:
    calls: list[str] = []

    def unexpected_resolver(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls.append("resolve")
        pytest.fail("rejected compact start must not resolve a run")

    def unexpected_dispatcher(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls.append("dispatch")
        pytest.fail("rejected compact start must not dispatch")

    monkeypatch.setattr(
        feishu_bot,
        "resolve_compact_submission_start",
        unexpected_resolver,
        raising=False,
    )
    monkeypatch.setattr(
        feishu_bot,
        "dispatch_compact_submission_start",
        unexpected_dispatcher,
        raising=False,
    )
    monkeypatch.setattr(feishu_bot, "ask_assistant", reject_assistant)
    runs_file = tmp_path / "feishu-runs.json"
    prompts_dir = tmp_path / "prompts"
    sessions_dir = tmp_path / "codex-app-sessions"
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", runs_file)
    monkeypatch.setattr(feishu_bot, "PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr(feishu_bot, "CODEX_APP_SESSIONS_DIR", sessions_dir)

    reply = feishu_bot.handle_incoming_text(
        sample_config(**config_overrides),
        compact_request(),
        incoming_chat,
        source="test",
    )

    assert calls == []
    assert_not_started(reply)
    assert not runs_file.exists()
    assert not prompts_dir.exists()
    assert not sessions_dir.exists()


def test_invalid_compact_start_never_reaches_resolver_dispatcher_or_gpt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def unexpected_resolver(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls.append("resolve")
        return resolved_run()

    def unexpected_dispatcher(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls.append("dispatch")
        return resolved_run()

    monkeypatch.setattr(
        feishu_bot,
        "resolve_compact_submission_start",
        unexpected_resolver,
        raising=False,
    )
    monkeypatch.setattr(
        feishu_bot,
        "dispatch_compact_submission_start",
        unexpected_dispatcher,
        raising=False,
    )
    monkeypatch.setattr(feishu_bot, "ask_assistant", reject_assistant)

    reply = feishu_bot.handle_incoming_text(
        sample_config(),
        compact_request(("utm-notion", "utm-login")),
        PROJECT_CHAT,
        source="test",
    )

    assert calls == []
    assert_not_started(reply)


def test_dispatch_failure_is_not_reported_as_started_and_never_reaches_gpt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = resolved_run()
    calls: list[str] = []

    def resolve(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls.append("resolve")
        return run

    def dispatch(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        calls.append("dispatch")
        raise RuntimeError("redacted dispatch failure")

    monkeypatch.setattr(
        feishu_bot, "resolve_compact_submission_start", resolve, raising=False
    )
    monkeypatch.setattr(
        feishu_bot, "dispatch_compact_submission_start", dispatch, raising=False
    )
    monkeypatch.setattr(feishu_bot, "ask_assistant", reject_assistant)

    reply = feishu_bot.handle_incoming_text(
        sample_config(), compact_request(), PROJECT_CHAT, source="test"
    )

    assert calls == ["resolve", "dispatch"]
    assert_not_started(reply)


def test_same_active_application_cannot_dispatch_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = resolved_run(status="running")
    resolver_count = 0
    dispatcher_count = 0

    def resolve(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        nonlocal resolver_count
        resolver_count += 1
        if resolver_count > 1:
            raise RuntimeError("application already has an active compact start")
        return run

    def dispatch(_config: Any, resolved: dict[str, Any]) -> dict[str, Any]:
        nonlocal dispatcher_count
        assert resolved is run
        dispatcher_count += 1
        return resolved

    monkeypatch.setattr(
        feishu_bot, "resolve_compact_submission_start", resolve, raising=False
    )
    monkeypatch.setattr(
        feishu_bot, "dispatch_compact_submission_start", dispatch, raising=False
    )
    monkeypatch.setattr(feishu_bot, "ask_assistant", reject_assistant)
    config = sample_config()

    first = feishu_bot.handle_incoming_text(
        config, compact_request(), PROJECT_CHAT, source="test"
    )
    second = feishu_bot.handle_incoming_text(
        config, compact_request(), PROJECT_CHAT, source="test"
    )

    assert resolver_count == 2
    assert dispatcher_count == 1
    assert APP_NAME in first
    assert "开始" in first or "启动" in first
    assert_not_started(second)


def test_codex_prompt_authorizes_only_requested_skills_and_exact_app_vm() -> None:
    prompt = feishu_bot.build_codex_prompt(resolved_run())
    authorization_lines = [
        line.strip() for line in prompt.splitlines() if "唯一授权技能" in line
    ]

    assert f"应用名：{APP_NAME}" in prompt
    assert f"虚拟机名称：{VM_NAME}" in prompt
    assert "不得按“最新”重选" in prompt
    assert len(authorization_lines) == 1
    authorization = authorization_lines[0]
    assert " -> ".join(REQUESTED_SKILLS) in authorization
    assert all(
        skill not in authorization
        for skill in feishu_bot.SUBMISSION_SKILL_ORDER
        if skill not in REQUESTED_SKILLS
    )
    assert "请求范围之外" in prompt
    assert "固定技能顺序（16 个）" not in prompt
    assert "本提示是完整提审请求时执行全部四段" not in prompt


def test_lifecycle_rejects_skill_outside_requested_subset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_started_run(monkeypatch, tmp_path)

    result = feishu_bot.record_skill_lifecycle(
        lifecycle_args("utm-vm-clone"), sample_config(), "started"
    )

    assert result == 2
    stored = feishu_bot.find_run(RUN_ID)
    assert stored is not None
    assert not stored.get("skill_attempts")


def test_lifecycle_rejects_skipped_or_out_of_order_skill_starts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    install_started_run(monkeypatch, tmp_path)

    assert (
        feishu_bot.record_skill_lifecycle(
            lifecycle_args("utm-clash-ip"), sample_config(), "started"
        )
        == 2
    )
    assert (
        feishu_bot.record_skill_lifecycle(
            lifecycle_args("utm-notion"), sample_config(), "started"
        )
        == 0
    )
    assert (
        feishu_bot.record_skill_lifecycle(
            lifecycle_args("utm-notion"), sample_config(), "succeeded"
        )
        == 0
    )
    assert (
        feishu_bot.record_skill_lifecycle(
            lifecycle_args("utm-login"), sample_config(), "started"
        )
        == 2
    )
    assert (
        feishu_bot.record_skill_lifecycle(
            lifecycle_args("utm-clash-ip"), sample_config(), "started"
        )
        == 0
    )
