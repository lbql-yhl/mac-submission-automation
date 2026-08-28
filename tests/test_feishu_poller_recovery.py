#!/usr/bin/env python3
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import feishu_bot, feishu_supervisor
from services.host_config import ConfigurationError


ALLOWED_CHAT = "oc_allowed"


def sample_config() -> feishu_bot.Config:
    return replace(
        feishu_bot.load_config(environ={}),
        allowed_chat_id=ALLOWED_CHAT,
    )


def test_supervisor_enables_poller_only_for_allowed_chat() -> None:
    with patch.dict(
        os.environ,
        {
            "FEISHU_ALLOWED_CHAT_ID": ALLOWED_CHAT,
            "FEISHU_TUNNEL_ENABLED": "0",
        },
        clear=False,
    ):
        supervisor = feishu_supervisor.Supervisor()

    assert supervisor.poller_enabled is True
    assert supervisor.poll_chat_id == ALLOWED_CHAT
    assert supervisor.poller_command()[-1] == "poll"


def test_supervisor_never_parses_or_retains_removed_poll_list() -> None:
    with patch.dict(
        os.environ,
        {
            "FEISHU_ALLOWED_CHAT_ID": ALLOWED_CHAT,
            "FEISHU_POLL_CHAT_IDS": "oc_stale,oc_other",
            "FEISHU_TUNNEL_ENABLED": "0",
        },
        clear=False,
    ):
        supervisor = feishu_supervisor.Supervisor()

    assert supervisor.poll_chat_id == ALLOWED_CHAT
    assert not hasattr(supervisor, "poll_chat_ids")
    assert "oc_stale" not in supervisor.poller_command()
    assert "oc_other" not in supervisor.poller_command()


def test_supervisor_does_not_fallback_when_allowed_chat_is_missing() -> None:
    with patch.dict(
        os.environ,
        {
            "FEISHU_ALLOWED_CHAT_ID": "",
            "FEISHU_POLL_CHAT_IDS": "oc_stale",
            "FEISHU_TUNNEL_ENABLED": "0",
        },
        clear=False,
    ):
        supervisor = feishu_supervisor.Supervisor()

    assert supervisor.poller_enabled is False
    assert supervisor.poll_chat_id == ""


def test_poll_mode_uses_exact_allowed_chat() -> None:
    args = SimpleNamespace(
        poll_chat_id=[],
        once=True,
        poll_interval_seconds=15,
    )

    with patch.object(feishu_bot, "poll_once", return_value=0) as poll_once:
        assert feishu_bot.poll_messages(args, sample_config()) == 0

    poll_once.assert_called_once_with(sample_config())


def test_poll_mode_forces_allowed_chat_over_stale_explicit_list() -> None:
    args = SimpleNamespace(
        poll_chat_id=["oc_stale"],
        once=True,
        poll_interval_seconds=15,
    )
    config = sample_config()

    with patch.object(feishu_bot, "poll_once", return_value=0) as poll_once:
        assert feishu_bot.poll_messages(args, config) == 0

    poll_once.assert_called_once_with(config)


def test_poll_mode_refuses_to_run_without_allowed_chat() -> None:
    args = SimpleNamespace(
        poll_chat_id=["oc_stale"],
        once=True,
        poll_interval_seconds=15,
    )
    config = replace(sample_config(), allowed_chat_id="")

    with patch.object(feishu_bot, "poll_once") as poll_once:
        assert feishu_bot.poll_messages(args, config) == 2

    poll_once.assert_not_called()


def test_poll_once_refuses_to_read_any_chat_without_allowed_chat() -> None:
    config = replace(sample_config(), allowed_chat_id="")

    with patch.object(feishu_bot, "fetch_chat_messages", return_value=[]) as fetch:
        with pytest.raises(ConfigurationError, match="FEISHU_ALLOWED_CHAT_ID"):
            feishu_bot.poll_once(config)

    fetch.assert_not_called()


