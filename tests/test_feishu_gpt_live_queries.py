from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from services import feishu_bot


PROJECT_CHAT = "project-chat"
OTHER_CHAT = "other-chat"
LOCAL_HOST = "host-a"


def sample_config(**overrides: Any) -> SimpleNamespace:
    values = {
        "allowed_chat_id": PROJECT_CHAT,
        "daily_report_chat_id": "",
        "submission_host_machine": LOCAL_HOST,
        "assistant_enabled": True,
        "assistant_require_mention": True,
        "assistant_provider": "openai",
        "assistant_max_output_tokens": 800,
        "openai_api_key": "test-openai-key",
        "openai_model": "must-not-control-live-query-model",
        "codex_command": "codex",
        "codex_model": "must-not-control-live-query-model",
        "codex_timeout_seconds": 30,
        "send_timeout_seconds": 20,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    "text",
    (
        "查看可用虚拟机",
        "可用的虚拟机",
        "目前可用虚拟机有多少",
        "/提审 可用VM",
    ),
)
def test_all_vm_query_phrases_are_exact_vm_intents_after_mention_stripping(
    text: str,
) -> None:
    assert feishu_bot.project_query_intent(text) == "vms"
    assert (
        feishu_bot.project_query_intent(
            f'<at user_id="ou_bot">提审机器人</at> {text}'
        )
        == "vms"
    )


def test_authorized_vm_query_reads_a_fresh_snapshot_for_each_gpt_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory_reads: list[Path] = []
    snapshots = iter((["abcd"], ["wxyz", "zyxw"]))
    assistant_calls: list[tuple[str, str, str]] = []
    assistant_starts: list[str] = []

    def list_vms(database: Path) -> list[str]:
        inventory_reads.append(database)
        return list(next(snapshots))

    def answer(
        config: SimpleNamespace,
        chat_id: str,
        user_text: str,
        *,
        live_context: str,
    ) -> str:
        assert config.assistant_provider == "openai"
        assistant_calls.append((chat_id, user_text, live_context))
        return f"GPT live answer {len(assistant_calls)}"

    monkeypatch.setattr(feishu_bot, "list_available_vm_names", list_vms)
    monkeypatch.setattr(feishu_bot, "ask_codex_assistant", answer)
    monkeypatch.setattr(
        feishu_bot,
        "ask_assistant",
        lambda *_args, **_kwargs: pytest.fail(
            "live project queries must bypass the generic provider router"
        ),
    )

    config = sample_config(openai_api_key="")
    first = feishu_bot.handle_incoming_text(
        config,
        "/提审 可用VM",
        PROJECT_CHAT,
        source="test",
        on_assistant_start=lambda: assistant_starts.append("started"),
    )
    second = feishu_bot.handle_incoming_text(
        config,
        "/提审 可用VM",
        PROJECT_CHAT,
        source="test",
        on_assistant_start=lambda: assistant_starts.append("started"),
    )

    assert (first, second) == ("GPT live answer 1", "GPT live answer 2")
    assert assistant_starts == ["started", "started"]
    assert len(inventory_reads) == 2
    assert len(assistant_calls) == 2
    first_context = assistant_calls[0][2]
    second_context = assistant_calls[1][2]
    assert "abcd" in first_context
    assert "wxyz" not in first_context
    assert "wxyz" in second_context
    assert "zyxw" in second_context
    assert "abcd" not in second_context
    assert first_context != second_context


