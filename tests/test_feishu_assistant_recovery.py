#!/usr/bin/env python3
import json
import io
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import services.feishu_bot as feishu_bot
import services.feishu_gateway as feishu_gateway


FIXTURE_ALLOWED_CHAT = "oc_allowed"
FIXTURE_WRONG_CHAT = "oc_wrong"
FIXTURE_SENSITIVE_CHAT = "oc_sensitive_chat"


class ImmediateThread:
    def __init__(self, target, **_kwargs):
        self.target = target

    def start(self):
        self.target()


class JsonResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def assistant_config():
    return replace(
        feishu_bot.load_config(
            environ={"FEISHU_DAILY_REPORT_CHAT_ID": "test-report-chat"}
        ),
        allowed_chat_id=FIXTURE_ALLOWED_CHAT,
        assistant_provider="codex",
        assistant_enabled=True,
        assistant_require_mention=True,
        codex_command="/opt/test/bin/codex",
        codex_model="gpt-5.6-sol",
    )


def test_codex_command() -> None:
    captured = []

    def fake_run(cmd, **_kwargs):
        captured.append(cmd)
        Path(cmd[cmd.index("-o") + 1]).write_text("MODEL_OK", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with (
            patch.object(feishu_bot, "RUNTIME_DIR", tmp_path),
            patch.object(feishu_bot, "CONVERSATIONS_FILE", tmp_path / "conversations.json"),
            patch.object(feishu_bot.subprocess, "run", fake_run),
        ):
            assert feishu_bot.ask_codex_assistant(
                assistant_config(), FIXTURE_ALLOWED_CHAT, "你是谁"
            ) == "MODEL_OK"

    cmd = captured[0]
    assert cmd[0] == "/opt/test/bin/codex"
    assert 'model_reasoning_effort="high"' in cmd
    assert 'model_reasoning_effort="low"' not in cmd
    assert "--skip-git-repo-check" in cmd
    assert cmd[cmd.index("-m") + 1] == "gpt-5.6-sol"


def test_codex_command_is_found_with_launchd_system_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        fake_home = tmp_path / "home"
        fake_bin = fake_home / ".local" / "bin"
        fake_bin.mkdir(parents=True)
        fake_codex = fake_bin / "codex"
        fake_codex.write_text(
            """#!/bin/sh
output=''
while [ "$#" -gt 0 ]; do
  if [ "$1" = '-o' ]; then
    shift
    output="$1"
  fi
  shift
done
test -n "$output" || exit 2
printf 'LAUNCHD_CODEX_OK' > "$output"
""",
            encoding="utf-8",
        )
        fake_codex.chmod(0o700)
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        config = replace(assistant_config(), codex_command="codex")

        with (
            patch.dict(
                os.environ,
                {
                    "HOME": str(fake_home),
                    "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                },
                clear=True,
            ),
            patch.object(feishu_bot, "RUNTIME_DIR", runtime),
            patch.object(
                feishu_bot,
                "CONVERSATIONS_FILE",
                runtime / "conversations.json",
            ),
        ):
            reply = feishu_bot.ask_codex_assistant(
                config,
                FIXTURE_ALLOWED_CHAT,
                "项目技能有什么",
            )

    assert reply == "LAUNCHD_CODEX_OK"


def test_text_sender_includes_stable_feishu_uuid() -> None:
    sent_bodies = []

    def post_json(_url, body, _headers, **_kwargs):
        sent_bodies.append(body)
        return {"code": 0, "data": {"message_id": "message"}}

    with (
        patch.object(
            feishu_gateway,
            "network_precheck",
            return_value={"ok": True, "host": "open.feishu.cn", "port": 443},
        ),
        patch.object(
            feishu_gateway,
            "get_tenant_access_token",
            return_value="token",
        ),
        patch.object(feishu_gateway, "post_json", side_effect=post_json),
    ):
        feishu_gateway.send_text_message(
            "app",
            "secret",
            "chat",
            "answer",
            message_uuid="gpt-final-stable",
        )

    assert sent_bodies == [
        {
            "receive_id": "chat",
            "msg_type": "text",
            "content": json.dumps({"text": "answer"}, ensure_ascii=False),
            "uuid": "gpt-final-stable",
        }
    ]


def test_assistant_text_uuid_is_stable_phase_scoped_and_within_feishu_limit() -> None:
    first = feishu_bot.assistant_text_message_uuid("source-message", "final")
    second = feishu_bot.assistant_text_message_uuid("source-message", "final")
    progress = feishu_bot.assistant_text_message_uuid("source-message", "progress")

    assert first == second
    assert first != progress
    assert len(first) <= 50


def test_feishu_client_adds_and_removes_typing_reaction_via_openapi() -> None:
    client = feishu_bot.FeishuClient(assistant_config())
    requests = []

    def open_url(req, **_kwargs):
        requests.append(req)
        if req.get_method() == "POST":
            return JsonResponse(
                {"code": 0, "data": {"reaction_id": "reaction_openapi"}}
            )
        return JsonResponse({"code": 0, "data": {}})

    with (
        patch.object(
            feishu_bot,
            "get_tenant_access_token",
            side_effect=("tenant-token-add", "tenant-token-delete"),
        ) as get_token,
        patch.object(
            client,
            "app_access_token",
            side_effect=AssertionError("reaction API must use tenant_access_token"),
        ),
        patch.object(feishu_bot.request, "urlopen", side_effect=open_url),
    ):
        reaction_id = client.add_message_reaction("message_openapi", "Typing")
        client.remove_message_reaction("message_openapi", reaction_id)

    assert get_token.call_count == 2
    assert reaction_id == "reaction_openapi"
    assert [req.get_method() for req in requests] == ["POST", "DELETE"]
    assert requests[0].get_header("Authorization") == "Bearer tenant-token-add"
    assert requests[1].get_header("Authorization") == "Bearer tenant-token-delete"
    assert requests[0].full_url.endswith(
        "/open-apis/im/v1/messages/message_openapi/reactions"
    )
    assert json.loads(requests[0].data.decode("utf-8")) == {
        "reaction_type": {"emoji_type": "Typing"}
    }
    assert requests[1].full_url.endswith(
        "/open-apis/im/v1/messages/message_openapi/reactions/reaction_openapi"
    )


def test_feishu_client_lists_only_its_own_typing_reactions() -> None:
    client = feishu_bot.FeishuClient(
        replace(assistant_config(), app_id="cli_current_bot")
    )
    requests = []
    response = JsonResponse(
        {
            "code": 0,
            "data": {
                "items": [
                    {
                        "reaction_id": "reaction_own",
                        "operator": {
                            "operator_type": "app",
                            "operator_id": "cli_current_bot",
                        },
                        "reaction_type": {"emoji_type": "Typing"},
                    },
                    {
                        "reaction_id": "reaction_other_bot",
                        "operator": {
                            "operator_type": "app",
                            "operator_id": "cli_other_bot",
                        },
                        "reaction_type": {"emoji_type": "Typing"},
                    },
                    {
                        "reaction_id": "reaction_user",
                        "operator": {
                            "operator_type": "user",
                            "operator_id": "ou_user",
                        },
                        "reaction_type": {"emoji_type": "Typing"},
                    },
                ],
                "has_more": False,
            },
        }
    )

    def open_url(req, **_kwargs):
        requests.append(req)
        return response

    with (
        patch.object(
            feishu_bot,
            "get_tenant_access_token",
            return_value="tenant-token-list",
        ),
        patch.object(feishu_bot.request, "urlopen", side_effect=open_url),
    ):
        reaction_ids = client.list_own_message_reaction_ids(
            "message_openapi",
            "Typing",
        )

    assert reaction_ids == ["reaction_own"]
    assert len(requests) == 1
    assert requests[0].get_method() == "GET"
    assert requests[0].full_url.endswith(
        "/open-apis/im/v1/messages/message_openapi/reactions"
        "?reaction_type=Typing&page_size=50"
    )


def test_websocket_acknowledges_before_model_answer_and_poller_does_not_duplicate() -> None:
    config = assistant_config()
    events: list[tuple[str, ...]] = []
    event = SimpleNamespace(
        event=SimpleNamespace(
            message=SimpleNamespace(
                message_id="om_test",
                chat_id=FIXTURE_ALLOWED_CHAT,
                content=json.dumps({"text": "@_user_1 你是谁"}, ensure_ascii=False),
            )
        )
    )
    history_item = {
        "message_id": "om_test",
        "sender": {"sender_type": "user"},
        "body": {"content": json.dumps({"text": "@_user_1 你是谁"}, ensure_ascii=False)},
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        def answer(*_args, **_kwargs):
            events.append(("model", "called"))
            return "测试回复"

        with (
            patch.object(feishu_bot, "PROCESSED_MESSAGES_FILE", tmp_path / "processed.json"),
            patch.object(feishu_bot, "PROCESSED_MESSAGES_DIR", tmp_path / "processed", create=True),
            patch.object(feishu_bot, "load_config", return_value=config),
            patch.object(feishu_bot, "ask_assistant", side_effect=answer),
            patch.object(
                feishu_bot.FeishuClient,
                "add_message_reaction",
                lambda _self, message_id, emoji_type: (
                    events.append(("reaction_add", message_id, emoji_type))
                    or "reaction_test"
                ),
                create=True,
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "remove_message_reaction",
                lambda _self, message_id, reaction_id: events.append(
                    ("reaction_remove", message_id, reaction_id)
                ),
                create=True,
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "send_text",
                lambda _self, _chat_id, text, *, message_uuid="": events.append(
                    ("send", text, message_uuid)
                ),
            ),
            patch.object(feishu_bot, "fetch_chat_messages", return_value=[history_item]),
            patch.object(feishu_bot.threading, "Thread", ImmediateThread),
        ):
            feishu_bot.handle_ws_message_receive(event, config)
            assert feishu_bot.poll_once(config) == 0
            claim_state = json.loads(
                feishu_bot.processed_message_path("om_test").read_text(
                    encoding="utf-8"
                )
            )

    assert events == [
        ("reaction_add", "om_test", "Typing"),
        ("model", "called"),
        (
            "send",
            "测试回复",
            feishu_bot.assistant_text_message_uuid("om_test", "final"),
        ),
        ("reaction_remove", "om_test", "reaction_test"),
    ]
    assert claim_state["state"] == "completed"


def test_websocket_claim_uses_the_configured_operation_lease() -> None:
    config = replace(
        assistant_config(),
        codex_timeout_seconds=3_600,
        send_retries=4,
        send_timeout_seconds=30,
    )
    event = SimpleNamespace(
        event=SimpleNamespace(
            message=SimpleNamespace(
                message_id="om_long_ws",
                chat_id=FIXTURE_ALLOWED_CHAT,
                content=json.dumps({"text": "@_user_1 question"}),
            )
        )
    )

    with (
        patch.object(feishu_bot, "claim_message", return_value=True) as claim,
        patch.object(feishu_bot, "deliver_incoming_message_reply", return_value="reply"),
        patch.object(feishu_bot, "complete_message"),
        patch.object(feishu_bot.threading, "Thread", ImmediateThread),
    ):
        feishu_bot.handle_ws_message_receive(event, config)

    claim.assert_called_once_with(
        "om_long_ws",
        lease_seconds=feishu_bot.message_claim_lease_seconds(config),
    )


def test_webhook_claim_uses_the_configured_operation_lease() -> None:
    config = replace(
        assistant_config(),
        codex_timeout_seconds=3_600,
        send_retries=4,
        send_timeout_seconds=30,
    )
    payload = {
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "message": {
                "message_id": "om_long_http",
                "chat_id": FIXTURE_ALLOWED_CHAT,
                "content": json.dumps({"text": "@_user_1 question"}),
            }
        },
    }
    raw = json.dumps(payload).encode("utf-8")
    handler_type = feishu_bot.configured_http_handler(config)
    handler = object.__new__(handler_type)
    handler.path = feishu_bot.CALLBACK_PATH
    handler.headers = {"Content-Length": str(len(raw))}
    handler.rfile = io.BytesIO(raw)
    responses = []
    handler._json_response = lambda status, body: responses.append((status, body))

    with (
        patch.object(feishu_bot, "verify_signature", return_value=True),
        patch.object(feishu_bot, "claim_message", return_value=True) as claim,
        patch.object(feishu_bot, "deliver_incoming_message_reply", return_value="reply"),
        patch.object(feishu_bot, "complete_message"),
        patch.object(feishu_bot.threading, "Thread", ImmediateThread),
    ):
        handler.do_POST()

    claim.assert_called_once_with(
        "om_long_http",
        lease_seconds=feishu_bot.message_claim_lease_seconds(config),
    )
    assert responses == [(200, {"ok": True})]


def test_websocket_model_exception_still_gets_an_explicit_final_reply() -> None:
    config = assistant_config()
    events: list[tuple[str, ...]] = []
    event = SimpleNamespace(
        event=SimpleNamespace(
            message=SimpleNamespace(
                message_id="om_failure",
                chat_id=FIXTURE_ALLOWED_CHAT,
                content=json.dumps(
                    {"text": "@_user_1 项目技能有什么"},
                    ensure_ascii=False,
                ),
            )
        )
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                tmp_path / "processed",
                create=True,
            ),
            patch.object(
                feishu_bot,
                "ask_assistant",
                side_effect=RuntimeError("synthetic model failure"),
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "add_message_reaction",
                lambda _self, message_id, emoji_type: (
                    events.append(("reaction_add", message_id, emoji_type))
                    or "reaction_failure"
                ),
                create=True,
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "remove_message_reaction",
                lambda _self, message_id, reaction_id: events.append(
                    ("reaction_remove", message_id, reaction_id)
                ),
                create=True,
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "send_text",
                lambda _self, _chat_id, text, *, message_uuid="": events.append(
                    ("send", text)
                ),
            ),
            patch.object(feishu_bot.threading, "Thread", ImmediateThread),
        ):
            feishu_bot.handle_ws_message_receive(event, config)

    assert events == [
        ("reaction_add", "om_failure", "Typing"),
        ("send", "GPT 本次处理失败，请稍后重试。"),
        ("reaction_remove", "om_failure", "reaction_failure"),
    ]


def test_websocket_reaction_failure_falls_back_without_blocking_model() -> None:
    config = assistant_config()
    events: list[tuple[str, ...]] = []
    event = SimpleNamespace(
        event=SimpleNamespace(
            message=SimpleNamespace(
                message_id="om_reaction_failure",
                chat_id=FIXTURE_ALLOWED_CHAT,
                content=json.dumps({"text": "@_user_1 你是谁"}, ensure_ascii=False),
            )
        )
    )

    def fail_reaction(*_args, **_kwargs):
        events.append(("reaction_add", "failed"))
        raise RuntimeError("synthetic reaction failure")

    def answer(*_args, **_kwargs):
        events.append(("model", "called"))
        return "测试回复"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                tmp_path / "processed",
                create=True,
            ),
            patch.object(feishu_bot, "ask_assistant", side_effect=answer),
            patch.object(
                feishu_bot.FeishuClient,
                "add_message_reaction",
                side_effect=fail_reaction,
                create=True,
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "remove_message_reaction",
                lambda *_args, **_kwargs: events.append(("reaction_remove",)),
                create=True,
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "list_own_message_reaction_ids",
                lambda _self, message_id, emoji_type: (
                    events.append(("reaction_list", message_id, emoji_type)) or []
                ),
                create=True,
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "send_text",
                lambda _self, _chat_id, text, *, message_uuid="": events.append(
                    ("send", text)
                ),
            ),
            patch.object(feishu_bot.threading, "Thread", ImmediateThread),
        ):
            feishu_bot.handle_ws_message_receive(event, config)

    assert events == [
        ("reaction_add", "failed"),
        ("send", "⌨️ GPT 已收到，正在思考。"),
        ("model", "called"),
        ("send", "测试回复"),
        ("reaction_list", "om_reaction_failure", "Typing"),
    ]