def test_fetch_chat_messages_refuses_any_chat_other_than_the_allowed_chat() -> None:
    config = sample_config()

    with (
        patch.object(feishu_bot, "get_tenant_access_token") as token,
        patch.object(feishu_bot.request, "urlopen") as open_url,
    ):
        with pytest.raises(ConfigurationError, match="configured allowed chat"):
            feishu_bot.fetch_chat_messages(config, "oc_stale")

    token.assert_not_called()
    open_url.assert_not_called()


class JsonResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_fetch_chat_messages_reads_every_page_without_a_twenty_message_cap() -> None:
    config = sample_config()
    requests = []
    responses = iter(
        (
            JsonResponse(
                {
                    "code": 0,
                    "data": {
                        "items": [{"message_id": "m1"}, {"message_id": "m2"}],
                        "has_more": True,
                        "page_token": "next-page",
                    },
                }
            ),
            JsonResponse(
                {
                    "code": 0,
                    "data": {
                        "items": [{"message_id": "m3"}],
                        "has_more": False,
                    },
                }
            ),
        )
    )

    def open_url(req, **_kwargs):
        requests.append(req)
        return next(responses)

    with (
        patch.object(feishu_bot, "get_tenant_access_token", return_value="token"),
        patch.object(feishu_bot.request, "urlopen", side_effect=open_url),
    ):
        items = feishu_bot.fetch_chat_messages(
            config,
            ALLOWED_CHAT,
            start_time=100,
            end_time=200,
        )

    assert [item["message_id"] for item in items] == ["m1", "m2", "m3"]
    assert len(requests) == 2
    assert "page_size=50" in requests[0].full_url
    assert "sort_type=ByCreateTimeAsc" in requests[0].full_url
    assert "start_time=100" in requests[0].full_url
    assert "end_time=200" in requests[0].full_url
    assert "page_token=next-page" in requests[1].full_url


def test_poll_watermark_advances_only_after_the_complete_scan() -> None:
    config = sample_config()
    with tempfile.TemporaryDirectory() as tmp:
        processed_dir = Path(tmp) / "processed"
        with (
            patch.object(feishu_bot, "PROCESSED_MESSAGES_DIR", processed_dir),
            patch.object(feishu_bot.time, "time", side_effect=(1_000_000, 1_000_015)),
            patch.object(feishu_bot, "fetch_chat_messages", return_value=[]) as fetch,
        ):
            assert feishu_bot.poll_once(config) == 0
            assert feishu_bot.poll_once(config) == 0

    first = fetch.call_args_list[0]
    second = fetch.call_args_list[1]
    assert first.kwargs == {"start_time": 913_600, "end_time": 1_000_000}
    assert second.kwargs == {"start_time": 999_940, "end_time": 1_000_015}
    assert first.args == (config, ALLOWED_CHAT)
    assert second.args == (config, ALLOWED_CHAT)


def test_poll_watermark_does_not_advance_past_another_live_worker() -> None:
    config = sample_config()
    item = {
        "message_id": "om_inflight",
        "sender": {"sender_type": "user"},
        "body": {"content": json.dumps({"text": "@_user_1 question"})},
    }
    with tempfile.TemporaryDirectory() as tmp:
        processed_dir = Path(tmp) / "processed"
        with patch.object(feishu_bot, "PROCESSED_MESSAGES_DIR", processed_dir):
            marker = feishu_bot.processed_message_path("om_inflight")
            feishu_bot.secure_write_text(
                marker,
                json.dumps(feishu_bot.processing_message_state()),
            )
            with (
                patch.object(feishu_bot, "message_claim_owner_is_alive", return_value=True),
                patch.object(feishu_bot, "fetch_chat_messages", return_value=[item]),
            ):
                assert feishu_bot.poll_once(config) == 0

            assert not feishu_bot.poll_watermark_path().exists()


