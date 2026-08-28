#!/usr/bin/env python3
"""Daily reconciliation/preview for the standalone UTM VM inventory.

The scan is deliberately separate from cloning.  It only compares the local
SQLite inventory with the configured image directory; unknown bundles are
reported for human review and are never inserted automatically.  Inventory
evidence is local-only and cannot be delivered as a Feishu daily report.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.vm_inventory import InventoryError, register_existing, scan_inventory  # noqa: E402


VM_NAME_RE = re.compile(r"^[a-z]{4}$")


def _date_from_scan(scan_at: str) -> str:
    try:
        return datetime.fromisoformat(scan_at.replace("Z", "+00:00")).date().isoformat()
    except (TypeError, ValueError):
        return str(scan_at)[:10]


def build_report(result: dict[str, Any]) -> str:
    """Render a deterministic, date-first report from local scan evidence."""
    scan_at = str(result.get("scan_at", ""))
    reusable = sorted(str(name) for name in result.get("newly_reusable", []))
    master_paths = sorted(str(path) for path in result.get("master_paths", []))
    unregistered = sorted(
        (dict(item) for item in result.get("unregistered", [])),
        key=lambda item: (str(item.get("vm_name", "")), str(item.get("bundle_path", ""))),
    )
    lines = [
        _date_from_scan(scan_at),
        "UTM 虚拟机目录每日整理报告",
        f"扫描时间：{scan_at}",
        f"数据库登记数量：{int(result.get('registered_count', 0))}",
        f"目录虚拟机数量：{int(result.get('directory_count', 0))}",
        f"master模板数量：{len(master_paths)}",
        "",
    ]
    if master_paths:
        lines.append(f"master模板：{', '.join(master_paths)}")
    lines.extend(["", "本次新发现已清理、名称可复用："])
    lines.extend(f"- {name}" for name in reusable) if reusable else lines.append("- 无")
    lines.extend(["", "目录存在但数据库未登记（需人工检查；可用标记固定为 0）："])
    if unregistered:
        lines.extend(
            f"- 未登记虚拟机：{item.get('vm_name', '')}（路径：{item.get('bundle_path', '')}）"
            for item in unregistered
        )
    else:
        lines.append("- 无")
    return "\n".join(lines) + "\n"


def report_sha256(report: str) -> str:
    return hashlib.sha256(report.encode("utf-8")).hexdigest()


def _bundle_created_at(bundle: Path) -> str:
    stat_result = bundle.stat()
    timestamp = getattr(stat_result, "st_birthtime", stat_result.st_ctime)
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="seconds")


def _register_confirmed_bundles(
    database: Path,
    images_dir: Path,
    names: list[str],
    application_name: str,
) -> list[str]:
    """Register only explicitly approved existing bundles; never discover-and-add."""
    if not names:
        return []
    from scripts.utm_clone_macos import read_identity

    registered: list[str] = []
    for name in names:
        if not VM_NAME_RE.fullmatch(name):
            raise InventoryError(f"invalid confirmed VM name: {name}")
        bundle = images_dir / f"{name}.utm"
        config = bundle / "config.plist"
        if not bundle.is_dir() or bundle.is_symlink() or not config.is_file() or config.is_symlink():
            raise InventoryError(f"confirmed VM bundle/config is missing or unsafe: {bundle}")
        identity = read_identity(config)
        register_existing(
            database,
            name,
            identity["uuid"],
            bundle,
            identity["mac"],
            identity["machine_identifier_sha256"],
            application_name,
            vm_created_at=_bundle_created_at(bundle),
            available=False,
        )
        registered.append(name)
        print(
            f"REGISTERED_EXISTING_VM={name} APPLICATION_NAME={application_name} "
            "AVAILABLE=0"
        )
    return registered


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    delivery_options = ("--send-feishu", "--approval-sha256")
    if any(
        argument == option or argument.startswith(f"{option}=")
        for argument in raw_argv
        for option in delivery_options
    ):
        print(
            "VM_INVENTORY_SCAN=failed reason=Feishu delivery is disabled; "
            "use scripts/feishu_daily_report.py with explicit user-provided JSON",
            file=sys.stderr,
        )
        return 2

    parser = argparse.ArgumentParser(description="Scan and report the standalone UTM VM inventory")
    parser.add_argument("--images-dir", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument(
        "--register-existing",
        nargs="+",
        metavar="VM_NAME",
        help="register only these manually confirmed existing four-letter VM bundles",
    )
    parser.add_argument(
        "--application-name",
        default="test",
        help="application label for --register-existing (only literal 'test' may repeat)",
    )
    args = parser.parse_args(raw_argv)

    try:
        if args.images_dir is None or args.database is None:
            from services.project_paths import PROJECT_ROOT, VM_IMAGES_DIR

            images_dir = args.images_dir or VM_IMAGES_DIR
            database = args.database or PROJECT_ROOT / "runtime" / "vm-inventory.sqlite3"
        else:
            images_dir = args.images_dir
            database = args.database
        images_dir = images_dir.expanduser()
        if images_dir.is_symlink():
            raise InventoryError("images directory must be an existing non-symlink directory")
        images_dir = images_dir.resolve()
        _register_confirmed_bundles(
            database,
            images_dir,
            list(args.register_existing or []),
            args.application_name,
        )
        result = scan_inventory(database, images_dir)
        report = build_report(result)
        digest = report_sha256(report)
        print(report, end="")
        print(f"REPORT_SHA256={digest}")
        print("REPORT_PREVIEW_ONLY=verified")
        return 0
    except (InventoryError, OSError, RuntimeError) as error:
        print(f"VM_INVENTORY_SCAN=failed reason={type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
