#!/usr/bin/env python3
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from services import feishu_bot


PROJECT_CHAT = "project-chat"
FOREIGN_CHAT = "foreign-chat"
LOCAL_HOST = "host-one"


@pytest.fixture()
def branch_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    run_id = "branch-run"
    monkeypatch.setattr(feishu_bot, "RUNS_FILE", tmp_path / "feishu-runs.json")
    monkeypatch.setattr(
        feishu_bot,
        "CARD_CALLBACK_LOG_FILE",
        tmp_path / "feishu-card-callbacks.jsonl",
    )
    feishu_bot.write_json(
        feishu_bot.RUNS_FILE,
        {
            "runs": [
                {
                    "id": run_id,
                    "app_name": "DemoApp",
                    "chat_id": PROJECT_CHAT,
                    "project_chat_id": PROJECT_CHAT,
                    "submission_data": {"host_machine": LOCAL_HOST},
                    "events": [],
                }
            ]
        },
    )
    return run_id


def callback_payload(run_id: str, decision_id: str, branch: str) -> dict:
    return {
        "header": {"event_type": "card.action.trigger"},
        "event": {
            "operator": {"open_id": "operator-1"},
            "action": {
                "value": {
                    "action": "submission_code_branch_decision",
                    "decision": branch,
                    "decision_id": decision_id,
                    "run_id": run_id,
                }
            },
        },
    }


def test_code_branch_card_has_exact_choices_and_no_sensitive_context(
    branch_run: str,
) -> None:
    run = feishu_bot.create_or_update_code_branch_selection(branch_run)
    pending = run["pending_decision"]

    assert pending["kind"] == "code_branch"
    assert pending["status"] == "waiting"
    assert pending["allowed_branches"] == ["main", "dev", "release"]
    assert pending["decision_id"]
    assert pending["message_uuid"]

    card = feishu_bot.build_code_branch_card(run)
    elements = card["body"]["elements"]
    assert [element["text"]["content"] for element in elements[1:]] == [
        "main",
        "dev",
        "release",
    ]
    visible = "\n".join(
        element["text"]["content"] for element in elements if "text" in element
    )
    assert branch_run not in visible
    assert PROJECT_CHAT not in visible
    assert "http" not in visible
    assert "路径" not in visible


@pytest.mark.parametrize("branch", ("main", "dev", "release"))
def test_code_branch_callback_persists_once_and_unblocks_waiter(
    branch_run: str,
    branch: str,
) -> None:
    run = feishu_bot.create_or_update_code_branch_selection(branch_run)
    decision_id = run["pending_decision"]["decision_id"]
    payload = callback_payload(branch_run, decision_id, branch)

    first = feishu_bot.handle_card_action(
        payload,
        LOCAL_HOST,
        "report-only-chat",
        PROJECT_CHAT,
    )
    result_card = first["card"]["data"]
    result_button = result_card["body"]["elements"][1]
    assert result_button["text"]["content"] == f"已选择：{branch}"
    assert result_button["disabled"] is True
    assert "behaviors" not in result_button

    stored = feishu_bot.find_run(branch_run)
    assert stored is not None
    assert stored["status"] == f"decision_code_branch_{branch}"
    assert stored["pending_decision"]["status"] == "answered"
    assert stored["pending_decision"]["decision"] == branch
    assert stored["pending_decision"]["operator_id"] == "operator-1"
    answered_at = stored["pending_decision"]["answered_at"]

    duplicate = feishu_bot.handle_card_action(
        payload,
        LOCAL_HOST,
        "report-only-chat",
        PROJECT_CHAT,
    )
    duplicate_button = duplicate["card"]["data"]["body"]["elements"][1]
    assert duplicate_button["text"]["content"] == f"已选择：{branch}"
    stored_after_duplicate = feishu_bot.find_run(branch_run)
    assert stored_after_duplicate is not None
    assert stored_after_duplicate["pending_decision"]["answered_at"] == answered_at
    assert len(
        [
            event
            for event in stored_after_duplicate["events"]
            if event.get("status") == f"decision_code_branch_{branch}"
        ]
    ) == 1

    output = StringIO()
    with redirect_stdout(output):
        status = feishu_bot.wait_decision(
            SimpleNamespace(
                run_id=branch_run,
                decision_kind="code_branch",
                timeout_seconds=1,
                poll_seconds=0,
            ),
            object(),
        )
    assert status == 0
    assert output.getvalue().strip() == branch


