from __future__ import annotations

from pathlib import Path

from services.feishu_bot import SUBMISSION_START_ENABLED, build_codex_prompt


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "skills" / "_shared" / "AUTOMATION_CONTRACT.md"


def sample_run() -> dict[str, object]:
    return {
        "id": "exact-run-42",
        "app_name": "SampleApp",
        "vm_name": "abcd",
        "chat_id": "exact-project-chat",
        "raw_text": "explicit registration payload",
        "submission_data": {"host_machine": "exact-host-a"},
    }


def test_generated_prompt_and_shared_contract_wire_lifecycle_commands() -> None:
    prompt = build_codex_prompt(sample_run())
    contract = CONTRACT.read_text(encoding="utf-8")

    for source in (prompt, contract):
        for command in (
            "run-start",
            "skill-start",
            "skill-success",
            "skill-failure",
            "notify-fault",
            "wait-decision",
            "run-finish",
        ):
            assert command in source
        assert source.index("run-start") < source.index("skill-start")
        assert source.index("skill-start") < source.index("skill-success")
        assert source.index("skill-failure") < source.index("notify-fault")
        assert source.index("notify-fault") < source.index("wait-decision")
        assert source.index("wait-decision") < source.index("run-finish")


def test_lifecycle_contract_places_commands_at_authoritative_boundaries() -> None:
    prompt = build_codex_prompt(sample_run())
    contract = CONTRACT.read_text(encoding="utf-8")

    for source in (prompt, contract):
        assert "首次技能副作用之前" in source
        assert "恢复穷尽后" in source
        assert "请求范围尾端" in source
        assert "终止失败或停止" in source


def test_generated_prompt_preserves_exact_inherited_run_chat_and_host() -> None:
    prompt = build_codex_prompt(sample_run())

    assert "--run-id exact-run-42" in prompt
    assert "--chat-id exact-project-chat" in prompt
    assert "宿主身份：exact-host-a" in prompt
    assert "同一精确 run、原 chat_id 和宿主身份" in prompt


def test_intake_stays_disabled() -> None:
    assert SUBMISSION_START_ENABLED is False