def test_websocket_delete_failure_recovers_own_typing_reaction_by_listing() -> None:
    config = assistant_config()
    events: list[tuple[str, ...]] = []
    event = SimpleNamespace(
        event=SimpleNamespace(
            message=SimpleNamespace(
                message_id="om_delete_retry",
                chat_id=FIXTURE_ALLOWED_CHAT,
                content=json.dumps({"text": "@_user_1 你是谁"}, ensure_ascii=False),
            )
        )
    )
    delete_attempts = 0

    def remove(_self, message_id, reaction_id):
        nonlocal delete_attempts
        delete_attempts += 1
        events.append(("reaction_remove", message_id, reaction_id))
        if delete_attempts == 1:
            raise RuntimeError("synthetic first delete failure")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                tmp_path / "processed",
                create=True,
            ),
            patch.object(feishu_bot, "ask_assistant", return_value="模型答案"),
            patch.object(
                feishu_bot.FeishuClient,
                "add_message_reaction",
                return_value="reaction_delete_retry",
            ),
            patch.object(feishu_bot.FeishuClient, "remove_message_reaction", remove),
            patch.object(
                feishu_bot.FeishuClient,
                "list_own_message_reaction_ids",
                lambda _self, message_id, emoji_type: (
                    events.append(("reaction_list", message_id, emoji_type))
                    or ["reaction_delete_retry"]
                ),
                create=True,
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "send_text",
                lambda _self, _chat_id, text, *, message_uuid="": events.append(
                    ("send", text)
                ),
            ),
            patch.object(feishu_bot.threading, "Thread", ImmediateThread),
        ):
            feishu_bot.handle_ws_message_receive(event, config)

    assert events == [
        ("send", "模型答案"),
        ("reaction_remove", "om_delete_retry", "reaction_delete_retry"),
        ("reaction_list", "om_delete_retry", "Typing"),
        ("reaction_remove", "om_delete_retry", "reaction_delete_retry"),
    ]


