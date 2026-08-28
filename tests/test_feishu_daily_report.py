#!/usr/bin/env python3
import hashlib
import io
import json
import sys
from datetime import date
from pathlib import Path
from types import MappingProxyType

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import feishu_daily_report  # noqa: E402


def _payload() -> dict[str, object]:
    return {
        "prepared_apps": ["AppA"],
        "review_items": [
            {"app": "AppB", "status": "审核中", "days": 3},
            {"app": "AppC", "status": "过审", "days": 1},
        ],
    }


def _report() -> str:
    return feishu_daily_report.build_daily_report(
        _payload(), report_date=date(2026, 8, 26)
    )


def _digest() -> str:
    return hashlib.sha256(_report().encode("utf-8")).hexdigest()


def test_report_uses_only_explicit_user_fields() -> None:
    assert _report() == (
        "日期：2026-08-26\n"
        "今天提审准备：\n"
        "AppA\n"
        "查审情况：\n"
        "AppB  审核中 3天\n"
        "AppC  过审 1天\n"
    )


def test_both_headings_are_generated_when_prepared_section_is_empty() -> None:
    report = feishu_daily_report.build_daily_report(
        {
            "prepared_apps": [],
            "review_items": [{"app": "ReviewOnly", "status": "待审", "days": 0}],
        },
        report_date=date(2026, 8, 27),
    )

    assert report == (
        "日期：2026-08-27\n" "今天提审准备：\n" "查审情况：\n" "ReviewOnly  待审 0天\n"
    )


def test_both_headings_are_generated_when_review_section_is_empty() -> None:
    report = feishu_daily_report.build_daily_report(
        {"prepared_apps": ["PreparedOnly"], "review_items": []},
        report_date=date(2026, 8, 28),
    )

    assert report == (
        "日期：2026-08-28\n" "今天提审准备：\n" "PreparedOnly\n" "查审情况：\n"
    )


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"prepared_apps": []},
        {"review_items": []},
        {"prepared_apps": ["AppA"], "review_items": [], "extra": "forbidden"},
        {"prepared_apps": "AppA", "review_items": []},
        {"prepared_apps": [], "review_items": {}},
        {"prepared_apps": [""], "review_items": []},
        {"prepared_apps": ["   "], "review_items": []},
        {"prepared_apps": [False], "review_items": []},
        {"prepared_apps": ["AppA\nInjected"], "review_items": []},
        {
            "prepared_apps": [],
            "review_items": [{"app": "", "status": "待审", "days": 1}],
        },
        {
            "prepared_apps": [],
            "review_items": [{"app": "AppA", "status": "未知", "days": 1}],
        },
        {
            "prepared_apps": [],
            "review_items": [{"app": "AppA", "status": "待审", "days": -1}],
        },
        {
            "prepared_apps": [],
            "review_items": [{"app": "AppA", "status": "待审", "days": True}],
        },
        {
            "prepared_apps": [],
            "review_items": [{"app": "AppA", "status": "待审", "days": 1.0}],
        },
        {
            "prepared_apps": [],
            "review_items": [
                {"app": "AppA", "status": "待审", "days": 1, "extra": "forbidden"}
            ],
        },
        {"prepared_apps": ["AppA", "AppA"], "review_items": []},
        {
            "prepared_apps": [],
            "review_items": [
                {"app": "AppA", "status": "待审", "days": 1},
                {"app": "AppA", "status": "过审", "days": 2},
            ],
        },
    ],
)
def test_invalid_payloads_are_rejected(payload: object) -> None:
    with pytest.raises(feishu_daily_report.DailyReportError):
        feishu_daily_report.build_daily_report(
            payload,  # type: ignore[arg-type]
            report_date=date(2026, 8, 26),
        )


def test_empty_business_rows_cannot_build_or_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        feishu_daily_report,
        "host_settings_snapshot",
        lambda **_kwargs: pytest.fail("empty input must fail before config access"),
    )
    empty = {"prepared_apps": [], "review_items": []}

    with pytest.raises(feishu_daily_report.DailyReportError):
        feishu_daily_report.build_daily_report(empty, report_date=date(2026, 8, 26))
    with pytest.raises(feishu_daily_report.DailyReportError):
        feishu_daily_report.send_daily_report(
            empty,
            approval_sha256="0" * 64,
            user_confirmed=True,
            report_date=date(2026, 8, 26),
        )


@pytest.mark.parametrize(
    ("approval_sha256", "user_confirmed"),
    [
        (None, True),
        ("", True),
        ("wrong", True),
        ("DIGEST", True),
        ("valid-digest-is-replaced-below", False),
        ("valid-digest-is-replaced-below", 1),
    ],
)
def test_confirmation_and_hash_gates_run_before_config_access(
    approval_sha256: str | None,
    user_confirmed: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        feishu_daily_report,
        "host_settings_snapshot",
        lambda **_kwargs: pytest.fail("approval gates must fail before config access"),
    )
    if approval_sha256 == "valid-digest-is-replaced-below":
        approval_sha256 = _digest()

    with pytest.raises(feishu_daily_report.DailyReportError):
        feishu_daily_report.send_daily_report(
            _payload(),
            approval_sha256=approval_sha256,
            user_confirmed=user_confirmed,  # type: ignore[arg-type]
            report_date=date(2026, 8, 26),
        )


