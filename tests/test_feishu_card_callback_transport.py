#!/usr/bin/env python3
import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import feishu_bot as feishu_bot_module
from services.feishu_bot import (
    handle_card_action as _handle_card_action,
    handle_ws_card_action,
    normalize_ws_card_payload,
    wait_decision,
)


REPORT_ONLY_CHAT = "-".join(("daily", "report", "chat"))
PROJECT_CHAT = "test-chat"


def handle_card_action(payload: dict, submission_host_machine: str) -> dict:
    return _handle_card_action(
        payload,
        submission_host_machine,
        REPORT_ONLY_CHAT,
        PROJECT_CHAT,
    )


def serialized_callback_result(result: object) -> dict:
    if isinstance(result, dict):
        serialized = json.dumps(result, ensure_ascii=False)
    else:
        from lark_oapi import JSON as LarkJSON

        serialized = LarkJSON.marshal(result)
    assert serialized
    return json.loads(serialized)


@pytest.mark.parametrize(
    ("decision", "transport", "selected_text", "run_status", "wait_status"),
    (
        ("stop", "ws_json_value", "已选择：停止流程", "decision_stop", 2),
        (
            "manual_continue",
            "http_dict_value",
            "已选择：已人工处理，继续流程",
            "decision_manual_continue",
            0,
        ),
        (
            "retry_skill",
            "http_json_value",
            "已选择：重试技能，跳过已处理成功的步骤",
            "decision_retry_skill",
            0,
        ),
    ),
)
def test_fault_callback_persists_answered_card_and_unblocks_waiter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    decision: str,
    transport: str,
    selected_text: str,
    run_status: str,
    wait_status: int,
) -> None:
    run_id = f"callback-lifecycle-{decision}"
    decision_id = f"decision-{decision}"
    runs_file = tmp_path / "feishu-runs.json"
    callback_log_file = tmp_path / "feishu-card-callbacks.jsonl"
    monkeypatch.setattr(feishu_bot_module, "RUNS_FILE", runs_file)
    monkeypatch.setattr(
        feishu_bot_module,
        "CARD_CALLBACK_LOG_FILE",
        callback_log_file,
    )
    feishu_bot_module.write_json(
        runs_file,
        {
            "runs": [
                {
                    "id": run_id,
                    "app_name": "Callback Lifecycle App",
                    "chat_id": PROJECT_CHAT,
                    "project_chat_id": PROJECT_CHAT,
                    "submission_data": {"host_machine": "海淋"},
                    "pending_decision": {
                        "kind": "fault",
                        "status": "waiting",
                        "decision_id": decision_id,
                        "stage": "callback-test",
                        "recovery_skill": "utm-24",
                    },
                    "events": [],
                }
            ]
        },
    )
    value = {
        "action": "submission_fault_decision",
        "decision": decision,
        "decision_id": decision_id,
        "run_id": run_id,
    }

    def dispatch() -> dict:
        if transport == "ws_json_value":
            ws_event = SimpleNamespace(
                event=SimpleNamespace(
                    operator=SimpleNamespace(open_id="operator-1", user_id=""),
                    action=SimpleNamespace(value=json.dumps(value, ensure_ascii=False)),
                )
            )
            result = handle_ws_card_action(
                ws_event,
                "海淋",
                REPORT_ONLY_CHAT,
                PROJECT_CHAT,
            )
        else:
            action_value = (
                value
                if transport == "http_dict_value"
                else json.dumps(value, ensure_ascii=False)
            )
            result = _handle_card_action(
                {
                    "header": {"event_type": "card.action.trigger"},
                    "event": {
                        "operator": {"open_id": "operator-1"},
                        "action": {"value": action_value},
                    },
                },
                "海淋",
                REPORT_ONLY_CHAT,
                PROJECT_CHAT,
            )
        return serialized_callback_result(result)

    first_response = dispatch()
    replacement = first_response["card"]["data"]
    elements = replacement["body"]["elements"]
    assert len(elements) == 2
    assert elements[1]["tag"] == "button"
    assert elements[1]["text"]["content"] == selected_text
    assert elements[1]["disabled"] is True
    assert "behaviors" not in elements[1]

    stored = feishu_bot_module.find_run(run_id)
    assert stored is not None
    assert stored["status"] == run_status
    assert stored["pending_decision"]["status"] == "answered"
    assert stored["pending_decision"]["decision"] == decision
    assert stored["pending_decision"]["operator_id"] == "operator-1"
    decision_events = [
        event for event in stored["events"] if event.get("status") == run_status
    ]
    assert len(decision_events) == 1
    answered_at = stored["pending_decision"]["answered_at"]

    duplicate_response = dispatch()
    duplicate_elements = duplicate_response["card"]["data"]["body"]["elements"]
    assert duplicate_elements[1]["text"]["content"] == selected_text
    assert duplicate_elements[1]["disabled"] is True
    assert "behaviors" not in duplicate_elements[1]
    stored_after_duplicate = feishu_bot_module.find_run(run_id)
    assert stored_after_duplicate is not None
    assert stored_after_duplicate["pending_decision"]["answered_at"] == answered_at
    assert len(
        [
            event
            for event in stored_after_duplicate["events"]
            if event.get("status") == run_status
        ]
    ) == 1

    callback_log = [
        json.loads(line)
        for line in callback_log_file.read_text(encoding="utf-8").splitlines()
    ]
    assert len(callback_log) == 2
    assert callback_log[0]["result"] == {
        "ok": True,
        "run_id": run_id,
        "decision": decision,
    }
    assert callback_log[1]["result"] == {
        "ok": True,
        "duplicate": True,
        "run_id": run_id,
    }

    output = StringIO()
    with redirect_stdout(output):
        status = wait_decision(
            SimpleNamespace(run_id=run_id, timeout_seconds=1, poll_seconds=0),
            object(),
        )
    assert status == wait_status
    assert output.getvalue().strip() == decision


