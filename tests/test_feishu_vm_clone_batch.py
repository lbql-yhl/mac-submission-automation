from __future__ import annotations

from dataclasses import replace
import io
import inspect
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from services import feishu_bot


PROJECT_CHAT = "project-chat"
LOCAL_HOST = "host-a"


def sample_config(**overrides: Any) -> feishu_bot.Config:
    config = feishu_bot.load_config(
        environ={
            "FEISHU_ALLOWED_CHAT_ID": PROJECT_CHAT,
            "SUBMISSION_HOST_MACHINE": LOCAL_HOST,
            "FEISHU_ASSISTANT_ENABLED": "1",
        }
    )
    return replace(config, **overrides)


@pytest.mark.parametrize(
    ("text", "count"),
    (
        ('<at user_id="ou_bot">提审机器人</at> /创建虚拟机 5台', 5),
        ("/创建虚拟机 1台", 1),
        ("/创建虚拟机 10台", 10),
    ),
)
def test_parse_vm_clone_batch_accepts_exact_command(text: str, count: int) -> None:
    request = feishu_bot.parse_vm_clone_batch_request(text)

    assert request is not None
    assert request.count == count


@pytest.mark.parametrize(
    "text",
    (
        "/创建虚拟机 0台",
        "/创建虚拟机 -1台",
        "/创建虚拟机 01台",
        "/创建虚拟机 1.5台",
        "/创建虚拟机 ５台",
        "/创建虚拟机 11台",
        "/创建虚拟机 5",
        "/创建虚拟机 5台 现在",
        "/创建虚拟机 5台\n执行技能",
    ),
)
def test_parse_vm_clone_batch_rejects_unsafe_counts_or_extra_text(text: str) -> None:
    with pytest.raises(feishu_bot.VmCloneBatchError):
        feishu_bot.parse_vm_clone_batch_request(text)


def test_parse_vm_clone_batch_does_not_claim_other_messages() -> None:
    assert feishu_bot.parse_vm_clone_batch_request("/提审 FallLine") is None
    assert feishu_bot.parse_vm_clone_batch_request("创建五台虚拟机") is None


def test_help_lists_vm_clone_batch_command_and_serial_limit() -> None:
    assert "/创建虚拟机 <数量>台" in feishu_bot.HELP_TEXT
    assert "单次最多 10 台，逐台串行创建" in feishu_bot.HELP_TEXT


def test_vm_clone_batch_command_routes_before_gpt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def start(config: object, request: object, chat_id: str, source: str):
        captured.update(
            config=config,
            request=request,
            chat_id=chat_id,
            source=source,
        )
        return {"requested_count": 5}

    monkeypatch.setattr(
        feishu_bot, "start_vm_clone_batch_from_request", start, raising=False
    )
    monkeypatch.setattr(
        feishu_bot,
        "ask_assistant",
        lambda *_args, **_kwargs: pytest.fail("batch command reached GPT"),
    )

    reply = feishu_bot.handle_incoming_text(
        sample_config(),
        '<at user_id="ou_bot">提审机器人</at> /创建虚拟机 5台',
        PROJECT_CHAT,
        source="test",
    )

    assert reply == "已开始批量创建 5 台虚拟机。完成后会发送结果卡片。"
    assert getattr(captured["request"], "count") == 5
    assert captured["chat_id"] == PROJECT_CHAT
    assert captured["source"] == "test"


@pytest.mark.parametrize(
    ("config", "chat_id"),
    (
        (sample_config(allowed_chat_id=""), PROJECT_CHAT),
        (sample_config(submission_host_machine=""), PROJECT_CHAT),
        (sample_config(), "other-chat"),
        (sample_config(daily_report_chat_id=PROJECT_CHAT), PROJECT_CHAT),
    ),
)
def test_vm_clone_batch_command_fails_closed_outside_project_owner(
    config: feishu_bot.Config,
    chat_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        feishu_bot,
        "start_vm_clone_batch_from_request",
        lambda *_args, **_kwargs: pytest.fail("unauthorized batch was dispatched"),
        raising=False,
    )

    assert (
        feishu_bot.handle_incoming_text(
            config, "/创建虚拟机 5台", chat_id, source="test"
        )
        == ""
    )