def test_websocket_final_send_failure_still_removes_reaction_and_reports_failure() -> None:
    config = assistant_config()
    events: list[tuple[str, ...]] = []
    event = SimpleNamespace(
        event=SimpleNamespace(
            message=SimpleNamespace(
                message_id="om_send_failure",
                chat_id=FIXTURE_ALLOWED_CHAT,
                content=json.dumps({"text": "@_user_1 你是谁"}, ensure_ascii=False),
            )
        )
    )

    def send(_self, _chat_id, text, *, message_uuid=""):
        events.append(("send", text))
        if text == "模型答案":
            raise RuntimeError("synthetic final send failure")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                tmp_path / "processed",
                create=True,
            ),
            patch.object(feishu_bot, "ask_assistant", return_value="模型答案"),
            patch.object(
                feishu_bot.FeishuClient,
                "add_message_reaction",
                return_value="reaction_send_failure",
                create=True,
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "remove_message_reaction",
                lambda _self, message_id, reaction_id: events.append(
                    ("reaction_remove", message_id, reaction_id)
                ),
                create=True,
            ),
            patch.object(feishu_bot.FeishuClient, "send_text", send),
            patch.object(feishu_bot.threading, "Thread", ImmediateThread),
        ):
            feishu_bot.handle_ws_message_receive(event, config)

    assert events == [
        ("send", "模型答案"),
        ("send", "GPT 本次处理失败，请稍后重试。"),
        ("reaction_remove", "om_send_failure", "reaction_send_failure"),
    ]


