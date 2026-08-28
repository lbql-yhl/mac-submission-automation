#!/usr/bin/env python3
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
SHARED_CONTRACT = SKILLS / "_shared" / "AUTOMATION_CONTRACT.md"

SKILL_CONTRACTS = (
    ("utm-vm-clone", "scripts/utm_clone_and_initialize.py", "UTM_CLONE_AND_INITIALIZE=verified", "utm-notion"),
    ("utm-notion", "scripts/utm_notion.py", "status=verified", "utm-clash-ip"),
    ("utm-clash-ip", "scripts/utm_clash_ip.py", "UTM_CLASH_IP=verified", "utm-login"),
    ("utm-login", "scripts/utm_7_login.py", "UTM_7=verified", "utm-edit"),
    ("utm-edit", "scripts/utm_8_change_password.py", "UTM_8=verified", "utm-key"),
    ("utm-key", "scripts/utm_9.py", "UTM_9=verified", "utm-apps"),
    ("utm-apps", "scripts/utm_apps.py", "UTM_APPS=verified", "utm-business"),
    ("utm-business", "scripts/utm_business.py", "UTM_BUSINESS=verified", "utm-env"),
    ("utm-env", "scripts/utm_env.py", "UTM_ENV=verified", "utm-script"),
    ("utm-script", "scripts/utm_18.py", "UTM_18=verified", "utm-image"),
    ("utm-image", "scripts/utm_image.py", "UTM_19=verified", "utm-p8"),
    ("utm-p8", "scripts/utm_p8.py", "UTM_P8=verified", "utm-21"),
    ("utm-21", "scripts/utm_21_prepare.py", "UTM_21=verified", "utm-22"),
    ("utm-22", "scripts/utm_22_upload.py", "UTM_22=verified", "utm-23"),
    ("utm-23", "scripts/utm_23.py", "UTM_23=verified", "utm-24"),
    ("utm-24", "scripts/session.mjs", "UTM_24=verified", None),
)


@pytest.mark.parametrize(
    "entry",
    sorted({entry for _, entry, _, _ in SKILL_CONTRACTS}),
)
def test_every_published_entry_exists(entry: str) -> None:
    assert (ROOT / entry).is_file(), entry


def test_shared_contract_owns_automatic_recovery_and_handoff() -> None:
    shared = SHARED_CONTRACT.read_text(encoding="utf-8")

    for required in (
        "Retry only the exact failed checkpoint while preserving the same run and target.",
        "diagnose, apply one safe reversible repair, then independently reverify",
        "Only after the bounded budget is exhausted",
        "must never be repeated speculatively",
        "Do not wait for ordinary user confirmation.",
        "Never hand off a partial, blocked, ambiguous, or result-unknown state.",
    ):
        assert required in shared
