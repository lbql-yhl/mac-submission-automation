#!/usr/bin/env python3
"""Standalone optional skill: create in-app purchases for an already-ready guest app."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.clean_cli import run_clean_cli  # noqa: E402
from scripts.notion_api import api_from_env  # noqa: E402
from scripts.utm_direct_context import resolve_direct_context  # noqa: E402
from scripts.utm_iap_attempt import (  # noqa: E402
    AttemptResult,
    UTMIAPAttemptError,
    classify_attempt,
    create_attempt,
    inspect_remote,
    load_single_attempt,
    mark_attempt,
    precommit_remote,
    run_remote,
)
from services.feishu_bot import find_run, load_config, run_host_machine  # noqa: E402
from services.host_config import optional_setting  # noqa: E402


DEFAULT_ATTEMPTS_ROOT = PROJECT_ROOT / "runtime" / "utm-iap-attempts"
IAP_WAIT_SECONDS = 3600
IAP_POLL_SECONDS = 5


class UTMIAPError(RuntimeError):
    """Raised when the optional utm-iap host entry cannot complete safely."""


def _run_context(run_id: str, vm_name: str) -> tuple[str, str, str]:
    config = load_config()
    record = find_run(config, run_id)
    if record is None:
        raise UTMIAPError("RUN_NOT_FOUND")
    host = run_host_machine(record)
    if not host:
        raise UTMIAPError("RUN_HOST_MISSING")
    app_name = str(record.get("app_name") or "").strip()
    if not app_name:
        raise UTMIAPError("RUN_APP_MISSING")
    page_title = f"{app_name}-{vm_name}"
    return host, app_name, page_title


def _classify_with_rechecks(attempt: Any) -> AttemptResult:
    deadline = time.monotonic() + IAP_WAIT_SECONDS
    pending: AttemptResult | None = None
    while True:
        log, status, running = inspect_remote(attempt)
        result = classify_attempt(
            log,
            status,
            process_running=running,
            expected_attempt_id=attempt.attempt_id,
        )
        if result.state == "verified":
            return result
        if result.state == "blocked_business_error":
            return result
        if result.state == "verification_pending":
            pending = result
        if time.monotonic() >= deadline:
            return pending or result
        time.sleep(IAP_POLL_SECONDS)


def _attempt_failure_message(result: AttemptResult) -> str:
    message = f"IAP_CREATION_BLOCKED={result.state}:{result.mode}"
    if result.reason:
        message = f"{message};{result.reason}"
    return message


def run(args: argparse.Namespace) -> int:
    if args.vm_user != args.vm_name:
        raise UTMIAPError("VM_USER_MISMATCH")
    attempts_root = Path(args.attempts_root)
    supplied_run_id = getattr(args, "run_id", None)
    direct_mode = not supplied_run_id
    legacy_page = str(getattr(args, "page_title", "") or "").strip()
    check_notion_app = True
    if direct_mode:
        context = resolve_direct_context(
            parent_title=optional_setting("SUBMISSION_HOST_MACHINE"),
            page_title=legacy_page,
            vm_name=args.vm_name,
            vm_ip=args.vm_ip,
            vm_user=args.vm_user,
        )
        context_id = context.context_id
        parent_title, page_title, app_name = (
            context.parent_title,
            context.page_title,
            context.app_name,
        )
    else:
        context_id = str(supplied_run_id)
        parent_title, app_name, page_title = _run_context(context_id, args.vm_name)

    api = api_from_env()
    api.verify_parent(parent_title)
    if check_notion_app:
        notion_app = api.read_field(page_title, "应用信息", "应用名: ").strip()
        if notion_app != app_name:
            raise UTMIAPError("NOTION_PAGE_APP_MISMATCH")

    attempt = load_single_attempt(attempts_root, context_id)
    if attempt is not None:
        if (
            attempt.vm_name != args.vm_name
            or attempt.vm_ip != args.vm_ip
            or attempt.run_id != context_id
        ):
            raise UTMIAPError("ATTEMPT_CONTEXT_MISMATCH")
        if attempt.state == "verified":
            print("UTM_IAP_RESUME=verified")
            print("UTM_IAP=verified")
            return 0

    if attempt is None:
        attempt = create_attempt(
            attempts_root,
            run_id=context_id,
            vm_name=args.vm_name,
            vm_ip=args.vm_ip,
        )

    if attempt.state == "prepared":
        precommit_remote(attempt)
        print("UTM_IAP_LOG_PATH=precommitted")
        attempt = mark_attempt(attempt, state="precommitted")

    if attempt.state == "precommitted":
        attempt = mark_attempt(attempt, state="running")
        ssh_exit = run_remote(attempt)
        print(f"SSH_EXIT={ssh_exit}")

    if attempt.state not in {"running", "completion_observed"}:
        raise UTMIAPError(f"ATTEMPT_STATE_INVALID={attempt.state}")

    result = _classify_with_rechecks(attempt)
    if result.state != "verified" or result.product_count is None or result.product_count < 1:
        raise UTMIAPError(_attempt_failure_message(result))
    attempt = mark_attempt(attempt, state="verified", mode=result.mode)
    print("UTM_IAP_ATTEMPT_ID=verified")
    print("UTM_IAP_LOG=verified")
    print(f"SUMMARY_PRODUCT_COUNT={result.product_count}")
    print("IAP_CREATION=verified")
    if direct_mode:
        print("UTM_IAP_DIRECT_CONTEXT=verified")
    print("UTM_IAP=verified")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create in-app purchases for a guest app that already finished utm-script without IAP"
    )
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--run-id")
    selector.add_argument("--page-title")
    parser.add_argument("--vm-name", required=True)
    parser.add_argument("--vm-ip", required=True)
    parser.add_argument("--vm-user", required=True)
    parser.add_argument(
        "--attempts-root",
        type=Path,
        default=DEFAULT_ATTEMPTS_ROOT,
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    def operation() -> int:
        started_at = time.monotonic()
        status = run(args)
        print("utm-iap 内购步骤已完成")
        print(f"UTM_IAP_ELAPSED_SECONDS={round(time.monotonic() - started_at)}")
        return status

    return run_clean_cli(
        skill_name="utm-iap",
        success_marker="UTM_IAP=verified",
        operation=operation,
        preserve_error_detail=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
