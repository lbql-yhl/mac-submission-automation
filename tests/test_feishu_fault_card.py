#!/usr/bin/env python3
from copy import deepcopy
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import feishu_bot as feishu_bot_module
from services.feishu_bot import (
    FeishuClient,
    build_fault_decision_card,
    create_or_update_fault,
    decision_deadline,
    ensure_decision_card_delivered,
    handle_card_action as _handle_card_action,
    notify_fault,
    record_decision_by_run_id,
    record_fault_notification,
    wait_decision,
)
from services.feishu_gateway import FeishuSendError, send_interactive_card


REPORT_ONLY_CHAT = "-".join(("daily", "report", "chat"))
FIXTURE_CHAT = "test-chat"
FIXTURE_WRONG_CHAT = "wrong-chat"
FIXTURE_APP_IDENTIFIER = "test-app-id"
FIXTURE_APP_CREDENTIAL = "test-app-secret"


def handle_card_action(
    payload: dict,
    submission_host_machine: str,
    allowed_chat_id: str = FIXTURE_CHAT,
) -> dict:
    return _handle_card_action(
        payload,
        submission_host_machine,
        REPORT_ONLY_CHAT,
        allowed_chat_id,
    )


@pytest.mark.parametrize(
    ("changed_field", "changed_value"),
    (
        ("submission_data", {"host_machine": "other-host"}),
        ("chat_id", "other-project-chat"),
        ("project_chat_id", "other-project-chat"),
    ),
)
def test_fault_callback_rechecks_ownership_inside_atomic_mutation(
    changed_field: str,
    changed_value: object,
) -> None:
    waiting_run = {
        "id": "fault-card-ownership-race",
        "app_name": "Ownership Race App",
        "chat_id": FIXTURE_CHAT,
        "project_chat_id": FIXTURE_CHAT,
        "submission_data": {"host_machine": "海淋"},
        "pending_decision": {
            "kind": "fault",
            "status": "waiting",
            "decision_id": "fault-race-decision",
            "stage": "callback-test",
            "recovery_skill": "utm-24",
        },
        "events": [],
    }
    changed_run = deepcopy(waiting_run)
    changed_run[changed_field] = changed_value
    payload = {
        "event": {
            "operator": {"open_id": "operator-1"},
            "action": {
                "value": {
                    "action": "submission_fault_decision",
                    "decision": "retry_skill",
                    "decision_id": "fault-race-decision",
                    "run_id": "fault-card-ownership-race",
                }
            },
        }
    }

    def mutate_after_binding_change(run_id: str, mutator) -> dict:
        assert run_id == "fault-card-ownership-race"
        mutator(changed_run)
        return changed_run

    with (
        patch("services.feishu_bot.find_run", return_value=waiting_run),
        patch(
            "services.feishu_bot.mutate_run",
            side_effect=mutate_after_binding_change,
        ),
        patch("services.feishu_bot.append_card_callback_log"),
    ):
        result = handle_card_action(payload, "海淋")

    assert result == {
        "toast": {"type": "warning", "content": "故障卡已失效或不匹配"}
    }
    assert changed_run["pending_decision"] == waiting_run["pending_decision"]
    assert changed_run["events"] == []
    assert "status" not in changed_run


