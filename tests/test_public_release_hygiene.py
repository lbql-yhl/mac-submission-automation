import os
from pathlib import Path
import subprocess

from scripts.public_release_audit import (
    REQUIRED_SENSITIVE_EXAMPLE_KEYS,
    audit_repository,
)


ROOT = Path(__file__).resolve().parents[1]


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )


def _tracked_fixture_repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    assert _git(root, "init", "-q").returncode == 0

    personal_home = "/" + "Users" + "/audit-fixture/private"
    secret_value = "fixture-value-that-must-not-be-reported"
    (root / "unsafe.py").write_text(
        f'HOME_PATH = "{personal_home}"\n'
        f'FIXED_PASSWORD = "{secret_value}"\n'
        f'DEFAULT_APP_TOKEN = "{secret_value}"\n'
        f'DAILY_REPORT_CHAT_ID = "{secret_value}"\n',
        encoding="utf-8",
    )
    historical = root / "docs/superpowers/plans/old.md"
    historical.parent.mkdir(parents=True)
    historical.write_text("historical\n", encoding="utf-8")
    (root / "binary.dat").write_bytes(
        personal_home.encode() + b"\0" + secret_value.encode()
    )
    (root / ".env").write_text(
        f'FIXED_PASSWORD="{secret_value}"\n', encoding="utf-8"
    )
    (root / ".env.example").write_text(
        "".join(f"{key}=\n" for key in REQUIRED_SENSITIVE_EXAMPLE_KEYS),
        encoding="utf-8",
    )
    (root / "untracked.py").write_text(
        f'FIXED_PASSWORD = "{secret_value}"\n', encoding="utf-8"
    )
    os.symlink("unsafe.py", root / "tracked-link.py")
    assert (
        _git(
            root,
            "add",
            "unsafe.py",
            "docs/superpowers/plans/old.md",
            "binary.dat",
            ".env",
            ".env.example",
            "tracked-link.py",
        ).returncode
        == 0
    )
    return root


def test_audit_repository_returns_rule_and_relative_path_pairs() -> None:
    findings = audit_repository(ROOT)

    assert isinstance(findings, list)
    assert all(
        isinstance(rule, str) and isinstance(relative_path, str)
        for rule, relative_path in findings
    )


def test_audit_scans_only_tracked_regular_text_files_and_never_reads_env(
    tmp_path: Path, monkeypatch,
) -> None:
    root = _tracked_fixture_repository(tmp_path)
    original_read_bytes = Path.read_bytes

    def guarded_read_bytes(path: Path) -> bytes:
        if path == root / ".env":
            raise AssertionError("the host .env must never be read")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)

    findings = audit_repository(root)

    assert ("PERSONAL_HOME_PATH", "unsafe.py") in findings
    assert ("SENSITIVE_ASSIGNMENT", "unsafe.py") in findings
    assert ("FIXED_REPORT_DESTINATION", "unsafe.py") in findings
    assert ("HISTORICAL_PLAN", "docs/superpowers/plans/old.md") in findings
    content_rules = {
        "PERSONAL_HOME_PATH",
        "SENSITIVE_ASSIGNMENT",
        "FIXED_REPORT_DESTINATION",
        "EXAMPLE_SENSITIVE_VALUE",
    }
    assert all(
        rule not in content_rules
        for rule, path in findings
        if path in {".env", "binary.dat", "tracked-link.py", "untracked.py"}
    )
    assert "fixture-value-that-must-not-be-reported" not in repr(findings)
    assert findings == sorted(set(findings))


def test_sensitive_example_keys_are_required_and_must_be_empty(tmp_path: Path) -> None:
    root = _tracked_fixture_repository(tmp_path)
    nonempty_key = "SUBMISSION_PROJECT_ROOT"
    missing_key = "SUBMISSION_HOST_MACHINE"
    (root / ".env.example").write_text(
        "".join(
            f"{key}={'nonempty-fixture-value' if key == nonempty_key else ''}\n"
            for key in REQUIRED_SENSITIVE_EXAMPLE_KEYS
            if key != missing_key
        ),
        encoding="utf-8",
    )

    findings = audit_repository(root)

    assert ("EXAMPLE_SENSITIVE_VALUE", ".env.example") in findings
    assert ("EXAMPLE_SENSITIVE_KEY_MISSING", ".env.example") in findings
    assert "nonempty-fixture-value" not in repr(findings)


def test_duplicate_example_key_cannot_hide_an_earlier_nonempty_value(
    tmp_path: Path,
) -> None:
    root = _tracked_fixture_repository(tmp_path)
    lines = [f"{key}=\n" for key in REQUIRED_SENSITIVE_EXAMPLE_KEYS]
    lines.extend(("NOTION_TOKEN=nonempty-fixture-value\n", "NOTION_TOKEN=\n"))
    (root / ".env.example").write_text("".join(lines), encoding="utf-8")

    findings = audit_repository(root)

    assert ("EXAMPLE_DUPLICATE_KEY", ".env.example") in findings
    assert ("EXAMPLE_SENSITIVE_VALUE", ".env.example") in findings
    assert "nonempty-fixture-value" not in repr(findings)


def test_fixed_report_destination_does_not_require_a_sensitive_key_suffix(
    tmp_path: Path,
) -> None:
    root = _tracked_fixture_repository(tmp_path)
    value = "fixture-destination-that-must-not-be-reported"
    (root / "report.py").write_text(
        f'REPORT_DESTINATION = "{value}"\n', encoding="utf-8"
    )
    assert _git(root, "add", "report.py").returncode == 0

    findings = audit_repository(root)

    assert ("FIXED_REPORT_DESTINATION", "report.py") in findings
    assert value not in repr(findings)


def test_private_runtime_signing_and_vm_files_are_ignored_but_examples_are_allowed() -> None:
    ignored = (
        ".env",
        "config/workflow.env",
        "nested/service.env",
        "runtime/public-release-audit.json",
        "signing/public-release-audit.p8",
        "signing/public-release-audit.p12",
        "signing/public-release-audit.mobileprovision",
        "vm/public-release-audit.qcow2",
        "vm/public-release-audit.vmdk",
        "vm/public-release-audit.utm/config.plist",
    )
    allowed = (".env.example", "config/workflow.env.example")

    missing = [
        path
        for path in ignored
        if _git(ROOT, "check-ignore", "-q", "--no-index", "--", path).returncode
        != 0
    ]
    wrongly_ignored = [
        path
        for path in allowed
        if _git(ROOT, "check-ignore", "-q", "--no-index", "--", path).returncode
        == 0
    ]

    assert not missing, f"missing ignore rules: {missing}"
    assert not wrongly_ignored, f"example files must remain allowed: {wrongly_ignored}"
    assert _git(ROOT, "ls-files", "--error-unmatch", ".env.example").returncode == 0


def test_current_repository_has_an_explicit_red_baseline() -> None:
    findings = set(audit_repository(ROOT))
    expected = {
        ("PERSONAL_HOME_PATH", "README.md"),
        ("SENSITIVE_ASSIGNMENT", "scripts/ssh_password.py"),
        ("SENSITIVE_ASSIGNMENT", "scripts/utm_notion.py"),
        ("FIXED_REPORT_DESTINATION", "services/feishu_bot.py"),
        (
            "HISTORICAL_PLAN",
            "docs/superpowers/plans/2026-08-18-public-release-hardening.md",
        ),
    }

    assert findings
    assert not expected - findings, f"missing baseline findings: {sorted(expected - findings)}"