def test_authorized_active_application_query_is_answered_from_live_gpt_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs = [
        {
            "id": "sensitive-run-id",
            "chat_id": PROJECT_CHAT,
            "project_chat_id": PROJECT_CHAT,
            "app_name": "SampleApp",
            "prompt_path": "/sensitive/runtime/prompt.md",
            "submission_data": {"host_machine": LOCAL_HOST},
            "current_skill": "utm-image",
            "lifecycle": {"started_at": "2026-08-26T00:00:00+00:00"},
        }
    ]
    observed_contexts: list[str] = []

    def answer(
        _config: SimpleNamespace,
        _chat_id: str,
        _user_text: str,
        *,
        live_context: str,
    ) -> str:
        observed_contexts.append(live_context)
        return "GPT active-app answer"

    monkeypatch.setattr(feishu_bot, "read_runs_strict", lambda: runs)
    monkeypatch.setattr(feishu_bot, "ask_codex_assistant", answer)
    monkeypatch.setattr(
        feishu_bot,
        "ask_assistant",
        lambda *_args, **_kwargs: pytest.fail(
            "live application queries must bypass the generic provider router"
        ),
    )
    monkeypatch.setattr(
        feishu_bot,
        "list_available_vm_names",
        lambda _database: pytest.fail("application-only query must not read inventory"),
    )

    reply = feishu_bot.handle_incoming_text(
        sample_config(), "/提审 应用列表", PROJECT_CHAT, source="test"
    )

    assert reply == "GPT active-app answer"
    assert len(observed_contexts) == 1
    context = observed_contexts[0]
    assert "SampleApp" in context
    assert "utm-image" in context
    assert "sensitive-run-id" not in context
    assert "/sensitive/runtime/prompt.md" not in context
    assert PROJECT_CHAT not in context


def test_authorized_resource_query_refreshes_both_snapshots_and_forces_codex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_snapshots = iter(
        (
            [
                {
                    "chat_id": PROJECT_CHAT,
                    "project_chat_id": PROJECT_CHAT,
                    "app_name": "FirstApp",
                    "submission_data": {"host_machine": LOCAL_HOST},
                    "current_skill": "utm-login",
                    "lifecycle": {"started_at": "2026-08-26T00:00:00+00:00"},
                }
            ],
            [
                {
                    "chat_id": PROJECT_CHAT,
                    "project_chat_id": PROJECT_CHAT,
                    "app_name": "SecondApp",
                    "submission_data": {"host_machine": LOCAL_HOST},
                    "current_skill": "utm-image",
                    "lifecycle": {"started_at": "2026-08-26T01:00:00+00:00"},
                }
            ],
        )
    )
    vm_snapshots = iter((["abcd"], ["wxyz", "zyxw"]))
    contexts: list[str] = []

    monkeypatch.setattr(feishu_bot, "read_runs_strict", lambda: next(run_snapshots))
    monkeypatch.setattr(
        feishu_bot,
        "list_available_vm_names",
        lambda _database: list(next(vm_snapshots)),
    )
    monkeypatch.setattr(
        feishu_bot,
        "ask_codex_assistant",
        lambda _config, _chat_id, _text, *, live_context: (
            contexts.append(live_context) or "Codex resource answer"
        ),
    )
    monkeypatch.setattr(
        feishu_bot,
        "ask_assistant",
        lambda *_args, **_kwargs: pytest.fail(
            "live resource queries must bypass the generic provider router"
        ),
    )

    config = sample_config(assistant_provider="openai", openai_api_key="")
    assert (
        feishu_bot.handle_incoming_text(
            config, "/提审 资源", PROJECT_CHAT, source="test"
        )
        == "Codex resource answer"
    )
    assert (
        feishu_bot.handle_incoming_text(
            config, "/提审 资源", PROJECT_CHAT, source="test"
        )
        == "Codex resource answer"
    )

    assert len(contexts) == 2
    assert "FirstApp" in contexts[0]
    assert "abcd" in contexts[0]
    assert "SecondApp" not in contexts[0]
    assert "wxyz" not in contexts[0]
    assert "SecondApp" in contexts[1]
    assert "wxyz" in contexts[1]
    assert "zyxw" in contexts[1]
    assert "FirstApp" not in contexts[1]
    assert "abcd" not in contexts[1]


@pytest.mark.parametrize(
    "query",
    (
        "查看可用虚拟机",
        "可用的虚拟机",
        "/提审 可用VM",
        "/提审 应用列表",
    ),
)
def test_unauthorized_project_queries_never_read_live_state_or_call_gpt(
    monkeypatch: pytest.MonkeyPatch,
    query: str,
) -> None:
    monkeypatch.setattr(
        feishu_bot,
        "list_available_vm_names",
        lambda _database: pytest.fail("unauthorized query read VM inventory"),
    )
    monkeypatch.setattr(
        feishu_bot,
        "read_runs_strict",
        lambda: pytest.fail("unauthorized query read run registry"),
    )
    monkeypatch.setattr(
        feishu_bot,
        "ask_assistant",
        lambda *_args, **_kwargs: pytest.fail("unauthorized query called GPT"),
    )

    assert (
        feishu_bot.handle_incoming_text(
            sample_config(), f"@Bot {query}", OTHER_CHAT, source="test"
        )
        == ""
    )