def test_invalid_vm_clone_batch_never_reaches_gpt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        feishu_bot,
        "ask_assistant",
        lambda *_args, **_kwargs: pytest.fail("invalid batch reached GPT"),
    )

    assert feishu_bot.handle_incoming_text(
        sample_config(), "/创建虚拟机 0台", PROJECT_CHAT, source="test"
    ).startswith("虚拟机创建启动失败：")


def test_start_vm_clone_batch_confirms_start_card_before_spawn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    batch = {
        "id": "batch-id",
        "requested_count": 5,
        "chat_id": PROJECT_CHAT,
        "host_machine": LOCAL_HOST,
        "start_message_uuid": "start-uuid",
    }
    monkeypatch.setattr(
        feishu_bot,
        "create_vm_clone_batch",
        lambda **_kwargs: events.append("create") or batch,
        raising=False,
    )
    monkeypatch.setattr(
        feishu_bot,
        "build_vm_clone_batch_start_card",
        lambda _batch: events.append("build-card") or {"schema": "2.0"},
        raising=False,
    )
    monkeypatch.setattr(
        feishu_bot.FeishuClient,
        "send_card",
        lambda _self, _chat, _card, *, message_uuid="": (
            events.append(f"send:{message_uuid}")
            or {"code": 0, "data": {"message_id": "start-message"}}
        ),
    )
    monkeypatch.setattr(
        feishu_bot,
        "record_vm_clone_batch_start_delivery",
        lambda _batch_id, _message_id: events.append("confirm") or batch,
        raising=False,
    )
    monkeypatch.setattr(
        feishu_bot,
        "spawn_vm_clone_batch_runner",
        lambda _config, _batch: events.append("spawn") or 4321,
        raising=False,
    )

    result = feishu_bot.start_vm_clone_batch_from_request(
        sample_config(), feishu_bot.VmCloneBatchRequest(5), PROJECT_CHAT, "test"
    )

    assert result == batch
    assert events == [
        "create",
        "build-card",
        "send:start-uuid",
        "confirm",
        "spawn",
    ]


def test_start_card_without_message_id_terminates_batch_and_never_spawns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    batch = {
        "id": "batch-id",
        "requested_count": 1,
        "chat_id": PROJECT_CHAT,
        "host_machine": LOCAL_HOST,
        "start_message_uuid": "start-uuid",
    }
    monkeypatch.setattr(feishu_bot, "create_vm_clone_batch", lambda **_kwargs: batch)
    monkeypatch.setattr(
        feishu_bot, "build_vm_clone_batch_start_card", lambda _batch: {"schema": "2.0"}
    )
    monkeypatch.setattr(
        feishu_bot.FeishuClient,
        "send_card",
        lambda *_args, **_kwargs: {"code": 0, "data": {}},
    )
    monkeypatch.setattr(
        feishu_bot,
        "freeze_vm_clone_batch",
        lambda batch_id, outcome, duration, *, failure_code="": (
            events.append(f"freeze:{batch_id}:{outcome}:{duration}:{failure_code}")
            or {**batch, "status": "failed", "outcome": "failed"}
        ),
    )
    monkeypatch.setattr(
        feishu_bot,
        "spawn_vm_clone_batch_runner",
        lambda *_args: pytest.fail("unconfirmed start spawned runner"),
    )

    with pytest.raises(feishu_bot.VmCloneBatchError, match="开始卡"):
        feishu_bot.start_vm_clone_batch_from_request(
            sample_config(), feishu_bot.VmCloneBatchRequest(1), PROJECT_CHAT, "test"
        )

    assert events == ["freeze:batch-id:failed:0:start_delivery_failed"]


