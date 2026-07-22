#!/usr/bin/env python3
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.feishu_bot import (
    create_or_update_fault,
    notify_review_success,
    record_decision_by_run_id,
)


def main() -> None:
    run = {
        "id": "review-success-sending-fault-recovery",
        "app_name": "Xrimo",
        "chat_id": "test-chat",
        "submission_data": {"host_machine": "海淋"},
        "status": "waiting_review_submission_confirmation",
        "pending_decision": {
            "kind": "review_submit",
            "status": "waiting",
            "decision": "",
            "decision_id": "review-request-b",
            "app_version": "1.0",
            "build_number": "7",
            "iap_count": 14,
            "evidence": "REVIEW_SCREENSHOTS=verified_5;ITEMS_READY=15",
        },
        "events": [],
    }

    def find_run(run_id: str) -> dict:
        assert run_id == run["id"]
        return run

    def mutate_run(run_id: str, mutator) -> dict:
        assert run_id == run["id"]
        mutator(run)
        return run

    config = SimpleNamespace(submission_host_machine="海淋")
    args = SimpleNamespace(
        run_id=run["id"],
        app_review_status="Waiting for Review",
    )

    with (
        patch("services.feishu_bot.find_run", side_effect=find_run),
        patch("services.feishu_bot.mutate_run", side_effect=mutate_run),
    ):
        record_decision_by_run_id(
            run["id"], "submit_review", "card_button", "approver", "review-request-b"
        )
        assert run["review_submission_approval"]["status"] == "approved"
        approved_snapshot = dict(run["review_submission_approval"])

        with (
            patch("services.feishu_bot.FeishuClient.send_card", return_value={"data": {}}) as first_send,
            redirect_stderr(StringIO()),
        ):
            assert notify_review_success(args, config) == 2
        message_uuid = run["review_success"]["message_uuid"]
        assert message_uuid

        create_or_update_fault(
            run_id=run["id"],
            chat_id="test-chat",
            stage="utm-25:success-notification",
            fault="success notification result unclear",
            suggested_action="recover the same sending attempt",
            recovery_skill="utm-25",
        )
        record_decision_by_run_id(
            run["id"],
            "retry_skill",
            "card_button",
            "operator",
            run["pending_decision"]["decision_id"],
        )
        assert run["review_submission_approval"] == approved_snapshot

        with (
            patch(
                "services.feishu_bot.FeishuClient.send_card",
                return_value={"data": {"message_id": "om_success_recovered"}},
            ) as recovery_send,
            redirect_stdout(StringIO()),
        ):
            assert notify_review_success(args, config) == 0

    assert first_send.call_args.kwargs["message_uuid"] == message_uuid
    assert recovery_send.call_args.kwargs["message_uuid"] == message_uuid
    assert len(
        {
            first_send.call_args.kwargs["message_uuid"],
            recovery_send.call_args.kwargs["message_uuid"],
        }
    ) == 1
    assert run["review_success"]["status"] == "sent"
    assert run["review_success"]["message_uuid"] == message_uuid
    sent_content = recovery_send.call_args.args[1]["body"]["elements"][0]["text"]["content"]
    assert "**版本**：1.0" in sent_content
    assert "**构建号**：7" in sent_content
    assert "**提交内容**：iOS App + 14 项内购" in sent_content
    assert "**提交项目数**：15" in sent_content


if __name__ == "__main__":
    main()
