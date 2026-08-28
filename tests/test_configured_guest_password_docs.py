from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIGURATION = "docs/configuration.md"
HISTORICAL_FIXED_PASSWORD_SPEC = (
    ROOT / "docs/superpowers/specs/2026-08-14-utm-script-visible-terminal-design.md"
)
STALE_PASSWORD_SEMANTICS = (
    "OP-FIXED-PASSWORD-1234",
    "`1234`",
    "fixed password",
    "fixed-password",
    "固定密码",
)


def test_configuration_requires_host_configured_guest_password() -> None:
    text = (ROOT / CONFIGURATION).read_text(encoding="utf-8")
    assert "SUBMISSION_GUEST_PASSWORD" in text
    assert "一次性 SSH askpass broker" in text
    assert "不进入子进程环境或日志" in text
    assert "OP-FIXED-PASSWORD-1234" not in text
    assert "`1234`" not in text


def test_tracked_docs_and_skills_contain_no_stale_fixed_password_semantics() -> None:
    markdown_files = sorted(
        (*((ROOT / "docs").rglob("*.md")), *((ROOT / "skills").rglob("*.md")))
    )
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        for stale in STALE_PASSWORD_SEMANTICS:
            assert stale not in text, f"{path.relative_to(ROOT)}: {stale}"

    assert not HISTORICAL_FIXED_PASSWORD_SPEC.exists()
