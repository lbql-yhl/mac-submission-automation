#!/usr/bin/env python3
"""Build and optionally deliver an explicit user-provided Feishu daily report."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.feishu_gateway import (  # noqa: E402
    FeishuSendError,
    message_id_from_response,
    send_text_message,
    verify_post_message_delivery,
)
from services.host_config import (  # noqa: E402
    ConfigurationError,
    host_settings_snapshot,
)

PAYLOAD_FIELDS = frozenset({"prepared_apps", "review_items"})
REVIEW_FIELDS = frozenset({"app", "status", "days"})
REVIEW_STATUSES = frozenset({"过审", "待审", "审核中"})


class DailyReportError(RuntimeError):
    """Raised when explicit report input or delivery approval is invalid."""


def shanghai_date() -> date:
    """Return the current calendar date in the report's fixed timezone."""
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def _app_name(value: object, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise DailyReportError(f"{field} must be a nonempty string")
    if "\n" in value or "\r" in value:
        raise DailyReportError(f"{field} must fit on one line")
    return value.strip()


def _validated_rows(
    payload: dict[str, Any],
) -> tuple[list[str], list[tuple[str, str, int]]]:
    if type(payload) is not dict:
        raise DailyReportError("payload must be a JSON object")
    if set(payload) != PAYLOAD_FIELDS:
        raise DailyReportError(
            "payload must contain only prepared_apps and review_items"
        )

    prepared_values = payload["prepared_apps"]
    review_values = payload["review_items"]
    if type(prepared_values) is not list:
        raise DailyReportError("prepared_apps must be a JSON array")
    if type(review_values) is not list:
        raise DailyReportError("review_items must be a JSON array")

    prepared_apps: list[str] = []
    prepared_seen: set[str] = set()
    for index, value in enumerate(prepared_values):
        app = _app_name(value, f"prepared_apps[{index}]")
        if app in prepared_seen:
            raise DailyReportError("prepared_apps must not contain duplicates")
        prepared_seen.add(app)
        prepared_apps.append(app)

    review_items: list[tuple[str, str, int]] = []
    review_seen: set[str] = set()
    for index, value in enumerate(review_values):
        if type(value) is not dict or set(value) != REVIEW_FIELDS:
            raise DailyReportError(
                f"review_items[{index}] must contain only app, status and days"
            )
        app = _app_name(value["app"], f"review_items[{index}].app")
        status = value["status"]
        days = value["days"]
        if type(status) is not str or status not in REVIEW_STATUSES:
            raise DailyReportError(
                f"review_items[{index}].status must be 过审, 待审 or 审核中"
            )
        if type(days) is not int or days < 0:
            raise DailyReportError(
                f"review_items[{index}].days must be a nonnegative integer"
            )
        if app in review_seen:
            raise DailyReportError("review_items must not contain duplicate apps")
        review_seen.add(app)
        review_items.append((app, status, days))

    if not prepared_apps and not review_items:
        raise DailyReportError("at least one user-provided report row is required")
    return prepared_apps, review_items


def build_daily_report(payload: dict[str, Any], report_date: date | None = None) -> str:
    """Render the exact daily report from validated user-provided business rows."""
    prepared_apps, review_items = _validated_rows(payload)
    selected_date = shanghai_date() if report_date is None else report_date
    if type(selected_date) is not date:
        raise DailyReportError("report_date must be a date")

    lines = [f"日期：{selected_date.isoformat()}", "今天提审准备："]
    lines.extend(prepared_apps)
    lines.append("查审情况：")
    lines.extend(f"{app}  {status} {days}天" for app, status, days in review_items)
    return "\n".join(lines) + "\n"


def report_sha256(report: str) -> str:
    return hashlib.sha256(report.encode("utf-8")).hexdigest()


def _required_setting(settings: Mapping[str, str], name: str) -> str:
    value = str(settings.get(name, "")).strip()
    if not value:
        raise ConfigurationError(f"missing required host setting: {name}")
    return value


def send_daily_report(
    payload: dict[str, Any],
    *,
    approval_sha256: str | None,
    user_confirmed: bool,
    report_date: date | None = None,
    environ: Mapping[str, str] | None = None,
    env_path: Path | None = None,
) -> str:
    """Deliver one approved report to the configured project-group route."""
    report = build_daily_report(payload, report_date=report_date)
    digest = report_sha256(report)
    if user_confirmed is not True:
        raise DailyReportError("refusing Feishu delivery: --user-confirmed is required")
    if type(approval_sha256) is not str or approval_sha256 != digest:
        raise DailyReportError(
            "refusing Feishu delivery: --approval-sha256 must exactly match "
            "the preview REPORT_SHA256"
        )

    if env_path is not None:
        settings_path: Path | None = Path(env_path)
    elif environ is None:
        settings_path = ROOT / ".env"
    else:
        settings_path = None
    settings = host_settings_snapshot(environ=environ, env_path=settings_path)
    app_id = _required_setting(settings, "FEISHU_APP_ID")
    app_secret = _required_setting(settings, "FEISHU_APP_SECRET")
    project_chat_id = _required_setting(settings, "FEISHU_ALLOWED_CHAT_ID")

    response = send_text_message(app_id, app_secret, project_chat_id, report)
    if not message_id_from_response(response).strip():
        raise DailyReportError("Feishu delivery response has no message ID")
    verification = verify_post_message_delivery([project_chat_id], response)
    if verification.get("status") != "checked":
        raise DailyReportError("Feishu delivery verification was not checked")
    return report


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DailyReportError("duplicate JSON object fields are not allowed")
        result[key] = value
    return result


def _load_stdin_payload() -> dict[str, Any]:
    try:
        payload = json.load(sys.stdin, object_pairs_hook=_strict_json_object)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise DailyReportError("stdin must contain one valid JSON payload") from error
    if type(payload) is not dict:
        raise DailyReportError("payload must be a JSON object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview or deliver an explicit user-provided Feishu daily report"
    )
    parser.add_argument("--send-feishu", action="store_true")
    parser.add_argument(
        "--approval-sha256",
        help="exact REPORT_SHA256 copied from the reviewed preview",
    )
    parser.add_argument(
        "--user-confirmed",
        action="store_true",
        help="assert that the user confirmed the exact rendered preview",
    )
    args = parser.parse_args(argv)

    try:
        if not args.send_feishu and (
            args.approval_sha256 is not None or args.user_confirmed
        ):
            raise DailyReportError(
                "approval options may only be used with --send-feishu"
            )
        payload = _load_stdin_payload()
        selected_date = shanghai_date()
        report = build_daily_report(payload, report_date=selected_date)
        digest = report_sha256(report)
        if args.send_feishu:
            send_daily_report(
                payload,
                approval_sha256=args.approval_sha256,
                user_confirmed=args.user_confirmed,
                report_date=selected_date,
            )
            marker = "REPORT_FEISHU=verified"
        else:
            marker = "REPORT_PREVIEW_ONLY=verified"
        print(report, end="")
        print(f"REPORT_SHA256={digest}")
        print(marker)
        return 0
    except DailyReportError as error:
        print(f"DAILY_REPORT=failed reason={error}", file=sys.stderr)
    except ConfigurationError as error:
        print(f"DAILY_REPORT=failed reason={error}", file=sys.stderr)
    except FeishuSendError:
        print("DAILY_REPORT=failed reason=Feishu delivery failed", file=sys.stderr)
    except OSError:
        print("DAILY_REPORT=failed reason=local input failed", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