def test_send_uses_project_route_and_ignores_legacy_daily_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot_calls = 0
    sent: list[tuple[str, str, str, str]] = []
    verified: list[tuple[list[str], dict[str, object]]] = []
    response: dict[str, object] = {
        "code": 0,
        "data": {"message_id": "sensitive-message-id"},
    }

    def snapshot(**_kwargs: object) -> MappingProxyType[str, str]:
        nonlocal snapshot_calls
        snapshot_calls += 1
        return MappingProxyType(
            {
                "FEISHU_APP_ID": "sensitive-app-id",
                "FEISHU_APP_SECRET": "sensitive-app-secret",
                "FEISHU_DAILY_REPORT_CHAT_ID": "sensitive-daily-chat",
                "FEISHU_ALLOWED_CHAT_ID": "sensitive-project-chat",
            }
        )

    def send(*args: str) -> dict[str, object]:
        sent.append(args)
        return response

    def verify(
        expected_chat_ids: list[str], send_response: dict[str, object]
    ) -> dict[str, str]:
        verified.append((expected_chat_ids, send_response))
        return {"status": "checked"}

    monkeypatch.setattr(feishu_daily_report, "host_settings_snapshot", snapshot)
    monkeypatch.setattr(feishu_daily_report, "send_text_message", send)
    monkeypatch.setattr(feishu_daily_report, "verify_post_message_delivery", verify)

    returned = feishu_daily_report.send_daily_report(
        _payload(),
        approval_sha256=_digest(),
        user_confirmed=True,
        report_date=date(2026, 8, 26),
        environ={},
    )

    assert returned == _report()
    assert snapshot_calls == 1
    assert sent == [
        (
            "sensitive-app-id",
            "sensitive-app-secret",
            "sensitive-project-chat",
            _report(),
        )
    ]
    assert verified == [(["sensitive-project-chat"], response)]


@pytest.mark.parametrize("project_chat_id", (None, "   "))
def test_send_requires_project_route_before_network(
    project_chat_id: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = {
        "FEISHU_APP_ID": "app-id",
        "FEISHU_APP_SECRET": "app-secret",
        "FEISHU_DAILY_REPORT_CHAT_ID": "legacy-daily-chat",
    }
    if project_chat_id is not None:
        settings["FEISHU_ALLOWED_CHAT_ID"] = project_chat_id
    monkeypatch.setattr(
        feishu_daily_report,
        "host_settings_snapshot",
        lambda **_kwargs: MappingProxyType(settings),
    )
    monkeypatch.setattr(
        feishu_daily_report,
        "send_text_message",
        lambda *_args: pytest.fail("missing project route must fail before network"),
    )

    with pytest.raises(feishu_daily_report.ConfigurationError) as captured:
        feishu_daily_report.send_daily_report(
            _payload(),
            approval_sha256=_digest(),
            user_confirmed=True,
            report_date=date(2026, 8, 26),
            environ={},
        )

    assert str(captured.value) == (
        "missing required host setting: FEISHU_ALLOWED_CHAT_ID"
    )


def test_matching_legacy_daily_route_does_not_block_project_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        feishu_daily_report,
        "host_settings_snapshot",
        lambda **_kwargs: MappingProxyType(
            {
                "FEISHU_APP_ID": "sensitive-app-id",
                "FEISHU_APP_SECRET": "sensitive-app-secret",
                "FEISHU_DAILY_REPORT_CHAT_ID": "same-sensitive-chat",
                "FEISHU_ALLOWED_CHAT_ID": "same-sensitive-chat",
            }
        ),
    )
    monkeypatch.setattr(
        feishu_daily_report,
        "send_text_message",
        lambda *args: sent.append(args)
        or {"code": 0, "data": {"message_id": "synthetic-message"}},
    )
    monkeypatch.setattr(
        feishu_daily_report,
        "verify_post_message_delivery",
        lambda *_args: {"status": "checked"},
    )

    returned = feishu_daily_report.send_daily_report(
        _payload(),
        approval_sha256=_digest(),
        user_confirmed=True,
        report_date=date(2026, 8, 26),
        environ={},
    )

    assert returned == _report()
    assert sent == [
        (
            "sensitive-app-id",
            "sensitive-app-secret",
            "same-sensitive-chat",
            _report(),
        )
    ]