def test_websocket_non_model_command_does_not_add_typing_reaction() -> None:
    config = assistant_config()
    sent: list[str] = []
    event = SimpleNamespace(
        event=SimpleNamespace(
            message=SimpleNamespace(
                message_id="om_help",
                chat_id=FIXTURE_ALLOWED_CHAT,
                content=json.dumps({"text": "/提审 帮助"}, ensure_ascii=False),
            )
        )
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                tmp_path / "processed",
                create=True,
            ),
            patch.object(feishu_bot, "ask_assistant") as assistant,
            patch.object(
                feishu_bot.FeishuClient,
                "add_message_reaction",
                side_effect=AssertionError("command must not add a typing reaction"),
                create=True,
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "send_text",
                lambda _self, _chat_id, text, *, message_uuid="": sent.append(text),
            ),
            patch.object(feishu_bot.threading, "Thread", ImmediateThread),
        ):
            feishu_bot.handle_ws_message_receive(event, config)

    assistant.assert_not_called()
    assert sent == [feishu_bot.HELP_TEXT]


def test_websocket_ignored_message_does_not_add_typing_reaction() -> None:
    config = assistant_config()
    event = SimpleNamespace(
        event=SimpleNamespace(
            message=SimpleNamespace(
                message_id="om_ignored",
                chat_id=FIXTURE_ALLOWED_CHAT,
                content=json.dumps({"text": "普通群聊"}, ensure_ascii=False),
            )
        )
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                tmp_path / "processed",
                create=True,
            ),
            patch.object(feishu_bot, "ask_assistant") as assistant,
            patch.object(
                feishu_bot.FeishuClient,
                "add_message_reaction",
                side_effect=AssertionError("ignored text must not add a typing reaction"),
                create=True,
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "send_text",
                side_effect=AssertionError("ignored text must not send"),
            ),
            patch.object(feishu_bot.threading, "Thread", ImmediateThread),
        ):
            feishu_bot.handle_ws_message_receive(event, config)

    assistant.assert_not_called()