def main() -> None:
    run = {
        "id": "transport-test",
        "chat_id": PROJECT_CHAT,
        "project_chat_id": PROJECT_CHAT,
        "submission_data": {"host_machine": "海淋"},
        "pending_decision": {
            "kind": "fault",
            "status": "waiting",
            "decision_id": "decision-1",
            "stage": "utm-vm-clone",
            "fault": "test fault",
            "suggested_action": "continue",
            "failure_action": "stop",
            "evidence": "transport-test",
            "recovery_skill": "utm-vm-clone",
        },
    }
    # Some long-connection deliveries encode action.value as a JSON string,
    # while the SDK P2 model only accepts a dict. The raw transport adapter
    # must normalize it before invoking the business callback.
    payload = {
        "schema": "2.0",
        "header": {"event_type": "card.action.trigger"},
        "event": {
            "operator": {"open_id": "operator-1"},
            "action": {
                "value": json.dumps(
                    {
                        "action": "submission_fault_decision",
                        "decision": "manual_continue",
                        "decision_id": "decision-1",
                        "run_id": "transport-test",
                    }
                )
            },
        },
    }
    answered = {
        **run,
        "pending_decision": {
            **run["pending_decision"],
            "status": "answered",
            "decision": "manual_continue",
        },
    }
    with (
        patch("services.feishu_bot.find_run", return_value=run),
        patch("services.feishu_bot.record_decision_by_run_id", return_value=answered),
        patch("services.feishu_bot.append_card_callback_log"),
    ):
        normalized = normalize_ws_card_payload(json.dumps(payload))
        result = handle_card_action(normalized, "海淋")

    assert result["toast"]["content"] == "已收到人工处理结果，正在继续流程"

    legacy_without_generation = {
        **run,
        "pending_decision": {
            key: value
            for key, value in run["pending_decision"].items()
            if key != "decision_id"
        },
    }
    legacy_payload = {
        "event": {
            "operator": {"open_id": "operator-1"},
            "action": {
                "value": {
                    "action": "submission_fault_decision",
                    "decision": "manual_continue",
                    "run_id": "transport-test",
                }
            },
        }
    }
    with (
        patch("services.feishu_bot.find_run", return_value=legacy_without_generation),
        patch(
            "services.feishu_bot.record_decision_by_run_id",
            return_value=answered,
        ) as legacy_record,
        patch("services.feishu_bot.append_card_callback_log"),
    ):
        legacy_result = handle_card_action(legacy_payload, "海淋")
    assert "参数无效" in legacy_result["toast"]["content"]
    legacy_record.assert_not_called()

    # Fault, confirmation, and review callbacks all share the exact same
    # configured-project-chat and persisted-binding authorization boundary.
    callback_shapes = (
        ("fault", "submission_fault_decision", "manual_continue"),
        ("confirmation", "submission_confirmation_decision", "confirm_continue"),
        ("review_submit", "submission_review_decision", "submit_review"),
    )
    for kind, action, decision in callback_shapes:
        foreign = {
            **run,
            "project_chat_id": "foreign-project-chat",
            "pending_decision": {
                **run["pending_decision"],
                "kind": kind,
            },
        }
        foreign_payload = {
            "event": {
                "operator": {"open_id": "operator-1"},
                "action": {
                    "value": {
                        "action": action,
                        "decision": decision,
                        "decision_id": "decision-1",
                        "run_id": "transport-test",
                    }
                },
            }
        }
        with (
            patch("services.feishu_bot.find_run", return_value=foreign),
            patch("services.feishu_bot.record_decision_by_run_id") as record,
            patch("services.feishu_bot.append_card_callback_log"),
        ):
            rejected = handle_card_action(foreign_payload, "海淋")
        assert "非本机卡片" in rejected["toast"]["content"]
        record.assert_not_called()


if __name__ == "__main__":
    main()