@pytest.mark.parametrize(
    ("provider", "target_name"),
    (("openai", "ask_openai_assistant"), ("codex", "ask_codex_assistant")),
)
def test_assistant_router_forwards_live_context_to_the_selected_provider(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    target_name: str,
) -> None:
    calls: list[tuple[str, str, str]] = []

    def provider_answer(
        _config: SimpleNamespace,
        chat_id: str,
        user_text: str,
        *,
        live_context: str,
    ) -> str:
        calls.append((chat_id, user_text, live_context))
        return "provider answer"

    monkeypatch.setattr(feishu_bot, target_name, provider_answer)

    reply = feishu_bot.ask_assistant(
        sample_config(assistant_provider=provider),
        PROJECT_CHAT,
        "查看可用虚拟机",
        live_context="可用虚拟机（1）：abcd",
    )

    assert reply == "provider answer"
    assert calls == [
        (PROJECT_CHAT, "查看可用虚拟机", "可用虚拟机（1）：abcd")
    ]


def test_openai_live_query_model_is_pinned_to_gpt_5_6(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_bodies: list[dict[str, Any]] = []

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"output_text":"GPT answer"}'

    def urlopen(req: Any, *, timeout: int) -> FakeResponse:
        assert timeout == 20
        captured_bodies.append(json.loads(req.data.decode("utf-8")))
        return FakeResponse()

    monkeypatch.setattr(feishu_bot.request, "urlopen", urlopen)
    monkeypatch.setattr(feishu_bot, "read_conversation", lambda _chat_id: [])
    monkeypatch.setattr(feishu_bot, "append_conversation", lambda *_args: None)

    live_context = "可用虚拟机（1）：abcd"
    reply = feishu_bot.ask_openai_assistant(
        sample_config(openai_model="not-gpt-5.6"),
        PROJECT_CHAT,
        "查看可用虚拟机",
        live_context=live_context,
    )

    assert reply == "GPT answer"
    assert len(captured_bodies) == 1
    body = captured_bodies[0]
    assert body["model"] == "gpt-5.6"
    assert live_context in json.dumps(body, ensure_ascii=False)


def test_codex_live_query_uses_gpt_5_6_sol_and_receives_live_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []

    def run(cmd: list[str], **_kwargs: Any) -> SimpleNamespace:
        commands.append(cmd)
        output_path = Path(cmd[cmd.index("-o") + 1])
        output_path.write_text("Codex answer", encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(feishu_bot, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(feishu_bot.subprocess, "run", run)
    monkeypatch.setattr(feishu_bot, "append_conversation", lambda *_args: None)

    live_context = "正在提审的应用（1）：\n- SampleApp｜utm-image｜1分 2秒"
    reply = feishu_bot.ask_codex_assistant(
        sample_config(
            assistant_provider="codex",
            codex_model="not-gpt-5.6-sol",
        ),
        PROJECT_CHAT,
        "正在提审的应用",
        live_context=live_context,
    )

    assert reply == "Codex answer"
    assert len(commands) == 1
    command = commands[0]
    assert command[command.index("-m") + 1] == "gpt-5.6-sol"
    assert 'model_reasoning_effort="high"' in command
    assert 'model_reasoning_effort="low"' not in command
    assert "回答前先只读检查当前项目" in command[-1]
    assert "不得读取根 .env、runtime/" in command[-1]
    assert live_context in command[-1]


def test_compact_start_candidate_is_never_delegated_to_a_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        feishu_bot,
        "ask_assistant",
        lambda *_args, **_kwargs: pytest.fail(
            "compact-start syntax must be handled deterministically"
        ),
    )

    malformed_compact_start = (
        '<at user_id="ou_bot">提审机器人</at> /提审 SampleApp\n'
        "执行技能\n"
        "not-a-canonical-skill"
    )
    reply = feishu_bot.handle_incoming_text(
        sample_config(), malformed_compact_start, PROJECT_CHAT, source="test"
    )

    assert isinstance(reply, str)
