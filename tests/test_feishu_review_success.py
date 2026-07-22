#!/usr/bin/env python3
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.feishu_bot import build_review_success_card, notify_review_success


def main() -> None:
    run = {
        "id": "review-success-test",
        "app_name": "Xrimo",
        "chat_id": "test-chat",
        "submission_data": {"host_machine": "海淋"},
        "status": "decision_submit_review",
        "pending_decision": {
            "kind": "review_submit",
            "status": "answered",
            "decision": "submit_review",
            "decision_id": "review-request-legacy",
            "app_version": "1.0",
            "build_number": "7",
            "iap_count": 14,
            "evidence": "REVIEW_SCREENSHOTS=verified_5;ITEMS_READY=15",
            "answered_at": "2026-07-17T07:59:00+00:00",
            "operator_id": "approver",
        },
        "events": [],
    }
    completed_at = "2026-07-17T08:00:00+00:00"
    card = build_review_success_card(run, "Waiting for Review", completed_at)
    assert card["schema"] == "2.0"
    assert card["header"]["template"] == "green"
    assert card["header"]["title"]["content"] == "提审提交成功"
    elements = card["body"]["elements"]
    assert all(element["tag"] != "button" for element in elements)
    assert all("behaviors" not in element for element in elements)
    content = elements[0]["text"]["content"]
    for value in (
        "**应用**：Xrimo",
        "**版本**：1.0",
        "**构建号**：7",
        "**提交内容**：iOS App + 14 项内购",
        "**提交项目数**：15",
        "**App Store 状态**：Waiting for Review",
        f"**完成时间**：{completed_at}",
        "**运行**：review-success-test",
    ):
        assert value in content, value

    # Once an explicit snapshot exists it is authoritative for card metadata;
    # a rejected snapshot cannot fall back to stale legacy pending values.
    rejected_card_run = {
        **run,
        "review_submission_approval": {
            "kind": "review_submit",
            "status": "rejected",
            "decision": "do_not_submit",
            "decision_id": "review-request-rejected",
            "app_version": "2.0",
            "build_number": "8",
            "iap_count": 14,
            "evidence": "REVIEW_SCREENSHOTS=verified_5;ITEMS_READY=15",
            "answered_at": completed_at,
            "operator_id": "approver",
        },
    }
    rejected_card_content = build_review_success_card(
        rejected_card_run, "Waiting for Review", completed_at
    )["body"]["elements"][0]["text"]["content"]
    assert "**版本**：未知" in rejected_card_content
    assert "**构建号**：未知" in rejected_card_content
    assert "**提交内容**：iOS App + 0 项内购" in rejected_card_content
    assert "**版本**：1.0" not in rejected_card_content
    assert "**版本**：2.0" not in rejected_card_content

    args = SimpleNamespace(
        run_id="review-success-test",
        chat_id="test-chat",
        app_review_status="Waiting for Review",
    )
    config = SimpleNamespace(submission_host_machine="海淋")
    # Legacy migration is permitted only from the current answered review card.
    # A waiting card or a fault pending record cannot be interpreted as approval,
    # even when stale fields happen to contain submit_review and complete metadata.
    for invalid_pending in (
        {**run["pending_decision"], "status": "waiting"},
        {**run["pending_decision"], "kind": "fault", "status": "answered"},
    ):
        invalid = {**run, "pending_decision": invalid_pending}
        with (
            patch("services.feishu_bot.find_run", return_value=invalid),
            patch("services.feishu_bot.mutate_run") as invalid_legacy_mutate,
            patch("services.feishu_bot.FeishuClient.send_card") as invalid_legacy_send,
            redirect_stderr(StringIO()),
        ):
            assert notify_review_success(args, config) == 2
        invalid_legacy_mutate.assert_not_called()
        invalid_legacy_send.assert_not_called()

    # The authorization must be revalidated inside the atomic transition to
    # review_success=sending. A newer do_not_submit that wins the race cannot
    # be followed by a success-card send based on the stale pre-read approval.
    approved_snapshot = {
        "kind": "review_submit",
        "status": "approved",
        "decision": "submit_review",
        "decision_id": "review-request-race-approved",
        "app_version": "1.0",
        "build_number": "7",
        "iap_count": 14,
        "evidence": "REVIEW_SCREENSHOTS=verified_5;ITEMS_READY=15",
        "answered_at": completed_at,
        "operator_id": "approver",
    }
    stale_approved_run = {
        **run,
        "review_submission_approval": dict(approved_snapshot),
        "events": [],
    }
    race_current_run = {
        **stale_approved_run,
        "review_submission_approval": dict(approved_snapshot),
        "events": [],
    }

    def race_mutate(run_id: str, mutate) -> dict:
        assert run_id == "review-success-test"
        race_current_run["review_submission_approval"] = {
            **approved_snapshot,
            "status": "rejected",
            "decision": "do_not_submit",
            "decision_id": "review-request-race-rejected",
        }
        mutate(race_current_run)
        return race_current_run

    with (
        patch("services.feishu_bot.find_run", return_value=stale_approved_run),
        patch("services.feishu_bot.mutate_run", side_effect=race_mutate),
        patch("services.feishu_bot.FeishuClient.send_card") as race_send,
        redirect_stderr(StringIO()),
    ):
        assert notify_review_success(args, config) == 2
    race_send.assert_not_called()
    assert "review_success" not in race_current_run

    mutable_run = {**run, "pending_decision": dict(run["pending_decision"]), "events": []}

    def fake_mutate(run_id: str, mutate) -> dict:
        assert run_id == "review-success-test"
        mutate(mutable_run)
        return mutable_run

    # A response-loss/unknown-delivery result must leave one durable sending
    # attempt. A recovery invocation reuses that attempt's stable UUID.
    first_stderr = StringIO()
    with (
        patch("services.feishu_bot.find_run", return_value=mutable_run),
        patch("services.feishu_bot.FeishuClient.send_card", return_value={"data": {}}) as first_send,
        patch("services.feishu_bot.mutate_run", side_effect=fake_mutate),
        patch("services.feishu_bot.utc_now", return_value=completed_at),
        redirect_stderr(first_stderr),
    ):
        assert notify_review_success(args, config) == 2
    assert mutable_run["review_success"]["status"] == "sending"
    assert mutable_run["review_submission_approval"] == {
        "kind": "review_submit",
        "status": "approved",
        "decision": "submit_review",
        "decision_id": "review-request-legacy",
        "app_version": "1.0",
        "build_number": "7",
        "iap_count": 14,
        "evidence": "REVIEW_SCREENSHOTS=verified_5;ITEMS_READY=15",
        "answered_at": "2026-07-17T07:59:00+00:00",
        "operator_id": "approver",
    }
    assert mutable_run["review_success"]["app_review_status"] == "Waiting for Review"
    message_uuid = mutable_run["review_success"]["message_uuid"]
    assert message_uuid
    assert first_send.call_args.kwargs["message_uuid"] == message_uuid

    stdout = StringIO()
    with (
        patch("services.feishu_bot.find_run", return_value=mutable_run),
        patch(
            "services.feishu_bot.FeishuClient.send_card",
            return_value={"data": {"message_id": "om_review_success"}},
        ) as recovery_send,
        patch("services.feishu_bot.mutate_run", side_effect=fake_mutate),
        patch("services.feishu_bot.utc_now", return_value=completed_at),
        redirect_stdout(stdout),
    ):
        assert notify_review_success(args, config) == 0
    assert stdout.getvalue().strip() == "review-success-test"
    assert recovery_send.call_count == 1
    assert recovery_send.call_args.args[0] == "test-chat"
    assert recovery_send.call_args.kwargs["message_uuid"] == message_uuid
    sent_card = recovery_send.call_args.args[1]
    assert all(element["tag"] != "button" for element in sent_card["body"]["elements"])
    assert mutable_run["review_success"] == {
        "status": "sent",
        "app_review_status": "Waiting for Review",
        "completed_at": completed_at,
        "message_id": "om_review_success",
        "message_uuid": message_uuid,
    }

    stdout = StringIO()
    args_without_chat = SimpleNamespace(
        run_id="review-success-test",
        app_review_status="Waiting for Review",
    )
    with (
        patch("services.feishu_bot.find_run", return_value=mutable_run),
        patch("services.feishu_bot.FeishuClient.send_card") as duplicate_send,
        redirect_stdout(stdout),
    ):
        assert notify_review_success(args_without_chat, config) == 0
    assert stdout.getvalue().strip() == "review-success-test"
    duplicate_send.assert_not_called()

    # A legacy/malformed sent marker is not an idempotency proof.
    for incomplete in (
        {
            **mutable_run,
            "review_success": {
                **mutable_run["review_success"],
                "app_review_status": "15 Items Submitted",
            },
        },
        {
            **mutable_run,
            "review_success": {**mutable_run["review_success"], "message_id": ""},
        },
    ):
        with (
            patch("services.feishu_bot.find_run", return_value=incomplete),
            patch("services.feishu_bot.mutate_run") as rejected_mutate,
            patch("services.feishu_bot.FeishuClient.send_card") as rejected_send,
            redirect_stderr(StringIO()),
        ):
            assert notify_review_success(args, config) == 2
        rejected_mutate.assert_not_called()
        rejected_send.assert_not_called()

    # An explicit current snapshot is authoritative. Rejected or structurally
    # incomplete snapshots must not fall back to a legacy answered pending card.
    for invalid_approval in (
        {
            "kind": "review_submit",
            "status": "rejected",
            "decision": "do_not_submit",
            "decision_id": "review-request-2",
            "app_version": "1.0",
            "build_number": "7",
            "iap_count": 14,
            "answered_at": completed_at,
            "operator_id": "approver",
        },
        {
            "kind": "review_submit",
            "status": "approved",
            "decision": "submit_review",
            "decision_id": "",
            "app_version": "1.0",
            "build_number": "7",
            "iap_count": 14,
            "answered_at": completed_at,
            "operator_id": "approver",
        },
        {
            "kind": "review_submit",
            "status": "approved",
            "decision": "submit_review",
            "decision_id": "review-request-malformed-iap",
            "app_version": "1.0",
            "build_number": "7",
            "iap_count": "fourteen",
            "evidence": "REVIEW_SCREENSHOTS=verified_5;ITEMS_READY=15",
            "answered_at": completed_at,
            "operator_id": "approver",
        },
        {
            "kind": "review_submit",
            "status": "approved",
            "decision": "submit_review",
            "decision_id": "review-request-bad-evidence",
            "app_version": "1.0",
            "build_number": "7",
            "iap_count": 14,
            "evidence": "NOT_REVIEW_SCREENSHOTS=verified_5;ITEMS_READY=150",
            "answered_at": completed_at,
            "operator_id": "approver",
        },
    ):
        invalid_snapshot_run = {
            **run,
            "pending_decision": dict(run["pending_decision"]),
            "review_submission_approval": invalid_approval,
        }
        with (
            patch("services.feishu_bot.find_run", return_value=invalid_snapshot_run),
            patch("services.feishu_bot.mutate_run") as invalid_snapshot_mutate,
            patch("services.feishu_bot.FeishuClient.send_card") as invalid_snapshot_send,
            redirect_stderr(StringIO()),
        ):
            assert notify_review_success(args, config) == 2
        invalid_snapshot_mutate.assert_not_called()
        invalid_snapshot_send.assert_not_called()

    # Host and original-chat ownership are checked before any mutation/send.
    boundary_cases = (
        ({**run, "submission_data": {"host_machine": "dev1"}}, args, config),
        ({key: value for key, value in run.items() if key != "submission_data"}, args, config),
        (run, SimpleNamespace(**{**vars(args), "chat_id": "wrong-chat"}), config),
        ({**run, "chat_id": "oc_7e0ab0f30306c580726cd38bdcdff31c"},
         SimpleNamespace(**{**vars(args), "chat_id": "oc_7e0ab0f30306c580726cd38bdcdff31c"}),
         config),
    )
    for rejected_run, rejected_args, rejected_config in boundary_cases:
        with (
            patch("services.feishu_bot.find_run", return_value=rejected_run),
            patch("services.feishu_bot.mutate_run") as rejected_mutate,
            patch("services.feishu_bot.FeishuClient.send_card") as rejected_send,
            redirect_stderr(StringIO()),
        ):
            assert notify_review_success(rejected_args, rejected_config) == 2
        rejected_mutate.assert_not_called()
        rejected_send.assert_not_called()


if __name__ == "__main__":
    main()