def test_runner_spawn_failure_sends_frozen_failure_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    batch = {
        "id": "batch-id",
        "requested_count": 1,
        "chat_id": PROJECT_CHAT,
        "host_machine": LOCAL_HOST,
        "start_message_uuid": "start-uuid",
        "completion_message_uuid": "end-uuid",
    }
    failed = {
        **batch,
        "status": "failed",
        "outcome": "failed",
        "completed_vm_names": [],
        "duration_seconds": 0,
    }
    responses = iter(
        (
            {"code": 0, "data": {"message_id": "start-message"}},
            {"code": 0, "data": {"message_id": "end-message"}},
        )
    )
    monkeypatch.setattr(feishu_bot, "create_vm_clone_batch", lambda **_kwargs: batch)
    monkeypatch.setattr(
        feishu_bot,
        "build_vm_clone_batch_start_card",
        lambda _batch: events.append("start-card") or {"schema": "2.0"},
    )
    monkeypatch.setattr(
        feishu_bot,
        "build_vm_clone_batch_end_card",
        lambda _batch: events.append("end-card") or {"schema": "2.0"},
    )
    monkeypatch.setattr(
        feishu_bot.FeishuClient,
        "send_card",
        lambda _self, _chat, _card, *, message_uuid="": (
            events.append(f"send:{message_uuid}") or next(responses)
        ),
    )
    monkeypatch.setattr(
        feishu_bot,
        "record_vm_clone_batch_start_delivery",
        lambda *_args: events.append("confirm-start") or batch,
    )
    monkeypatch.setattr(
        feishu_bot,
        "spawn_vm_clone_batch_runner",
        lambda *_args: (_ for _ in ()).throw(OSError("spawn failed")),
    )
    monkeypatch.setattr(
        feishu_bot,
        "freeze_vm_clone_batch",
        lambda *_args, **_kwargs: events.append("freeze") or failed,
    )
    monkeypatch.setattr(
        feishu_bot,
        "record_vm_clone_batch_completion_delivery",
        lambda *_args: events.append("confirm-end") or failed,
    )

    with pytest.raises(feishu_bot.VmCloneBatchError, match="执行器启动失败"):
        feishu_bot.start_vm_clone_batch_from_request(
            sample_config(), feishu_bot.VmCloneBatchRequest(1), PROJECT_CHAT, "test"
        )

    assert events == [
        "start-card",
        "send:start-uuid",
        "confirm-start",
        "freeze",
        "end-card",
        "send:end-uuid",
        "confirm-end",
    ]