@pytest.mark.parametrize(
    "response",
    [
        {"code": 0, "data": {}},
        {"code": 0, "data": {"message_id": ""}},
        None,
    ],
)
def test_nonempty_message_id_is_required(
    response: dict[str, object] | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        feishu_daily_report,
        "host_settings_snapshot",
        lambda **_kwargs: MappingProxyType(
            {
                "FEISHU_APP_ID": "app-id",
                "FEISHU_APP_SECRET": "app-secret",
                "FEISHU_DAILY_REPORT_CHAT_ID": "daily-chat",
                "FEISHU_ALLOWED_CHAT_ID": "project-chat",
            }
        ),
    )
    monkeypatch.setattr(
        feishu_daily_report, "send_text_message", lambda *_args: response
    )
    monkeypatch.setattr(
        feishu_daily_report,
        "verify_post_message_delivery",
        lambda *_args: pytest.fail("missing message ID must fail before verification"),
    )

    with pytest.raises(feishu_daily_report.DailyReportError):
        feishu_daily_report.send_daily_report(
            _payload(),
            approval_sha256=_digest(),
            user_confirmed=True,
            report_date=date(2026, 8, 26),
            environ={},
        )


def test_delivery_verification_must_be_checked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        feishu_daily_report,
        "host_settings_snapshot",
        lambda **_kwargs: MappingProxyType(
            {
                "FEISHU_APP_ID": "app-id",
                "FEISHU_APP_SECRET": "app-secret",
                "FEISHU_DAILY_REPORT_CHAT_ID": "daily-chat",
                "FEISHU_ALLOWED_CHAT_ID": "project-chat",
            }
        ),
    )
    monkeypatch.setattr(
        feishu_daily_report,
        "send_text_message",
        lambda *_args: {"code": 0, "data": {"message_id": "sensitive-message"}},
    )
    monkeypatch.setattr(
        feishu_daily_report,
        "verify_post_message_delivery",
        lambda *_args: {
            "status": "failed",
            "message_id": "sensitive-message",
            "chat_id": "sensitive-chat",
        },
    )

    with pytest.raises(feishu_daily_report.DailyReportError) as captured:
        feishu_daily_report.send_daily_report(
            _payload(),
            approval_sha256=_digest(),
            user_confirmed=True,
            report_date=date(2026, 8, 26),
            environ={},
        )

    assert "sensitive-message" not in str(captured.value)
    assert "sensitive-chat" not in str(captured.value)


def test_preview_cli_prints_only_report_digest_and_redacted_marker(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_payload())))
    monkeypatch.setattr(
        feishu_daily_report,
        "shanghai_date",
        lambda: date(2026, 8, 26),
    )
    monkeypatch.setattr(
        feishu_daily_report,
        "host_settings_snapshot",
        lambda **_kwargs: pytest.fail("preview must not access config"),
    )

    assert feishu_daily_report.main([]) == 0

    assert capsys.readouterr().out == (
        _report() + f"REPORT_SHA256={_digest()}\n" + "REPORT_PREVIEW_ONLY=verified\n"
    )


@pytest.mark.parametrize(
    "raw_payload",
    [
        ('{"prepared_apps":["AppA"],"prepared_apps":["AppB"],' '"review_items":[]}'),
        (
            '{"prepared_apps":[],"review_items":['
            '{"app":"AppA","app":"AppB","status":"待审","days":1}]}'
        ),
    ],
)
def test_cli_rejects_ambiguous_duplicate_json_fields(
    raw_payload: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw_payload))
    monkeypatch.setattr(
        feishu_daily_report,
        "host_settings_snapshot",
        lambda **_kwargs: pytest.fail("invalid JSON must fail before config access"),
    )

    assert feishu_daily_report.main([]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "duplicate" in captured.err


def test_send_cli_does_not_print_sensitive_ids(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_payload())))
    monkeypatch.setattr(
        feishu_daily_report,
        "shanghai_date",
        lambda: date(2026, 8, 26),
    )
    monkeypatch.setattr(
        feishu_daily_report,
        "host_settings_snapshot",
        lambda **_kwargs: MappingProxyType(
            {
                "FEISHU_APP_ID": "sensitive-app-id",
                "FEISHU_APP_SECRET": "sensitive-app-secret",
                "FEISHU_DAILY_REPORT_CHAT_ID": "sensitive-daily-chat",
                "FEISHU_ALLOWED_CHAT_ID": "sensitive-project-chat",
            }
        ),
    )
    monkeypatch.setattr(
        feishu_daily_report,
        "send_text_message",
        lambda *_args: {
            "code": 0,
            "data": {"message_id": "sensitive-message-id"},
        },
    )
    monkeypatch.setattr(
        feishu_daily_report,
        "verify_post_message_delivery",
        lambda *_args: {
            "status": "checked",
            "message_id": "sensitive-message-id",
            "chat_id": "sensitive-daily-chat",
        },
    )

    assert (
        feishu_daily_report.main(
            [
                "--send-feishu",
                "--approval-sha256",
                _digest(),
                "--user-confirmed",
            ]
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == (
        _report() + f"REPORT_SHA256={_digest()}\n" + "REPORT_FEISHU=verified\n"
    )
    assert "sensitive" not in captured.out


if __name__ == "__main__":
    raise SystemExit(0)
