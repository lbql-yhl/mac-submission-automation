#!/usr/bin/env python3
import hashlib
import importlib
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def vm_inventory_scan() -> ModuleType:
    return importlib.import_module("scripts.vm_inventory_scan")


def test_import_does_not_read_host_dotenv() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import services.host_config as host_config
host_config._dotenv_setting = lambda *_args, **_kwargs: (_ for _ in ()).throw(
    AssertionError('inventory scan import must not read host .env')
)
import scripts.vm_inventory_scan
print('IMPORT_OK')
""",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "IMPORT_OK"


def test_report_starts_with_date_and_hash_is_stable(
    vm_inventory_scan: ModuleType,
) -> None:
    report = vm_inventory_scan.build_report(
        {
            "scan_at": "2026-07-29T08:00:00+00:00",
            "newly_reusable": ["abcd"],
            "unregistered": [{"vm_name": "efgh", "bundle_path": "/Volumes/AutoA/images/efgh.utm"}],
        }
    )
    assert report.splitlines()[0] == "2026-07-29"
    assert "未登记虚拟机：efgh" in report
    assert vm_inventory_scan.report_sha256(report) == hashlib.sha256(
        report.encode("utf-8")
    ).hexdigest()


def test_inventory_cli_rejects_feishu_send_before_scan(
    vm_inventory_scan: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        vm_inventory_scan,
        "scan_inventory",
        lambda *_args: pytest.fail("delivery flags must fail before inventory access"),
    )

    assert vm_inventory_scan.main(["--send-feishu"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "scripts/feishu_daily_report.py" in captured.err


def test_inventory_cli_rejects_approval_hash_before_scan(
    vm_inventory_scan: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        vm_inventory_scan,
        "scan_inventory",
        lambda *_args: pytest.fail("delivery flags must fail before inventory access"),
    )

    assert vm_inventory_scan.main(["--approval-sha256=unused"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "scripts/feishu_daily_report.py" in captured.err


def test_inventory_module_has_no_feishu_delivery_dependencies(
    vm_inventory_scan: ModuleType,
) -> None:
    assert not hasattr(vm_inventory_scan, "_send_report")
    assert not hasattr(vm_inventory_scan, "send_text_message")
    assert not hasattr(vm_inventory_scan, "host_settings_snapshot")


if __name__ == "__main__":
    raise SystemExit(0)