def main() -> None:
    first_delivery_deadline = decision_deadline(
        {
            "requested_at": "2026-07-20T08:00:00+00:00",
            "first_notified_at": "2026-07-20T08:05:00+00:00",
            "last_notified_at": "2026-07-20T08:45:00+00:00",
        },
        3600,
        9999999999.0,
    )
    assert first_delivery_deadline == 1784538300.0

    run = {
        "id": "fault-card-test",
        "app_name": "Fault Card App",
        "chat_id": FIXTURE_CHAT,
        "project_chat_id": FIXTURE_CHAT,
        "submission_data": {"host_machine": "海淋"},
        "lifecycle": {
            "started_at": "2026-07-20T07:55:00+00:00",
            "start_message_uuid": "start-message-uuid",
            "start_message_id": "om_start",
        },
        "pending_decision": {
            "kind": "fault",
            "status": "waiting",
            "decision_id": "fault-decision-1",
            "stage": "test",
            "fault": "test fault",
            "retry_count": 0,
            "evidence": "test evidence",
            "suggested_action": "test action",
            "recovery_skill": "utm-24",
            "completed_steps": "截图已验证",
        },
    }
    card = build_fault_decision_card(run)

    assert card["schema"] == "2.0"
    elements = card["body"]["elements"]
    assert elements[0]["tag"] == "div"
    visible_fault_body = elements[0]["text"]["content"]
    assert visible_fault_body == (
        "**故障技能**：utm-24\n"
        "**技能故障步骤**：test\n"
        "**应用**：Fault Card App\n"
        "**宿主**：海淋"
    )
    assert len(visible_fault_body.splitlines()) == 4
    buttons = elements[1:]
    assert [button["text"]["content"] for button in buttons] == [
        "停止流程",
        "已人工处理，继续流程",
        "重试技能，跳过已处理成功的步骤",
    ]
    assert all(button["tag"] == "button" for button in buttons)
    assert all(button["behaviors"][0]["type"] == "callback" for button in buttons)
    assert buttons[0]["behaviors"][0]["value"] == {
        "action": "submission_fault_decision",
        "decision": "stop",
        "decision_id": "fault-decision-1",
        "run_id": "fault-card-test",
    }
    assert buttons[1]["behaviors"][0]["value"]["decision"] == "manual_continue"
    assert buttons[2]["behaviors"][0]["value"]["decision"] == "retry_skill"
    assert "action" not in elements[0]
    visible_card_text = json.dumps(
        {
            "header": card["header"],
            "texts": [element.get("text") for element in elements],
        },
        ensure_ascii=False,
    )
    for forbidden in (
        "fault-card-test",
        "fault-decision-1",
        "test fault",
        "test evidence",
        "截图已验证",
        "test action",
        "已重试次数",
        "自动恢复",
    ):
        assert forbidden not in visible_card_text

    injected_run = {
        **run,
        "app_name": "Fault Card App\u2028**故障原因**：hidden-app-detail",
        "submission_data": {"host_machine": "海淋\x00hidden-host-detail"},
        "pending_decision": {
            **run["pending_decision"],
            "recovery_skill": "utm-24\n**当前证据**：hidden-skill-detail",
            "stage": "test\rhidden-stage-detail",
        },
    }
    injected_body = build_fault_decision_card(injected_run)["body"]["elements"][0][
        "text"
    ]["content"]
    assert injected_body == (
        "**故障技能**：未填写\n"
        "**技能故障步骤**：未知\n"
        "**应用**：未知应用\n"
        "**宿主**：未知"
    )
    assert len(injected_body.splitlines()) == 4
    assert "hidden-" not in injected_body

    overlong_run = {
        **run,
        "app_name": "a" * 121,
    }
    overlong_body = build_fault_decision_card(overlong_run)["body"]["elements"][0][
        "text"
    ]["content"]
    assert overlong_body.splitlines()[2] == "**应用**：未知应用"

    answered = {
        **run,
        "pending_decision": {**run["pending_decision"], "status": "answered", "decision": "manual_continue"},
    }
    answered_elements = build_fault_decision_card(answered)["body"]["elements"]
    assert len(answered_elements) == 2
    assert answered_elements[0]["text"]["content"] == visible_fault_body
    assert answered_elements[1]["text"]["content"] == "已选择：已人工处理，继续流程"
    assert answered_elements[1]["disabled"] is True

    mutable_run = {**run, "pending_decision": dict(run["pending_decision"]), "events": []}

    def fake_mutate(run_id: str, mutate) -> dict:
        assert run_id == "fault-card-test"
        mutate(mutable_run)
        return mutable_run

    with patch("services.feishu_bot.mutate_run", side_effect=fake_mutate):
        retried = record_decision_by_run_id(
            "fault-card-test",
            "retry_skill",
            "card_button",
            "approver",
            "fault-decision-1",
        )
    assert retried is mutable_run
    assert mutable_run["status"] == "decision_retry_skill"
    assert mutable_run["pending_decision"]["decision"] == "retry_skill"

    retry_payload = {
        "event": {
            "operator": {"open_id": "approver"},
            "action": {
                "value": {
                    "action": "submission_fault_decision",
                    "decision": "retry_skill",
                    "decision_id": "fault-decision-1",
                    "run_id": "fault-card-test",
                }
            }
        }
    }
    waiting_run = {**run, "pending_decision": dict(run["pending_decision"])}
    for rejected_run in (
        {**waiting_run, "submission_data": {"host_machine": "dev1"}},
        {key: value for key, value in waiting_run.items() if key != "submission_data"},
        {**waiting_run, "chat_id": REPORT_ONLY_CHAT},
        {**waiting_run, "chat_id": ""},
        {**waiting_run, "chat_id": FIXTURE_WRONG_CHAT},
        {**waiting_run, "project_chat_id": FIXTURE_WRONG_CHAT},
        {key: value for key, value in waiting_run.items() if key != "project_chat_id"},
    ):
        with (
            patch("services.feishu_bot.find_run", return_value=rejected_run),
            patch("services.feishu_bot.record_decision_by_run_id") as rejected_record,
            patch("services.feishu_bot.append_card_callback_log"),
        ):
            rejected = handle_card_action(retry_payload, "海淋")
        assert "非本机卡片" in rejected["toast"]["content"]
        rejected_record.assert_not_called()

    missing_operator_payload = {
        **retry_payload,
        "event": {
            **retry_payload["event"],
            "operator": {},
        },
    }
    with (
        patch("services.feishu_bot.find_run") as forbidden_find,
        patch("services.feishu_bot.record_decision_by_run_id") as forbidden_record,
        patch("services.feishu_bot.append_card_callback_log"),
    ):
        rejected = handle_card_action(missing_operator_payload, "海淋")
    assert "操作人" in rejected["toast"]["content"]
    forbidden_find.assert_not_called()
    forbidden_record.assert_not_called()

    stale_payload = {
        **retry_payload,
        "event": {
            **retry_payload["event"],
            "action": {
                "value": {
                    **retry_payload["event"]["action"]["value"],
                    "decision_id": "old-fault-decision",
                }
            },
        },
    }
    with (
        patch("services.feishu_bot.find_run", return_value=waiting_run),
        patch("services.feishu_bot.record_decision_by_run_id") as stale_record,
        patch("services.feishu_bot.append_card_callback_log"),
    ):
        rejected = handle_card_action(stale_payload, "海淋")
    assert "已失效或不匹配" in rejected["toast"]["content"]
    stale_record.assert_not_called()

    with (
        patch("services.feishu_bot.find_run", return_value=waiting_run),
        patch("services.feishu_bot.record_decision_by_run_id", return_value=mutable_run) as record_local,
        patch("services.feishu_bot.append_card_callback_log"),
    ):
        result = handle_card_action(retry_payload, "海淋")
    record_local.assert_called_once_with(
        "fault-card-test",
        "retry_skill",
        "card_button",
        "approver",
        "fault-decision-1",
        expected_host_machine="海淋",
        expected_project_chat_id=FIXTURE_CHAT,
    )
    assert result["toast"]["content"] == "已收到重试指令，正在重试当前技能"
    assert result["card"]["data"]["header"]["title"]["content"] == "已收到重试指令，正在重试技能"

    args = SimpleNamespace(
        run_id="fault-card-test",
        timeout_seconds=10,
        poll_seconds=1,
    )
    stdout = StringIO()
    with (
        patch("services.feishu_bot.find_run", return_value=mutable_run),
        patch("services.feishu_bot.time.time", side_effect=[0, 0]),
        redirect_stdout(stdout),
    ):
        assert wait_decision(args, object()) == 0
    assert stdout.getvalue().strip() == "retry_skill"

    notify_args = SimpleNamespace(
        chat_id=FIXTURE_CHAT,
        run_id="fault-card-test",
        stage="test",
        fault="test fault",
        suggested_action="test action",
        failure_action="test failure",
        retry_count=0,
        completed_steps="",
        evidence="test evidence",
        recovery_skill="",
        recovery_attempts=0,
        recovery_actions="",
        recovery_result="",
        unrepairable=False,
    )
    config = SimpleNamespace(
        submission_host_machine="海淋",
        daily_report_chat_id=REPORT_ONLY_CHAT,
        allowed_chat_id=FIXTURE_CHAT,
    )
    with (
        patch(
            "services.feishu_bot.find_run",
            return_value={**run, "chat_id": FIXTURE_CHAT},
        ),
        patch("services.feishu_bot.create_or_update_fault", return_value=run) as create_fault,
        patch("services.feishu_bot.FeishuClient.send_card"),
        redirect_stderr(StringIO()),
    ):
        assert notify_fault(notify_args, config) == 2
    create_fault.assert_not_called()

    delivery_run = {
        **run,
        "chat_id": FIXTURE_CHAT,
        "pending_decision": {
            **run["pending_decision"],
            "requested_at": "2026-07-20T08:00:00+00:00",
            "message_uuid": "fault-card-test-message",
            "last_notified_at": "2026-07-20T08:01:00+00:00",
        },
        "events": [],
    }

    def delivery_mutate(run_id: str, mutate) -> dict:
        assert run_id == "fault-card-test"
        mutate(delivery_run)
        return delivery_run

    with (
        patch("services.feishu_bot.mutate_run", side_effect=delivery_mutate),
        patch(
            "services.feishu_bot.FeishuClient.send_card",
            return_value={"data": {"message_id": "om_first_delivery"}},
        ) as send_first,
        patch("services.feishu_bot.utc_now", return_value="2026-07-20T08:05:00+00:00"),
    ):
        delivered = ensure_decision_card_delivered(delivery_run, config)
    assert delivered["pending_decision"]["first_notified_at"] == "2026-07-20T08:05:00+00:00"
    assert delivered["pending_decision"]["last_message_id"] == "om_first_delivery"
    assert send_first.call_count == 1
    assert send_first.call_args.kwargs.get("message_uuid") == "fault-card-test-message"

    generation_run = {
        **delivery_run,
        "pending_decision": {
            **delivery_run["pending_decision"],
            "first_notified_at": "",
            "last_notified_at": "",
            "last_message_id": "",
        },
    }

    def generation_mutate(run_id: str, mutate) -> dict:
        assert run_id == "fault-card-test"
        mutate(generation_run)
        return generation_run

    with (
        patch("services.feishu_bot.mutate_run", side_effect=generation_mutate),
        patch("services.feishu_bot.utc_now", return_value="2026-07-20T08:06:00+00:00"),
    ):
        recorded = record_fault_notification(
            "fault-card-test",
            "om_generation",
            expected_message_uuid="fault-card-test-message",
            expected_decision_id="fault-decision-1",
        )
    assert recorded["pending_decision"]["last_message_id"] == "om_generation"
    assert recorded["pending_decision"]["first_notified_at"] == (
        "2026-07-20T08:06:00+00:00"
    )

    for wrong_uuid, wrong_decision_id in (
        ("wrong-message-generation", "fault-decision-1"),
        ("fault-card-test-message", "wrong-decision-generation"),
    ):
        conflict_run = {
            **generation_run,
            "pending_decision": {
                **generation_run["pending_decision"],
                "first_notified_at": "",
                "last_notified_at": "",
                "last_message_id": "",
            },
        }

        def conflict_mutate(run_id: str, mutate) -> dict:
            assert run_id == "fault-card-test"
            mutate(conflict_run)
            return conflict_run

        with patch("services.feishu_bot.mutate_run", side_effect=conflict_mutate):
            try:
                record_fault_notification(
                    "fault-card-test",
                    "om_must_not_persist",
                    expected_message_uuid=wrong_uuid,
                    expected_decision_id=wrong_decision_id,
                )
            except RuntimeError as exc:
                assert "generation" in str(exc).lower()
            else:
                raise AssertionError("fault delivery generation conflict was accepted")
        assert conflict_run["pending_decision"]["last_message_id"] == ""
        assert conflict_run["pending_decision"]["first_notified_at"] == ""

    valid_notify_args = SimpleNamespace(**vars(notify_args))
    valid_notify_args.recovery_skill = "utm-24"
    valid_notify_args.recovery_attempts = 3
    valid_notify_args.recovery_actions = "diagnose,repair,reverify"
    valid_notify_args.recovery_result = "exhausted"
    with (
        patch("services.feishu_bot.find_run", return_value=delivery_run),
        patch("services.feishu_bot.create_or_update_fault", return_value=delivery_run),
        patch("services.feishu_bot.FeishuClient.send_card") as duplicate_fault_send,
        redirect_stdout(StringIO()),
    ):
        assert notify_fault(valid_notify_args, config) == 0
    duplicate_fault_send.assert_not_called()

    legacy_delivered_run = {
        **delivery_run,
        "pending_decision": {
            **delivery_run["pending_decision"],
            "first_notified_at": "",
            "last_notified_at": "2026-07-20T08:01:00+00:00",
            "last_message_id": "om_legacy_delivery",
        },
    }
    with (
        patch("services.feishu_bot.find_run", return_value=legacy_delivered_run),
        patch("services.feishu_bot.create_or_update_fault", return_value=legacy_delivered_run),
        patch("services.feishu_bot.FeishuClient.send_card") as legacy_duplicate_send,
        redirect_stdout(StringIO()),
    ):
        assert notify_fault(valid_notify_args, config) == 0
    legacy_duplicate_send.assert_not_called()

    def legacy_delivery_mutate(run_id: str, mutate) -> dict:
        assert run_id == "fault-card-test"
        mutate(legacy_delivered_run)
        return legacy_delivered_run

    with (
        patch("services.feishu_bot.mutate_run", side_effect=legacy_delivery_mutate),
        patch("services.feishu_bot.FeishuClient.send_card") as legacy_wait_send,
    ):
        migrated_delivery = ensure_decision_card_delivered(legacy_delivered_run, config)
    assert migrated_delivery["pending_decision"]["first_notified_at"] == "2026-07-20T08:01:00+00:00"
    legacy_wait_send.assert_not_called()

    undelivered_run = {
        **delivery_run,
        "pending_decision": {
            **delivery_run["pending_decision"],
            "first_notified_at": "",
            "last_notified_at": "",
            "last_message_id": "",
        },
    }
    with (
        patch("services.feishu_bot.find_run", return_value=undelivered_run),
        patch("services.feishu_bot.create_or_update_fault", return_value=undelivered_run) as create_valid_fault,
        patch("services.feishu_bot.FeishuClient.send_card", return_value={"data": {}}),
        patch("services.feishu_bot.record_fault_notification") as record_missing_id,
        redirect_stderr(StringIO()),
    ):
        assert notify_fault(valid_notify_args, config) == 2
    assert create_valid_fault.call_args.kwargs["host_machine"] == "海淋"
    record_missing_id.assert_not_called()

    synthetic_chat = "synthetic-sensitive-chat-id"
    synthetic_message_id = "synthetic-sensitive-message-id"
    failed_delivery_check = {
        "status": "failed",
        "expected_chat_ids": [synthetic_chat],
        "missing_chat_ids": [synthetic_chat],
        "targets": [
            {
                "chat_id": synthetic_chat,
                "message_id": synthetic_message_id,
                "status": "failed",
            }
        ],
    }
    verification_config = SimpleNamespace(
        **vars(config),
        app_id=FIXTURE_APP_IDENTIFIER,
        app_secret=FIXTURE_APP_CREDENTIAL,
        send_retries=1,
        send_timeout_seconds=1,
        verify_delivery=True,
    )
    with (
        patch(
            "services.feishu_bot.send_interactive_card",
            return_value={"code": 0, "data": {"message_id": synthetic_message_id}},
        ),
        patch(
            "services.feishu_bot.verify_post_message_delivery",
            return_value=failed_delivery_check,
        ),
    ):
        try:
            FeishuClient(verification_config).send_card(
                FIXTURE_CHAT,
                {"schema": "2.0"},
                message_uuid="synthetic-message-uuid",
            )
        except RuntimeError as exc:
            if str(exc) != "Feishu card delivery verification failed":
                raise AssertionError(f"verification details leaked: {exc}") from exc
        else:
            raise AssertionError("failed delivery verification was accepted")

    delivery_stderr = StringIO()
    with (
        patch("services.feishu_bot.find_run", return_value=undelivered_run),
        patch("services.feishu_bot.create_or_update_fault", return_value=undelivered_run),
        patch(
            "services.feishu_bot.send_interactive_card",
            return_value={"code": 0, "data": {"message_id": synthetic_message_id}},
        ),
        patch(
            "services.feishu_bot.verify_post_message_delivery",
            return_value=failed_delivery_check,
        ),
        patch("services.feishu_bot.record_fault_notification") as leaked_record,
        redirect_stderr(delivery_stderr),
    ):
        assert notify_fault(valid_notify_args, verification_config) == 2
    assert delivery_stderr.getvalue().splitlines() == ["notify-fault card delivery failed"]
    assert synthetic_chat not in delivery_stderr.getvalue()
    assert synthetic_message_id not in delivery_stderr.getvalue()
    leaked_record.assert_not_called()

    for send_error in (
        FeishuSendError("synthetic send failure"),
        RuntimeError("synthetic verification failure"),
    ):
        generic_stderr = StringIO()
        with (
            patch("services.feishu_bot.find_run", return_value=undelivered_run),
            patch("services.feishu_bot.create_or_update_fault", return_value=undelivered_run),
            patch("services.feishu_bot.FeishuClient.send_card", side_effect=send_error),
            redirect_stderr(generic_stderr),
        ):
            assert notify_fault(valid_notify_args, verification_config) == 2
        assert generic_stderr.getvalue().splitlines() == [
            "notify-fault card delivery failed"
        ]
        assert "synthetic" not in generic_stderr.getvalue()

    for persistence_result in (None, RuntimeError("generation changed")):
        with (
            patch("services.feishu_bot.find_run", return_value=undelivered_run),
            patch("services.feishu_bot.create_or_update_fault", return_value=undelivered_run),
            patch(
                "services.feishu_bot.FeishuClient.send_card",
                return_value={"data": {"message_id": "om_unconfirmed"}},
            ),
            patch("services.feishu_bot.record_fault_notification") as persist,
            redirect_stderr(StringIO()),
        ):
            if isinstance(persistence_result, Exception):
                persist.side_effect = persistence_result
            else:
                persist.return_value = persistence_result
            assert notify_fault(valid_notify_args, config) == 2
        persist.assert_called_once_with(
            "fault-card-test",
            "om_unconfirmed",
            expected_message_uuid="fault-card-test-message",
            expected_decision_id="fault-decision-1",
        )

    # The shared fault-send boundary rejects foreign/missing ownership and any
    # non-original or daily-report chat before it creates/mutates a pending fault.
    boundary_cases = (
        ({**delivery_run, "submission_data": {"host_machine": "dev1"}}, valid_notify_args),
        (
            {key: value for key, value in delivery_run.items() if key != "submission_data"},
            valid_notify_args,
        ),
        (
            delivery_run,
            SimpleNamespace(
                **{**vars(valid_notify_args), "chat_id": FIXTURE_WRONG_CHAT}
            ),
        ),
        (delivery_run, SimpleNamespace(**{**vars(valid_notify_args), "chat_id": ""})),
        (
            {**delivery_run, "chat_id": REPORT_ONLY_CHAT},
            SimpleNamespace(**{**vars(valid_notify_args), "chat_id": REPORT_ONLY_CHAT}),
        ),
        (
            {key: value for key, value in delivery_run.items() if key != "project_chat_id"},
            valid_notify_args,
        ),
        (
            {**delivery_run, "project_chat_id": FIXTURE_WRONG_CHAT},
            valid_notify_args,
        ),
        (
            {key: value for key, value in delivery_run.items() if key != "lifecycle"},
            valid_notify_args,
        ),
        (
            {
                **delivery_run,
                "lifecycle": {
                    **delivery_run["lifecycle"],
                    "start_message_id": "",
                },
            },
            valid_notify_args,
        ),
    )
    for rejected_run, rejected_args in boundary_cases:
        with (
            patch("services.feishu_bot.find_run", return_value=rejected_run),
            patch("services.feishu_bot.create_or_update_fault") as rejected_create,
            patch("services.feishu_bot.mutate_run") as rejected_mutate,
            patch("services.feishu_bot.FeishuClient.send_card") as rejected_send,
            redirect_stderr(StringIO()),
        ):
            assert notify_fault(rejected_args, config) == 2
        rejected_create.assert_not_called()
        rejected_mutate.assert_not_called()
        rejected_send.assert_not_called()

    # Even direct pending-fault construction cannot replace the run's original
    # chat. notify_fault enforces equality before reaching this helper.
    original_chat_run = {
        **delivery_run,
        "chat_id": FIXTURE_CHAT,
        "pending_decision": {},
        "events": [],
    }

    def original_chat_mutate(run_id: str, mutate) -> dict:
        assert run_id == "fault-card-test"
        mutate(original_chat_run)
        return original_chat_run

    with (
        patch("services.feishu_bot.find_run", return_value=original_chat_run),
        patch("services.feishu_bot.mutate_run", side_effect=original_chat_mutate),
    ):
        create_or_update_fault(
            run_id="fault-card-test",
            chat_id=FIXTURE_WRONG_CHAT,
            stage="new-stage",
            fault="new fault",
            suggested_action="retry",
            recovery_skill="utm-24",
            host_machine="海淋",
        )
    assert original_chat_run["chat_id"] == FIXTURE_CHAT
    assert original_chat_run["pending_decision"]["decision_id"]

    race_run = {
        **run,
        "id": "fault-card-race",
        "pending_decision": {},
        "events": [],
    }
    with TemporaryDirectory() as temporary_directory:
        runs_file = Path(temporary_directory) / "feishu-runs.json"
        with patch.object(feishu_bot_module, "RUNS_FILE", runs_file):
            feishu_bot_module.write_json(runs_file, {"runs": [race_run]})
            unlocked_find = feishu_bot_module.find_run
            stale_read_barrier = Barrier(2)

            def synchronized_stale_find(run_id: str) -> dict | None:
                snapshot = unlocked_find(run_id)
                stale_read_barrier.wait(timeout=5)
                return snapshot

            def create_same_fault(_index: int) -> dict:
                return create_or_update_fault(
                    run_id="fault-card-race",
                    chat_id=FIXTURE_CHAT,
                    stage="same-stage",
                    fault="same fault",
                    suggested_action="retry",
                    recovery_skill="utm-24",
                    host_machine="海淋",
                )

            with patch(
                "services.feishu_bot.find_run",
                side_effect=synchronized_stale_find,
            ):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(create_same_fault, index) for index in range(2)]
                    concurrent_results = [future.result(timeout=5) for future in futures]

            stored_race = unlocked_find("fault-card-race")
    assert stored_race is not None
    generations = {
        (
            result["pending_decision"]["decision_id"],
            result["pending_decision"]["message_uuid"],
        )
        for result in concurrent_results
    }
    assert len(generations) == 1
    assert (
        stored_race["pending_decision"]["decision_id"],
        stored_race["pending_decision"]["message_uuid"],
    ) in generations
    assert len(
        [
            event
            for event in stored_race["events"]
            if event.get("status") == "waiting_user_decision"
        ]
    ) == 1

    waiting_fault = {
        **original_chat_run,
        "pending_decision": {
            **original_chat_run["pending_decision"],
            "status": "waiting",
            "stage": "new-stage",
            "fault": "new fault",
            "recovery_skill": "utm-24",
        },
    }

    def overlapping_fault_mutate(run_id: str, mutate) -> dict:
        assert run_id == "fault-card-test"
        mutate(waiting_fault)
        return waiting_fault

    with (
        patch("services.feishu_bot.find_run", return_value=waiting_fault),
        patch(
            "services.feishu_bot.mutate_run",
            side_effect=overlapping_fault_mutate,
        ) as overlapping_mutate,
    ):
        try:
            create_or_update_fault(
                run_id="fault-card-test",
                chat_id=FIXTURE_CHAT,
                stage="different-stage",
                fault="different fault",
                suggested_action="retry",
                recovery_skill="utm-24",
                host_machine="海淋",
            )
        except RuntimeError as exc:
            assert "Another decision card is already waiting" in str(exc)
        else:
            raise AssertionError("a waiting fault decision was overwritten")
    overlapping_mutate.assert_called_once()

    answered_fault = {
        **waiting_fault,
        "status": "decision_stop",
        "pending_decision": {
            **waiting_fault["pending_decision"],
            "status": "answered",
            "decision": "stop",
            "answered_at": "2026-07-20T08:10:00+00:00",
        },
    }
    answered_before = json.loads(json.dumps(answered_fault, ensure_ascii=False))

    def answered_mutate(run_id: str, mutate) -> dict:
        assert run_id == "fault-card-test"
        mutate(answered_fault)
        return answered_fault

    with (
        patch("services.feishu_bot.find_run", return_value=answered_fault),
        patch("services.feishu_bot.mutate_run", side_effect=answered_mutate),
    ):
        try:
            create_or_update_fault(
                run_id="fault-card-test",
                chat_id=FIXTURE_CHAT,
                stage="new-after-answer",
                fault="must not replace answer",
                suggested_action="retry",
                recovery_skill="utm-24",
                host_machine="海淋",
            )
        except RuntimeError as exc:
            assert "answered" in str(exc).lower()
        else:
            raise AssertionError("an answered fault decision was overwritten")
    assert answered_fault == answered_before

    with (
        patch("services.feishu_bot.find_run", return_value=answered_fault),
        patch("services.feishu_bot.mutate_run", side_effect=answered_mutate),
        patch("services.feishu_bot.FeishuClient.send_card") as answered_send,
        redirect_stderr(StringIO()),
    ):
        assert notify_fault(valid_notify_args, config) == 2
    answered_send.assert_not_called()
    assert answered_fault == answered_before

    timeout_run = {
        "id": "fault-card-timeout",
        "app_name": "Timeout App",
        "submission_data": {"host_machine": "海淋"},
        "chat_id": "timeout-chat",
        "project_chat_id": "timeout-chat",
        "status": "waiting_user_decision",
        "pending_decision": {
            "kind": "fault",
            "status": "waiting",
            "decision_id": "fault-timeout-decision",
            "stage": "utm-business:bank",
            "fault": "bank state unclear",
            "recovery_skill": "utm-business",
            "requested_at": "2026-07-20T08:00:00+00:00",
            "first_notified_at": "2026-07-20T08:00:00+00:00",
            "message_uuid": "fault-card-timeout-message",
        },
        "events": [],
    }

    def timeout_mutate(run_id: str, mutate) -> dict:
        assert run_id == "fault-card-timeout"
        mutate(timeout_run)
        return timeout_run

    timeout_args = SimpleNamespace(
        run_id="fault-card-timeout",
        timeout_seconds=0,
        poll_seconds=1,
        decision_kind="fault",
    )
    with (
        patch("services.feishu_bot.find_run", return_value=timeout_run),
        patch("services.feishu_bot.mutate_run", side_effect=timeout_mutate),
        patch(
            "services.feishu_bot.FeishuClient.send_card",
            return_value={"data": {"message_id": "om_fault_timeout"}},
        ) as send_timeout,
        patch("services.feishu_bot.utc_now", return_value="2026-07-20T09:00:00+00:00"),
        redirect_stderr(StringIO()),
    ):
        assert wait_decision(timeout_args, object()) == 3

    assert timeout_run["status"] == "decision_timeout_stop"
    assert timeout_run["pending_decision"]["status"] == "expired"
    assert timeout_run["pending_decision"]["decision"] == "timeout"
    assert timeout_run["pending_decision"]["timeout_seconds"] == 0
    assert timeout_run["pending_decision"]["timeout_notification_attempted_at"]
    assert timeout_run["pending_decision"]["timeout_message_id"] == "om_fault_timeout"
    assert send_timeout.call_count == 1
    assert (
        send_timeout.call_args.kwargs.get("message_uuid")
        == timeout_run["pending_decision"]["timeout_message_uuid"]
    )
    timeout_chat_id, timeout_card = send_timeout.call_args.args
    assert timeout_chat_id == "timeout-chat"
    assert timeout_card["header"]["title"]["content"] == "等待回复超时，流程已停止"
    assert timeout_card["body"]["elements"][0]["text"]["content"] == (
        "**故障技能**：utm-business\n"
        "**技能故障步骤**：utm-business:bank\n"
        "**应用**：Timeout App\n"
        "**宿主**：海淋"
    )
    assert "fault-card-timeout" not in json.dumps(timeout_card, ensure_ascii=False)
    assert "2026-07-20T08:00:00+00:00" not in json.dumps(
        timeout_card, ensure_ascii=False
    )
    assert all(element["tag"] != "button" for element in timeout_card["body"]["elements"])

    with (
        patch("services.feishu_bot.find_run", return_value=timeout_run),
        patch("services.feishu_bot.mutate_run", side_effect=timeout_mutate),
        patch("services.feishu_bot.FeishuClient.send_card") as duplicate_timeout,
        redirect_stderr(StringIO()),
    ):
        assert wait_decision(timeout_args, object()) == 3
    duplicate_timeout.assert_not_called()

    timeout_failure_run = {
        **timeout_run,
        "id": "fault-card-timeout-failure",
        "pending_decision": {
            **timeout_run["pending_decision"],
            "status": "waiting",
            "decision": "",
            "expired_at": "",
            "timeout_notification_attempted_at": "",
            "timeout_notified_at": "",
            "timeout_message_id": "",
        },
        "events": [],
    }

    deferred_failure_callbacks = []
    timeout_failure_mutation_count = 0

    def timeout_failure_mutate(run_id: str, mutate) -> dict:
        nonlocal timeout_failure_mutation_count
        assert run_id == "fault-card-timeout-failure"
        timeout_failure_mutation_count += 1
        if timeout_failure_mutation_count == 1:
            mutate(timeout_failure_run)
        else:
            deferred_failure_callbacks.append(mutate)
        return timeout_failure_run

    timeout_failure_args = SimpleNamespace(
        run_id="fault-card-timeout-failure",
        timeout_seconds=0,
        poll_seconds=1,
        decision_kind="fault",
    )
    with (
        patch("services.feishu_bot.find_run", return_value=timeout_failure_run),
        patch("services.feishu_bot.mutate_run", side_effect=timeout_failure_mutate),
        patch("services.feishu_bot.FeishuClient.send_card", side_effect=RuntimeError("send failed")),
        redirect_stderr(StringIO()),
    ):
        assert wait_decision(timeout_failure_args, object()) == 3
    assert len(deferred_failure_callbacks) == 1
    deferred_failure_callbacks[0](timeout_failure_run)
    assert timeout_failure_run["status"] == "decision_timeout_stop"
    assert timeout_failure_run["pending_decision"]["timeout_notification_attempted_at"]
    assert timeout_failure_run["pending_decision"]["timeout_notification_failed_at"]
    assert timeout_failure_run["events"][-1]["status"] == (
        "decision_timeout_notification_failed"
    )
    assert timeout_failure_run["events"][-1]["note"].endswith("RuntimeError")

    with (
        patch("services.feishu_bot.find_run", return_value=timeout_failure_run),
        patch("services.feishu_bot.mutate_run", side_effect=timeout_failure_mutate),
        patch("services.feishu_bot.FeishuClient.send_card") as retry_failed_timeout,
        redirect_stderr(StringIO()),
    ):
        assert wait_decision(timeout_failure_args, object()) == 3
    retry_failed_timeout.assert_not_called()

    late_payload = {
        "event": {
            "operator": {"open_id": "approver"},
            "action": {
                "value": {
                    "action": "submission_fault_decision",
                    "decision": "manual_continue",
                    "decision_id": "fault-timeout-decision",
                    "run_id": "fault-card-timeout",
                }
            }
        }
    }
    with (
        patch("services.feishu_bot.find_run", return_value=timeout_run),
        patch("services.feishu_bot.record_decision_by_run_id") as record_late,
        patch("services.feishu_bot.append_card_callback_log"),
    ):
        late_result = handle_card_action(late_payload, "海淋", "timeout-chat")
    record_late.assert_not_called()
    assert "超过一小时" in late_result["toast"]["content"]
    assert all(
        element["tag"] != "button"
        for element in late_result["card"]["data"]["body"]["elements"]
    )

    source = (Path(__file__).resolve().parents[1] / "services" / "feishu_bot.py").read_text(encoding="utf-8")
    assert "notify-stop" not in source
    assert "def notify_stop(" not in source
    assert "resend_fault_decision_if_due" not in source
    assert "FEISHU_DECISION_REMIND_SECONDS" not in source

    with (
        patch("services.feishu_gateway.network_precheck", return_value={"ok": True}),
        patch("services.feishu_gateway.get_tenant_access_token", return_value="token"),
        patch(
            "services.feishu_gateway.post_json",
            return_value={"code": 0, "data": {"message_id": "om_uuid"}},
        ) as post_uuid,
    ):
        send_interactive_card(
            "app-id",
            "app-secret",
            FIXTURE_CHAT,
            {"schema": "2.0"},
            message_uuid="fault-message-uuid",
        )
    assert post_uuid.call_args.args[1]["uuid"] == "fault-message-uuid"


if __name__ == "__main__":
    main()