def test_websocket_live_project_query_adds_typing_reaction_before_model() -> None:
    config = replace(
        assistant_config(),
        assistant_provider="openai",
        openai_api_key="",
    )
    events: list[tuple[str, ...]] = []
    event = SimpleNamespace(
        event=SimpleNamespace(
            message=SimpleNamespace(
                message_id="om_live_query",
                chat_id=FIXTURE_ALLOWED_CHAT,
                content=json.dumps(
                    {"text": "目前可用虚拟机有多少"},
                    ensure_ascii=False,
                ),
            )
        )
    )

    def answer(*_args, **kwargs):
        events.append(("model", kwargs.get("live_context", "")))
        return "当前有 1 台可用虚拟机。"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                tmp_path / "processed",
                create=True,
            ),
            patch.object(feishu_bot, "handle_project_query", return_value="vm-live"),
            patch.object(feishu_bot, "ask_codex_assistant", side_effect=answer),
            patch.object(
                feishu_bot,
                "ask_assistant",
                side_effect=AssertionError(
                    "live project query must bypass generic provider routing"
                ),
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "add_message_reaction",
                lambda _self, message_id, emoji_type: (
                    events.append(("reaction_add", message_id, emoji_type))
                    or "reaction_live_query"
                ),
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "remove_message_reaction",
                lambda _self, message_id, reaction_id: events.append(
                    ("reaction_remove", message_id, reaction_id)
                ),
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "send_text",
                lambda _self, _chat_id, text, *, message_uuid="": events.append(
                    ("send", text)
                ),
            ),
            patch.object(feishu_bot.threading, "Thread", ImmediateThread),
        ):
            feishu_bot.handle_ws_message_receive(event, config)

    assert events == [
        ("reaction_add", "om_live_query", "Typing"),
        ("model", "vm-live"),
        ("send", "当前有 1 台可用虚拟机。"),
        ("reaction_remove", "om_live_query", "reaction_live_query"),
    ]


