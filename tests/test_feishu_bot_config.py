from __future__ import annotations

import importlib
import inspect
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest

from services.host_config import ConfigurationError


@pytest.fixture
def feishu_bot() -> ModuleType:
    return importlib.import_module("services.feishu_bot")


def test_import_does_not_read_or_require_host_dotenv(
) -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from pathlib import Path
import services.host_config as host_config

original_read_text = Path.read_text
def reject_dotenv_read(path, *args, **kwargs):
    if path.name == '.env':
        raise AssertionError('module import must not read the host .env')
    return original_read_text(path, *args, **kwargs)

Path.read_text = reject_dotenv_read
host_config._dotenv_setting = lambda *_args, **_kwargs: (_ for _ in ()).throw(
    AssertionError('module import must not resolve settings from the host .env')
)
import services.feishu_bot as module
assert 'config' not in module.FeishuHandler.__dict__
assert 'client' not in module.FeishuHandler.__dict__
print('IMPORT_OK')
""",
        ],
        cwd=root,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "IMPORT_OK"


@pytest.mark.parametrize("configured", ({}, {"FEISHU_DAILY_REPORT_CHAT_ID": "   "}))
def test_load_config_requires_daily_report_chat_without_revealing_values(
    feishu_bot: ModuleType,
    configured: dict[str, str],
) -> None:
    with pytest.raises(ConfigurationError) as captured:
        feishu_bot.load_config(environ=configured)

    assert str(captured.value) == (
        "missing required host setting: FEISHU_DAILY_REPORT_CHAT_ID"
    )
    assert all(value not in str(captured.value) for value in configured.values())


def test_load_config_reads_without_mutating_process_environment(
    feishu_bot: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "FEISHU_DAILY_REPORT_CHAT_ID=configured-report-chat\n"
        "SUBMISSION_HOST_MACHINE=Configured Host\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("FEISHU_DAILY_REPORT_CHAT_ID", raising=False)
    monkeypatch.delenv("SUBMISSION_HOST_MACHINE", raising=False)
    before = dict(os.environ)

    config = feishu_bot.load_config(env_path=env_path)

    assert config.daily_report_chat_id == "configured-report-chat"
    assert config.submission_host_machine == "Configured Host"
    assert dict(os.environ) == before


def test_daily_report_chat_is_loaded_and_used_by_routing_guards(
    feishu_bot: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = replace(
        feishu_bot.load_config(
            environ={"FEISHU_DAILY_REPORT_CHAT_ID": "daily-report-chat"}
        ),
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


def test_card_entrypoints_require_daily_report_destination(
    feishu_bot: ModuleType,
) -> None:
    for function in (
        feishu_bot.reject_nonlocal_card_callback,
        feishu_bot.handle_review_card_action,
        feishu_bot.handle_confirmation_card_action,
        feishu_bot.handle_card_action,
        feishu_bot.handle_ws_card_action,
    ):
        parameter = inspect.signature(function).parameters["daily_report_chat_id"]
        assert parameter.default is inspect.Parameter.empty


def test_source_has_no_fixed_daily_report_destination(
    feishu_bot: ModuleType,
) -> None:
    assert not hasattr(feishu_bot, "DAILY_REPORT_CHAT_ID")
