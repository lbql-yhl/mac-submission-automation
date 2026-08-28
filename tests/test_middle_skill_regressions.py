from pathlib import Path

import pytest

from scripts.utm_8_change_password import REQUIRED_GUEST_MARKERS
from scripts.utm_apps import GUEST_WRAPPERS
from scripts.utm_business import REQUIRED_MARKERS as BUSINESS_MARKERS
from skill_contract_assertions import assert_shared_contract_reference


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
SHARED_CONTRACT = SKILLS / "_shared" / "AUTOMATION_CONTRACT.md"

MIDDLE_SKILLS = (
    ("utm-clash-ip", "scripts/utm_clash_ip.py", "UTM_CLASH_IP=verified", "utm-login"),
    ("utm-edit", "scripts/utm_8_change_password.py", "UTM_8=verified", "utm-key"),
    ("utm-key", "scripts/utm_9.py", "UTM_9=verified", "utm-apps"),
    ("utm-apps", "scripts/utm_apps.py", "UTM_APPS=verified", "utm-business"),
    ("utm-business", "scripts/utm_business.py", "UTM_BUSINESS=verified", "utm-env"),
)


@pytest.mark.parametrize(
    ("skill_name", "entry", "marker", "handoff"),
    MIDDLE_SKILLS,
)
def test_middle_skill_contracts_expose_entry_result_and_handoff(
    skill_name: str,
    entry: str,
    marker: str,
    handoff: str,
) -> None:
    skill_file = SKILLS / skill_name / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")

    assert_shared_contract_reference(skill_file, text, SHARED_CONTRACT)
    assert entry in text
    assert marker in text
    assert handoff in text


def test_password_change_entry_owns_the_verified_guest_markers() -> None:
    assert {
        "PASSWORD_CHANGE_NAVIGATION=verified",
        "PASSWORD_CHANGE_FIELDS=verified",
        "PASSWORD_CHANGE_BUTTON=enabled",
        "PASSWORD_CHANGE_SUBMISSION=clicked_once",
    }.issubset(REQUIRED_GUEST_MARKERS)


def test_apps_entry_owns_the_four_post_login_stages() -> None:
    assert GUEST_WRAPPERS == {
        "utm-10": "utm_10_login.mjs",
        "utm-11": "utm_11_one.mjs",
        "utm-12": "utm_12_one.mjs",
        "utm-13": "utm_13_one.mjs",
    }


def test_business_entry_requires_verified_legal_and_banking_results() -> None:
    assert {
        "PAID_APPS_AGREEMENT=accepted_or_existing",
        "W8BEN_SUBMIT=verified",
        "BANK_ACCOUNT_PROCESSING=verified",
        "UTM_BUSINESS=verified",
    }.issubset(BUSINESS_MARKERS)