def test_vm_clone_batch_registry_rejects_a_second_active_batch(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "vm-batches.json"

    first = feishu_bot.create_vm_clone_batch(
        requested_count=5,
        chat_id=PROJECT_CHAT,
        host_machine=LOCAL_HOST,
        source="test",
        registry_path=registry,
    )

    assert first["requested_count"] == 5
    assert first["status"] == "queued"
    assert first["completed_vm_names"] == []
    assert first["start_message_uuid"]
    assert first["completion_message_uuid"]
    assert stat.S_IMODE(registry.stat().st_mode) == 0o600
    stored = json.loads(registry.read_text(encoding="utf-8"))
    assert stored["schema_version"] == 1
    assert stored["batches"] == [first]

    with pytest.raises(feishu_bot.VmCloneBatchError, match="已有虚拟机创建任务"):
        feishu_bot.create_vm_clone_batch(
            requested_count=1,
            chat_id=PROJECT_CHAT,
            host_machine=LOCAL_HOST,
            source="test",
            registry_path=registry,
        )


def test_vm_clone_batch_start_delivery_requires_and_persists_message_id(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "vm-batches.json"
    batch = feishu_bot.create_vm_clone_batch(
        requested_count=1,
        chat_id=PROJECT_CHAT,
        host_machine=LOCAL_HOST,
        source="test",
        registry_path=registry,
    )

    with pytest.raises(feishu_bot.VmCloneBatchError):
        feishu_bot.record_vm_clone_batch_start_delivery(
            batch["id"], "", registry_path=registry
        )

    delivered = feishu_bot.record_vm_clone_batch_start_delivery(
        batch["id"], "start-message", registry_path=registry
    )

    assert delivered["start_message_id"] == "start-message"
    assert delivered["status"] == "queued"


def _card_content(card: dict[str, Any]) -> str:
    return str(card["body"]["elements"][0]["text"]["content"])


def test_vm_clone_batch_cards_show_only_operational_batch_fields() -> None:
    batch = {
        "id": "secret-batch-id",
        "chat_id": "secret-chat-id",
        "host_machine": LOCAL_HOST,
        "requested_count": 2,
        "completed_count": 2,
        "completed_vm_names": ["abcd", "wxyz"],
        "available_vm_count": 11,
        "outcome": "success",
        "duration_seconds": 3661,
        "runner_log_path": "/private/runtime/secret.log",
        "raw_error": "password=secret-password",
    }

    start = feishu_bot.build_vm_clone_batch_start_card(batch)
    end = feishu_bot.build_vm_clone_batch_end_card(batch)

    assert start["schema"] == "2.0"
    assert start["header"]["title"]["content"] == "开始批量创建虚拟机"
    assert _card_content(start).splitlines() == [
        "**执行技能**：utm-vm-clone",
        "**计划创建**：2台",
        f"**宿主**：{LOCAL_HOST}",
    ]
    assert end["header"] == {
        "template": "green",
        "title": {"tag": "plain_text", "content": "虚拟机批量创建完成"},
    }
    assert _card_content(end).splitlines() == [
        "**结果**：成功",
        "**完成数量**：2/2",
        "**新建虚拟机（2）**：",
        "- abcd",
        "- wxyz",
        "",
        "**目前可用虚拟机**：11台",
        "**总耗时**：1小时 1分 1秒",
    ]
    rendered = json.dumps({"start": start, "end": end}, ensure_ascii=False)
    for secret in (
        "secret-batch-id",
        "secret-chat-id",
        "/private/runtime/secret.log",
        "secret-password",
    ):
        assert secret not in rendered
    assert "button" not in rendered


def test_failed_vm_clone_batch_card_keeps_partial_successes() -> None:
    card = feishu_bot.build_vm_clone_batch_end_card(
        {
            "requested_count": 3,
            "completed_vm_names": ["abcd"],
            "outcome": "failed",
            "duration_seconds": 65,
        }
    )

    assert card["header"] == {
        "template": "red",
        "title": {"tag": "plain_text", "content": "虚拟机批量创建失败"},
    }
    assert _card_content(card).splitlines() == [
        "**结果**：失败",
        "**完成数量**：1/3",
        "**新建虚拟机（1）**：",
        "- abcd",
        "",
        "**总耗时**：1分 5秒",
    ]


def test_failed_vm_clone_batch_card_omits_unverified_inventory_values() -> None:
    card = feishu_bot.build_vm_clone_batch_end_card(
        {
            "requested_count": 1,
            "completed_count": 0,
            "completed_vm_names": [],
            "available_vm_count": 11,
            "outcome": "failed",
            "failure_code": "SKILL_ENTRY_FAILED",
            "duration_seconds": 1,
        }
    )

    lines = _card_content(card).splitlines()
    assert not any("目前可用虚拟机" in line for line in lines)


def _prepared_batch(tmp_path: Path, count: int) -> tuple[Path, dict[str, Any]]:
    registry = tmp_path / "vm-batches.json"
    batch = feishu_bot.create_vm_clone_batch(
        requested_count=count,
        chat_id=PROJECT_CHAT,
        host_machine=LOCAL_HOST,
        source="test",
        registry_path=registry,
    )
    batch = feishu_bot.record_vm_clone_batch_start_delivery(
        batch["id"], "start-message", registry_path=registry
    )
    return registry, batch


def test_vm_clone_batch_runner_calls_skill_directly_without_inventory_checks(
    tmp_path: Path,
) -> None:
    from services import vm_clone_batch_runner

    registry, batch = _prepared_batch(tmp_path, 3)
    clone_calls: list[int] = []
    active = False
    terminal: list[dict[str, Any]] = []

    vm_names = iter(("abcd", "efgh", "wxyz"))

    def clone_once() -> str:
        nonlocal active
        assert active is False
        active = True
        clone_calls.append(len(clone_calls) + 1)
        active = False
        return next(vm_names)

    result = vm_clone_batch_runner.run_batch(
        batch["id"],
        sample_config(),
        registry_path=registry,
        clone_once=clone_once,
        available_vm_count_reader=lambda: 11,
        terminal_sender=lambda frozen: terminal.append(frozen) or "end-message",
        monotonic_clock=iter((100.0, 165.0)).__next__,
    )

    assert result == 0
    assert "inventory_reader" not in inspect.signature(
        vm_clone_batch_runner.run_batch
    ).parameters
    assert "execution_lock_path" not in inspect.signature(
        vm_clone_batch_runner.run_batch
    ).parameters
    assert clone_calls == [1, 2, 3]
    assert len(terminal) == 1
    assert terminal[0]["outcome"] == "success"
    assert terminal[0]["completed_count"] == 3
    assert terminal[0]["completed_vm_names"] == ["abcd", "efgh", "wxyz"]
    assert terminal[0]["available_vm_count"] == 11
    assert terminal[0]["duration_seconds"] == 65
    stored = feishu_bot.find_vm_clone_batch(batch["id"], registry_path=registry)
    assert stored is not None
    assert stored["status"] == "completed"
    assert stored["completion_message_id"] == "end-message"


def test_vm_clone_batch_runner_stops_after_first_skill_failure(
    tmp_path: Path,
) -> None:
    from services import vm_clone_batch_runner

    registry, batch = _prepared_batch(tmp_path, 3)
    calls = 0
    terminal: list[dict[str, Any]] = []

    def clone_once() -> str:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("sensitive low-level failure")
        return "abcd"

    result = vm_clone_batch_runner.run_batch(
        batch["id"],
        sample_config(),
        registry_path=registry,
        clone_once=clone_once,
        terminal_sender=lambda frozen: terminal.append(frozen) or "end-message",
        monotonic_clock=iter((100.0, 105.0)).__next__,
    )

    assert result == 1
    assert calls == 2
    assert len(terminal) == 1
    assert terminal[0]["outcome"] == "failed"
    assert terminal[0]["completed_count"] == 1
    assert terminal[0]["completed_vm_names"] == ["abcd"]
    assert terminal[0]["failure_code"] == "utm_vm_clone_failed"
    assert "sensitive" not in json.dumps(terminal[0])


def test_completion_delivery_failure_keeps_frozen_result_without_leaking_error(
    tmp_path: Path,
) -> None:
    from services import vm_clone_batch_runner

    registry, batch = _prepared_batch(tmp_path, 1)
    result = vm_clone_batch_runner.run_batch(
        batch["id"],
        sample_config(),
        registry_path=registry,
        clone_once=lambda: "abcd",
        available_vm_count_reader=lambda: 11,
        terminal_sender=lambda _frozen: (_ for _ in ()).throw(
            RuntimeError("secret network response")
        ),
        monotonic_clock=iter((100.0, 101.0)).__next__,
    )

    assert result == 2
    stored = feishu_bot.find_vm_clone_batch(batch["id"], registry_path=registry)
    assert stored is not None
    assert stored["status"] == "completed"
    assert stored["outcome"] == "success"
    assert stored["completed_count"] == 1
    assert stored["completed_vm_names"] == ["abcd"]
    assert stored["completion_message_id"] == ""
    assert "secret network response" not in json.dumps(stored)


def test_invalid_available_vm_count_still_freezes_and_sends_failure_card(
    tmp_path: Path,
) -> None:
    from services import vm_clone_batch_runner

    registry, batch = _prepared_batch(tmp_path, 1)
    terminal: list[dict[str, Any]] = []

    result = vm_clone_batch_runner.run_batch(
        batch["id"],
        sample_config(),
        registry_path=registry,
        clone_once=lambda: "abcd",
        available_vm_count_reader=lambda: "11",  # type: ignore[return-value]
        terminal_sender=lambda frozen: terminal.append(frozen) or "end-message",
        monotonic_clock=iter((100.0, 101.0)).__next__,
    )

    assert result == 1
    assert len(terminal) == 1
    assert terminal[0]["outcome"] == "failed"
    assert terminal[0]["completed_vm_names"] == ["abcd"]
    assert terminal[0]["failure_code"] == "AVAILABLE_VM_COUNT_INVALID"
    assert "available_vm_count" not in terminal[0]


def test_existing_utm_vm_clone_executes_the_complete_skill_entry(
    tmp_path: Path,
) -> None:
    from services import vm_clone_batch_runner

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "preflight.py").write_text(
        "import shlex\n"
        "from pathlib import Path\n"
        "root = Path(__file__).resolve().parents[1]\n"
        "print(f'export PROJECT_ROOT={shlex.quote(str(root))}')\n"
        "print('export UTM_SKILL_BOOTSTRAPPED=1')\n",
        encoding="utf-8",
    )
    (scripts / "utm_clone_and_initialize.py").write_text(
        "import os\n"
        "import sys\n"
        "if os.environ.get('UTM_SKILL_BOOTSTRAPPED') != '1':\n"
        "    print('执行报错：utm-vm-clone；BOOTSTRAP_MISSING', file=sys.stderr)\n"
        "    raise SystemExit(1)\n"
        "print('执行成功：utm-vm-clone；'\n"
        "      'UTM_CLONE_AND_INITIALIZE=verified;VM_NAME=abcd')\n",
        encoding="utf-8",
    )

    vm_name = vm_clone_batch_runner.run_existing_utm_vm_clone(
        project_root=tmp_path, timeout_seconds=123
    )

    assert vm_name == "abcd"


def test_existing_utm_vm_clone_pins_the_runner_python_interpreter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services import vm_clone_batch_runner

    captured: dict[str, Any] = {}

    def run(command: list[str], **kwargs: Any):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "执行成功：utm-vm-clone；"
                "UTM_CLONE_AND_INITIALIZE=verified;VM_NAME=abcd\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(vm_clone_batch_runner.subprocess, "run", run)

    assert (
        vm_clone_batch_runner.run_existing_utm_vm_clone(project_root=tmp_path)
        == "abcd"
    )
    command = captured["command"]
    kwargs = captured["kwargs"]
    assert command[:2] == ["/bin/zsh", "-c"]
    assert command[2].count('"$VM_CLONE_PYTHON"') == 2
    assert "python3 scripts/preflight.py" not in command[2]
    assert kwargs["env"]["VM_CLONE_PYTHON"] == sys.executable


@pytest.mark.parametrize(
    "stdout",
    (
        "执行成功：utm-vm-clone；UTM_CLONE_AND_INITIALIZE=verified\n",
        (
            "执行成功：utm-vm-clone；"
            "UTM_CLONE_AND_INITIALIZE=verified;VM_NAME=abcd\n"
            "执行成功：utm-vm-clone；"
            "UTM_CLONE_AND_INITIALIZE=verified;VM_NAME=wxyz\n"
        ),
        (
            "执行成功：utm-vm-clone；"
            "UTM_CLONE_AND_INITIALIZE=verified;VM_NAME=ABCD\n"
        ),
    ),
)
def test_existing_utm_vm_clone_rejects_missing_duplicate_or_invalid_vm_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
) -> None:
    from services import vm_clone_batch_runner

    monkeypatch.setattr(
        vm_clone_batch_runner.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command,
            0,
            stdout=stdout,
            stderr="",
        ),
    )

    with pytest.raises(vm_clone_batch_runner.VmCloneBatchExecutionError):
        vm_clone_batch_runner.run_existing_utm_vm_clone(project_root=tmp_path)


