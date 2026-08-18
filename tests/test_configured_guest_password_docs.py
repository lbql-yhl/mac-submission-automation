from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "skills/_shared/AUTOMATION_CONTRACT.md",
    "skills/utm-21/SKILL.md",
    "skills/utm-22/SKILL.md",
    "skills/utm-23/SKILL.md",
    "skills/utm-24/SKILL.md",
    "skills/utm-vm-clone/SKILL.md",
    "docs/utm-21.md",
    "docs/utm-22.md",
)


def test_operational_docs_require_host_configured_guest_password() -> None:
    for relative in TARGETS:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "SUBMISSION_GUEST_PASSWORD" in text, relative
        assert "OP-FIXED-PASSWORD-1234" not in text, relative
        assert "`1234`" not in text, relative

    shared = (ROOT / TARGETS[0]).read_text(encoding="utf-8")
    assert "OP-CONFIGURED-GUEST-PASSWORD" in shared
    assert "宿主 `.env`" in shared
    assert "不得回显" in shared

    for relative in TARGETS[1:6]:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "OP-CONFIGURED-GUEST-PASSWORD" in text, relative