def test_poller_claim_uses_the_configured_operation_lease() -> None:
    config = replace(
        sample_config(),
        codex_timeout_seconds=3_600,
        send_retries=4,
        send_timeout_seconds=30,
    )
    item = {
        "message_id": "om_long_poll",
        "sender": {"sender_type": "user"},
        "body": {"content": json.dumps({"text": "@_user_1 question"})},
    }

    with tempfile.TemporaryDirectory() as tmp:
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                Path(tmp) / "processed",
            ),
            patch.object(feishu_bot, "fetch_chat_messages", return_value=[item]),
            patch.object(feishu_bot, "claim_message", return_value=True) as claim,
            patch.object(feishu_bot, "process_polled_message", return_value="reply"),
            patch.object(feishu_bot, "complete_message"),
        ):
            assert feishu_bot.poll_once(config) == 1

    claim.assert_called_once_with(
        "om_long_poll",
        lease_seconds=feishu_bot.message_claim_lease_seconds(config),
    )
    assert feishu_bot.message_claim_lease_seconds(config) > 3_600


def test_poll_once_continues_after_one_message_fails() -> None:
    config = sample_config()
    items = [
        {"message_id": "om_failed"},
        {"message_id": "om_following"},
    ]
    processed: list[str] = []
    completed: list[str] = []
    released: list[str] = []

    def process(_config, _chat_id, item):
        message_id = item["message_id"]
        processed.append(message_id)
        if message_id == "om_failed":
            raise RuntimeError("one message failed")
        return "reply"

    with tempfile.TemporaryDirectory() as tmp:
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                Path(tmp) / "processed",
            ),
            patch.object(feishu_bot, "fetch_chat_messages", return_value=items),
            patch.object(feishu_bot, "claim_message", return_value=True),
            patch.object(feishu_bot, "process_polled_message", side_effect=process),
            patch.object(
                feishu_bot,
                "complete_message",
                side_effect=completed.append,
            ),
            patch.object(
                feishu_bot,
                "release_message",
                side_effect=released.append,
            ),
            patch.object(feishu_bot, "save_poll_watermark") as save_watermark,
        ):
            assert feishu_bot.poll_once(config) == 1

    assert processed == ["om_failed", "om_following"]
    assert released == ["om_failed"]
    assert completed == ["om_following"]
    save_watermark.assert_not_called()


@pytest.mark.parametrize(
    "failure_point",
    ("claim", "completion_check", "complete", "release"),
)
def test_poll_once_isolates_per_message_state_errors(failure_point: str) -> None:
    config = sample_config()
    items = [
        {"message_id": "om_failed"},
        {"message_id": "om_following"},
    ]
    processed: list[str] = []
    completed: list[str] = []

    def claim(message_id: str, **_kwargs) -> bool:
        if failure_point == "claim" and message_id == "om_failed":
            raise ConfigurationError("broken claim")
        if failure_point == "completion_check" and message_id == "om_failed":
            return False
        return True

    def completion_check(message_id: str) -> bool:
        if failure_point == "completion_check" and message_id == "om_failed":
            raise ConfigurationError("broken completion check")
        return False

    def process(_config, _chat_id, item):
        message_id = item["message_id"]
        processed.append(message_id)
        if failure_point == "release" and message_id == "om_failed":
            raise RuntimeError("force release cleanup")
        return "reply"

    def complete(message_id: str) -> None:
        if failure_point == "complete" and message_id == "om_failed":
            raise ConfigurationError("broken completion write")
        completed.append(message_id)

    def release(message_id: str) -> None:
        if failure_point == "release" and message_id == "om_failed":
            raise ConfigurationError("broken release")

    with tempfile.TemporaryDirectory() as tmp:
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                Path(tmp) / "processed",
            ),
            patch.object(feishu_bot, "fetch_chat_messages", return_value=items),
            patch.object(feishu_bot, "claim_message", side_effect=claim),
            patch.object(
                feishu_bot,
                "message_is_completed",
                side_effect=completion_check,
            ),
            patch.object(feishu_bot, "process_polled_message", side_effect=process),
            patch.object(feishu_bot, "complete_message", side_effect=complete),
            patch.object(feishu_bot, "release_message", side_effect=release),
            patch.object(feishu_bot, "save_poll_watermark") as save_watermark,
        ):
            assert feishu_bot.poll_once(config) == 1

    assert "om_following" in processed
    assert "om_following" in completed
    save_watermark.assert_not_called()