def test_existing_utm_vm_clone_reports_bootstrap_failure_safely(
    tmp_path: Path,
) -> None:
    from services import vm_clone_batch_runner

    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "preflight.py").write_text(
        "raise SystemExit(1)\n",
        encoding="utf-8",
    )

    with pytest.raises(vm_clone_batch_runner.VmCloneBatchExecutionError) as caught:
        vm_clone_batch_runner.run_existing_utm_vm_clone(project_root=tmp_path)

    assert caught.value.code == "SKILL_BOOTSTRAP_FAILED"


def test_existing_utm_vm_clone_uses_stable_code_for_unclassified_entry_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services import vm_clone_batch_runner

    monkeypatch.setattr(
        vm_clone_batch_runner.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command,
            1,
            stdout="开始执行：utm-vm-clone\n",
            stderr="unsafe child failure detail\n",
        ),
    )

    with pytest.raises(vm_clone_batch_runner.VmCloneBatchExecutionError) as caught:
        vm_clone_batch_runner.run_existing_utm_vm_clone(project_root=tmp_path)

    assert caught.value.code == "SKILL_ENTRY_FAILED"
    assert "unsafe child failure detail" not in str(caught.value)

    card = feishu_bot.build_vm_clone_batch_end_card(
        {
            "requested_count": 1,
            "completed_count": 0,
            "completed_vm_names": [],
            "outcome": "failed",
            "failure_code": caught.value.code,
            "duration_seconds": 0,
        }
    )
    assert "**失败原因**：SKILL_ENTRY_FAILED" in _card_content(card).splitlines()