def test_websocket_wrong_chat_does_not_add_typing_reaction() -> None:
    config = assistant_config()
    event = SimpleNamespace(
        event=SimpleNamespace(
            message=SimpleNamespace(
                message_id="om_wrong_chat",
                chat_id=FIXTURE_WRONG_CHAT,
                content=json.dumps({"text": "@_user_1 你是谁"}, ensure_ascii=False),
            )
        )
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                tmp_path / "processed",
                create=True,
            ),
            patch.object(feishu_bot, "ask_assistant") as assistant,
            patch.object(
                feishu_bot.FeishuClient,
                "add_message_reaction",
                side_effect=AssertionError("wrong chat must not add a reaction"),
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "send_text",
                side_effect=AssertionError("wrong chat must not send"),
            ),
            patch.object(feishu_bot.threading, "Thread", ImmediateThread),
        ):
            feishu_bot.handle_ws_message_receive(event, config)

    assistant.assert_not_called()


def test_websocket_logs_do_not_expose_chat_message_id_or_text() -> None:
    config = replace(assistant_config(), allowed_chat_id=FIXTURE_SENSITIVE_CHAT)
    event = SimpleNamespace(
        event=SimpleNamespace(
            message=SimpleNamespace(
                message_id="om_sensitive_message",
                chat_id=FIXTURE_SENSITIVE_CHAT,
                content=json.dumps(
                    {"text": "private user question"},
                    ensure_ascii=False,
                ),
            )
        )
    )
    logs: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                Path(tmp) / "processed",
            ),
            patch.object(
                feishu_bot,
                "safe_print",
                lambda *args, **_kwargs: logs.append(" ".join(map(str, args))),
            ),
            patch.object(feishu_bot.threading, "Thread", ImmediateThread),
        ):
            feishu_bot.handle_ws_message_receive(event, config)

    output = "\n".join(logs)
    assert "oc_sensitive_chat" not in output
    assert "om_sensitive_message" not in output
    assert "private user question" not in output


