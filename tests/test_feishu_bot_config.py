from __future__ import annotations

from dataclasses import replace

import pytest

from services import feishu_bot


def test_daily_report_chat_is_loaded_and_used_by_routing_guards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(feishu_bot, "load_dotenv", lambda _path: None)
    monkeypatch.setenv("FEISHU_DAILY_REPORT_CHAT_ID", "daily-report-chat")
    config = replace(
        feishu_bot.load_config(),
        allowed_chat_id="",
        assistant_enabled=False,
        submission_host_machine="Local Host",
    )

    assert config.daily_report_chat_id == "daily-report-chat"
    assert (
        feishu_bot.handle_incoming_text(
            config,
            "/提审 帮助",
            "daily-report-chat",
            source="test",
        )
        == ""
    )
    assert "提审机器人命令" in feishu_bot.handle_incoming_text(
        config,
        "/提审 帮助",
        "workflow-chat",
        source="test",
    )
    with pytest.raises(RuntimeError, match="original workflow chat"):
        feishu_bot.local_original_chat(
            {
                "chat_id": "daily-report-chat",
                "submission_data": {"host_machine": "Local Host"},
            },
            config,
        )


def test_source_has_no_fixed_daily_report_destination() -> None:
    assert not hasattr(feishu_bot, "DAILY_REPORT_CHAT_ID")
