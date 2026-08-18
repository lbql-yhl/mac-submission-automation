#!/usr/bin/env python3
import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.host_config import ConfigurationError  # noqa: E402
from scripts import vm_inventory_scan  # noqa: E402
from scripts.vm_inventory_scan import build_report, report_sha256  # noqa: E402


def test_report_starts_with_date_and_hash_is_stable() -> None:
    report = build_report(
        {
            "scan_at": "2026-07-29T08:00:00+00:00",
            "newly_reusable": ["abcd"],
            "unregistered": [{"vm_name": "efgh", "bundle_path": "/Volumes/AutoA/images/efgh.utm"}],
        }
    )
    assert report.splitlines()[0] == "2026-07-29"
    assert "未登记虚拟机：efgh" in report
    assert report_sha256(report) == hashlib.sha256(report.encode("utf-8")).hexdigest()


def test_send_report_requires_configured_daily_destination_before_send(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(vm_inventory_scan, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("FEISHU_DAILY_REPORT_CHAT_ID", raising=False)
    monkeypatch.setenv("FEISHU_APP_ID", "app-id")
    monkeypatch.setenv("FEISHU_APP_SECRET", "app-secret")
    monkeypatch.setattr(
        vm_inventory_scan,
        "send_text_message",
        lambda *_args: pytest.fail("delivery must not start without a destination"),
    )

    with pytest.raises(ConfigurationError) as captured:
        vm_inventory_scan._send_report("report", "digest", "digest")

    assert str(captured.value) == (
        "missing required host setting: FEISHU_DAILY_REPORT_CHAT_ID"
    )


def test_send_report_uses_configured_daily_destination(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sent: list[tuple[str, str, str, str]] = []
    monkeypatch.setattr(vm_inventory_scan, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("FEISHU_DAILY_REPORT_CHAT_ID", "configured-daily-chat")
    monkeypatch.setenv("FEISHU_APP_ID", "app-id")
    monkeypatch.setenv("FEISHU_APP_SECRET", "app-secret")
    monkeypatch.setattr(
        vm_inventory_scan,
        "send_text_message",
        lambda *args: sent.append(args),
    )

    vm_inventory_scan._send_report("report", "digest", "digest")

    assert sent == [
        ("app-id", "app-secret", "configured-daily-chat", "report")
    ]


if __name__ == "__main__":
    raise SystemExit(0)
