#!/usr/bin/env python3
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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


if __name__ == "__main__":
    raise SystemExit(0)