def test_poller_takeover_uses_same_typing_reaction_lifecycle() -> None:
    config = assistant_config()
    events: list[tuple[str, ...]] = []
    history_item = {
        "message_id": "om_poll_takeover",
        "sender": {"sender_type": "user"},
        "body": {
            "content": json.dumps(
                {"text": "@_user_1 你是谁"},
                ensure_ascii=False,
            )
        },
    }

    def answer(*_args, **_kwargs):
        events.append(("model", "called"))
        return "轮询恢复回复"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                tmp_path / "processed",
                create=True,
            ),
            patch.object(feishu_bot, "fetch_chat_messages", return_value=[history_item]),
            patch.object(feishu_bot, "ask_assistant", side_effect=answer),
            patch.object(
                feishu_bot.FeishuClient,
                "add_message_reaction",
                lambda _self, message_id, emoji_type: (
                    events.append(("reaction_add", message_id, emoji_type))
                    or "reaction_poll"
                ),
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "remove_message_reaction",
                lambda _self, message_id, reaction_id: events.append(
                    ("reaction_remove", message_id, reaction_id)
                ),
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "send_text",
                lambda _self, _chat_id, text, *, message_uuid="": events.append(
                    ("send", text)
                ),
            ),
        ):
            assert feishu_bot.poll_once(config) == 1
            claim_state = json.loads(
                feishu_bot.processed_message_path("om_poll_takeover").read_text(
                    encoding="utf-8"
                )
            )

    assert events == [
        ("reaction_add", "om_poll_takeover", "Typing"),
        ("model", "called"),
        ("send", "轮询恢复回复"),
        ("reaction_remove", "om_poll_takeover", "reaction_poll"),
    ]
    assert claim_state["state"] == "completed"


def test_poller_model_exception_sends_explicit_failure_and_removes_reaction() -> None:
    config = assistant_config()
    events: list[tuple[str, ...]] = []
    history_item = {
        "message_id": "om_poll_failure",
        "sender": {"sender_type": "user"},
        "body": {
            "content": json.dumps(
                {"text": "@_user_1 项目技能有什么"},
                ensure_ascii=False,
            )
        },
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with (
            patch.object(
                feishu_bot,
                "PROCESSED_MESSAGES_DIR",
                tmp_path / "processed",
                create=True,
            ),
            patch.object(feishu_bot, "fetch_chat_messages", return_value=[history_item]),
            patch.object(
                feishu_bot,
                "ask_assistant",
                side_effect=RuntimeError("synthetic poll model failure"),
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "add_message_reaction",
                return_value="reaction_poll_failure",
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "remove_message_reaction",
                lambda _self, message_id, reaction_id: events.append(
                    ("reaction_remove", message_id, reaction_id)
                ),
            ),
            patch.object(
                feishu_bot.FeishuClient,
                "send_text",
                lambda _self, _chat_id, text, *, message_uuid="": events.append(
                    ("send", text)
                ),
            ),
        ):
            assert feishu_bot.poll_once(config) == 1

    assert events == [
        ("send", "GPT 本次处理失败，请稍后重试。"),
        ("reaction_remove", "om_poll_failure", "reaction_poll_failure"),
    ]


def test_unconfigured_openai_reply_does_not_claim_gpt_is_thinking() -> None:
    config = replace(
        assistant_config(),
        assistant_provider="openai",
        openai_api_key="",
    )
    starts: list[str] = []

    reply = feishu_bot.handle_incoming_text(
        config,
        "@_user_1 你是谁",
        FIXTURE_ALLOWED_CHAT,
        source="test",
        on_assistant_start=lambda: starts.append("started"),
    )

    assert starts == []
    assert reply == "GPT 助手还没配置 OPENAI_API_KEY，暂时不能回答。"


def main() -> None:
    test_codex_command()
    test_codex_command_is_found_with_launchd_system_path()
    test_feishu_client_adds_and_removes_typing_reaction_via_openapi()
    test_feishu_client_lists_only_its_own_typing_reactions()
    test_websocket_acknowledges_before_model_answer_and_poller_does_not_duplicate()
    test_websocket_model_exception_still_gets_an_explicit_final_reply()
    test_websocket_reaction_failure_falls_back_without_blocking_model()
    test_websocket_delete_failure_recovers_own_typing_reaction_by_listing()
    test_websocket_final_send_failure_still_removes_reaction_and_reports_failure()
    test_websocket_non_model_command_does_not_add_typing_reaction()
    test_websocket_ignored_message_does_not_add_typing_reaction()
    test_websocket_live_project_query_adds_typing_reaction_before_model()
    test_websocket_wrong_chat_does_not_add_typing_reaction()
    test_poller_takeover_uses_same_typing_reaction_lifecycle()
    test_poller_model_exception_sends_explicit_failure_and_removes_reaction()
    test_unconfigured_openai_reply_does_not_claim_gpt_is_thinking()


if __name__ == "__main__":
    main()