def test_dead_processing_claim_is_reclaimed_after_process_restart() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        processed_dir = Path(tmp) / "processed"
        with patch.object(feishu_bot, "PROCESSED_MESSAGES_DIR", processed_dir):
            marker = feishu_bot.processed_message_path("om_crashed")
            feishu_bot.secure_write_text(
                marker,
                json.dumps(
                    {
                        "state": "processing",
                        "owner_pid": 99999999,
                    }
                ),
            )
            with patch.object(
                feishu_bot,
                "message_claim_owner_is_alive",
                return_value=False,
                create=True,
            ):
                assert feishu_bot.claim_message("om_crashed") is True

            state = json.loads(marker.read_text(encoding="utf-8"))
            assert state["state"] == "processing"
            assert state["owner_pid"] == os.getpid()


def test_completed_message_claim_remains_deduplicated() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        processed_dir = Path(tmp) / "processed"
        with patch.object(feishu_bot, "PROCESSED_MESSAGES_DIR", processed_dir):
            assert feishu_bot.claim_message("om_complete") is True
            feishu_bot.complete_message("om_complete")
            assert feishu_bot.claim_message("om_complete") is False
            state = json.loads(
                feishu_bot.processed_message_path("om_complete").read_text(
                    encoding="utf-8"
                )
            )

    assert state["state"] == "completed"


def test_corrupt_message_claim_is_not_silently_treated_as_completed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        processed_dir = Path(tmp) / "processed"
        with patch.object(feishu_bot, "PROCESSED_MESSAGES_DIR", processed_dir):
            marker = feishu_bot.processed_message_path("om_corrupt")
            feishu_bot.secure_write_text(marker, "not-json")
            with pytest.raises(ConfigurationError, match="processed message state"):
                feishu_bot.claim_message("om_corrupt")


def test_expired_processing_claim_is_reclaimed_even_if_pid_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        processed_dir = Path(tmp) / "processed"
        with patch.object(feishu_bot, "PROCESSED_MESSAGES_DIR", processed_dir):
            marker = feishu_bot.processed_message_path("om_stuck")
            feishu_bot.secure_write_text(
                marker,
                json.dumps(
                    {
                        "state": "processing",
                        "owner_pid": os.getpid(),
                        "claimed_at": (
                            datetime.now(timezone.utc) - timedelta(hours=2)
                        ).isoformat(),
                    }
                ),
            )
            with patch.object(
                feishu_bot,
                "message_claim_owner_is_alive",
                return_value=True,
            ):
                assert feishu_bot.claim_message("om_stuck") is True


def test_processing_claim_uses_the_stored_operation_lease() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        processed_dir = Path(tmp) / "processed"
        with patch.object(feishu_bot, "PROCESSED_MESSAGES_DIR", processed_dir):
            assert feishu_bot.claim_message(
                "om_long_model",
                lease_seconds=3600,
            ) is True
            marker = feishu_bot.processed_message_path("om_long_model")
            state = json.loads(marker.read_text(encoding="utf-8"))
            state["claimed_at"] = (
                datetime.now(timezone.utc) - timedelta(minutes=20)
            ).isoformat()
            feishu_bot.secure_write_text(marker, json.dumps(state))

            with patch.object(
                feishu_bot,
                "message_claim_owner_is_alive",
                return_value=True,
            ):
                assert feishu_bot.claim_message("om_long_model") is False

    assert state["lease_seconds"] == 3600