def test_safe_skill_failure_reason_is_preserved_for_the_end_card(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services import vm_clone_batch_runner

    reason = "CLONE_FAILED:TEMPLATE_NOT_STOPPED"
    monkeypatch.setattr(
        vm_clone_batch_runner.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command,
            1,
            stdout="开始执行：utm-vm-clone\n",
            stderr=f"执行报错：utm-vm-clone；{reason}\n",
        ),
    )

    with pytest.raises(vm_clone_batch_runner.VmCloneBatchExecutionError) as caught:
        vm_clone_batch_runner.run_existing_utm_vm_clone(project_root=tmp_path)

    assert caught.value.code == reason

    card = feishu_bot.build_vm_clone_batch_end_card(
        {
            "requested_count": 1,
            "completed_count": 0,
            "completed_vm_names": [],
            "outcome": "failed",
            "failure_code": caught.value.code,
            "duration_seconds": 3,
        }
    )
    assert f"**失败原因**：{reason}" in _card_content(card).splitlines()
    rendered = json.dumps(card, ensure_ascii=False)
    assert "stdout" not in rendered
    assert "stderr" not in rendered


def test_spawn_vm_clone_batch_runner_is_backgrounded_without_user_argv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class Process:
        pid = 4321

    def popen(command: list[str], **kwargs: Any) -> Process:
        calls.append({"command": command, **kwargs})
        return Process()

    monkeypatch.setattr(feishu_bot, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(feishu_bot.subprocess, "Popen", popen)
    monkeypatch.setenv("PATH", "/custom/bin:/usr/bin:/bin:/usr/sbin:/sbin")
    batch = {
        "id": "a" * 32,
        "requested_count": 5,
        "chat_id": PROJECT_CHAT,
        "host_machine": LOCAL_HOST,
    }

    pid = feishu_bot.spawn_vm_clone_batch_runner(sample_config(), batch)

    assert pid == 4321
    assert len(calls) == 1
    call = calls[0]
    assert call["command"] == [
        sys.executable,
        str(feishu_bot.ROOT / "services" / "vm_clone_batch_runner.py"),
    ]
    assert call["cwd"] == str(feishu_bot.ROOT)
    assert call["stdin"] is subprocess.DEVNULL
    assert call["start_new_session"] is True
    assert call.get("shell") is None
    assert call["env"]["VM_CLONE_BATCH_ID"] == "a" * 32
    path_entries = call["env"]["PATH"].split(os.pathsep)
    assert path_entries[:5] == [
        "/custom/bin",
        "/usr/bin",
        "/bin",
        "/usr/sbin",
        "/sbin",
    ]
    assert "/opt/homebrew/bin" in path_entries
    assert "/usr/local/bin" in path_entries
    assert "requested_count" not in " ".join(call["command"])
    log_path = tmp_path / f"{'a' * 32}.vm-clone-batch.log"
    assert stat.S_IMODE(log_path.stat().st_mode) == 0o600


def test_vm_clone_process_environment_preserves_path_and_appends_tool_dirs() -> None:
    source = {
        "PATH": "/custom/bin:/usr/bin:/custom/bin",
        "VM_CHAIN_SENTINEL": "kept",
    }

    environment = feishu_bot.vm_clone_process_environment(source)

    assert environment["PATH"].split(os.pathsep) == [
        "/custom/bin",
        "/usr/bin",
        "/opt/homebrew/bin",
        "/usr/local/bin",
    ]
    assert environment["VM_CHAIN_SENTINEL"] == "kept"
    assert source["PATH"] == "/custom/bin:/usr/bin:/custom/bin"


def test_repaired_vm_clone_path_reaches_the_skill_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from services import vm_clone_batch_runner

    spawned: dict[str, Any] = {}

    class Process:
        pid = 4321

    def popen(command: list[str], **kwargs: Any) -> Process:
        spawned.update(command=command, **kwargs)
        return Process()

    monkeypatch.setattr(feishu_bot, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(feishu_bot.subprocess, "Popen", popen)
    monkeypatch.setenv("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    monkeypatch.setenv("VM_CHAIN_SENTINEL", "kept")
    feishu_bot.spawn_vm_clone_batch_runner(
        sample_config(),
        {
            "id": "a" * 32,
            "requested_count": 1,
            "chat_id": PROJECT_CHAT,
            "host_machine": LOCAL_HOST,
        },
    )

    propagated = dict(spawned["env"])
    captured_skill: dict[str, Any] = {}

    def run(command: list[str], **kwargs: Any):
        captured_skill.update(command=command, **kwargs)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "执行成功：utm-vm-clone；"
                "UTM_CLONE_AND_INITIALIZE=verified;VM_NAME=abcd\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(vm_clone_batch_runner.os, "environ", propagated)
    monkeypatch.setattr(vm_clone_batch_runner.subprocess, "run", run)

    assert (
        vm_clone_batch_runner.run_existing_utm_vm_clone(project_root=tmp_path)
        == "abcd"
    )
    assert captured_skill["env"]["PATH"] == propagated["PATH"]
    assert captured_skill["env"]["VM_CLONE_BATCH_ID"] == "a" * 32
    assert captured_skill["env"]["VM_CHAIN_SENTINEL"] == "kept"
    assert captured_skill["env"]["VM_CLONE_PYTHON"] == sys.executable


def test_duplicate_http_callback_is_acknowledged_without_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "message": {
                "message_id": "message-1",
                "chat_id": PROJECT_CHAT,
                "content": json.dumps({"text": "/创建虚拟机 5台"}),
            }
        },
    }
    raw = json.dumps(payload).encode("utf-8")
    handler_type = feishu_bot.configured_http_handler(sample_config())
    handler = object.__new__(handler_type)
    handler.path = feishu_bot.CALLBACK_PATH
    handler.headers = {"Content-Length": str(len(raw))}
    handler.rfile = io.BytesIO(raw)
    responses: list[tuple[int, dict[str, Any]]] = []
    handler._json_response = lambda status, body: responses.append((status, body))
    monkeypatch.setattr(
        feishu_bot,
        "claim_message",
        lambda _message_id, **_kwargs: False,
    )
    monkeypatch.setattr(
        feishu_bot,
        "handle_incoming_text",
        lambda *_args, **_kwargs: pytest.fail("duplicate callback was dispatched"),
    )

    handler.do_POST()

    assert responses == [(200, {"ok": True, "duplicate": True})]