@pytest.mark.parametrize(
    ("mutation", "toast"),
    (
        ({"decision": "feature"}, "参数无效"),
        ({"decision_id": "stale"}, "失效"),
        ({"operator": {}}, "参数无效"),
    ),
)
def test_code_branch_callback_rejects_invalid_or_stale_input(
    branch_run: str,
    mutation: dict[str, object],
    toast: str,
) -> None:
    run = feishu_bot.create_or_update_code_branch_selection(branch_run)
    payload = callback_payload(
        branch_run,
        run["pending_decision"]["decision_id"],
        "main",
    )
    if "operator" in mutation:
        payload["event"]["operator"] = mutation["operator"]
    else:
        payload["event"]["action"]["value"].update(mutation)

    response = feishu_bot.handle_card_action(
        payload,
        LOCAL_HOST,
        "report-only-chat",
        PROJECT_CHAT,
    )
    assert toast in response["toast"]["content"]
    stored = feishu_bot.find_run(branch_run)
    assert stored is not None
    assert stored["pending_decision"]["status"] == "waiting"


def test_code_branch_callback_rejects_foreign_host_or_project_chat(
    branch_run: str,
) -> None:
    run = feishu_bot.create_or_update_code_branch_selection(branch_run)
    payload = callback_payload(
        branch_run,
        run["pending_decision"]["decision_id"],
        "release",
    )

    for host, chat in (("foreign-host", PROJECT_CHAT), (LOCAL_HOST, "foreign-chat")):
        response = feishu_bot.handle_card_action(
            payload,
            host,
            "report-only-chat",
            chat,
        )
        assert "非本机卡片" in response["toast"]["content"]

    stored = feishu_bot.find_run(branch_run)
    assert stored is not None
    assert stored["pending_decision"]["status"] == "waiting"


def test_code_branch_atomic_update_revalidates_host_and_project_chat(
    branch_run: str,
) -> None:
    run = feishu_bot.create_or_update_code_branch_selection(branch_run)
    decision_id = run["pending_decision"]["decision_id"]

    with pytest.raises(ValueError, match="ownership changed"):
        feishu_bot.record_decision_by_run_id(
            branch_run,
            "main",
            "card_button",
            "operator-1",
            decision_id,
            expected_host_machine="foreign-host",
            expected_project_chat_id=PROJECT_CHAT,
        )
    with pytest.raises(ValueError, match="ownership changed"):
        feishu_bot.record_decision_by_run_id(
            branch_run,
            "main",
            "card_button",
            "operator-1",
            decision_id,
            expected_host_machine=LOCAL_HOST,
            expected_project_chat_id=FOREIGN_CHAT,
        )

    stored = feishu_bot.find_run(branch_run)
    assert stored is not None
    assert stored["pending_decision"]["status"] == "waiting"


def test_code_branch_selection_is_idempotent_but_does_not_overwrite_waiting_kind(
    branch_run: str,
) -> None:
    first = feishu_bot.create_or_update_code_branch_selection(branch_run)
    second = feishu_bot.create_or_update_code_branch_selection(branch_run)
    assert second["pending_decision"] == first["pending_decision"]

    def change_kind(item: dict) -> None:
        item["pending_decision"]["kind"] = "confirmation"

    feishu_bot.mutate_run(branch_run, change_kind)
    with pytest.raises(RuntimeError, match="Another decision card is already waiting"):
        feishu_bot.create_or_update_code_branch_selection(branch_run)


def test_code_branch_timeout_card_does_not_show_run_or_chat_identifiers(
    branch_run: str,
) -> None:
    feishu_bot.create_or_update_code_branch_selection(branch_run)

    def expire(item: dict) -> None:
        pending = item["pending_decision"]
        pending.update(
            {
                "status": "expired",
                "decision": "timeout",
                "timeout_seconds": 3600,
                "expired_at": "2026-08-28T01:00:00+00:00",
            }
        )

    run = feishu_bot.mutate_run(branch_run, expire)
    assert run is not None
    card = feishu_bot.build_code_branch_card(run)
    visible = card["body"]["elements"][0]["text"]["content"]

    assert branch_run not in visible
    assert PROJECT_CHAT not in visible
    assert "DemoApp" in visible
    assert LOCAL_HOST in visible
