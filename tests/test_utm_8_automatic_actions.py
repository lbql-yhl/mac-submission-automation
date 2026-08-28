from pathlib import Path

from scripts import utm_8_change_password
from skill_contract_assertions import assert_shared_contract_reference


ROOT = Path(__file__).resolve().parents[1]
SKILL_FILE = ROOT / "skills" / "utm-edit" / "SKILL.md"
SHARED_CONTRACT = ROOT / "skills" / "_shared" / "AUTOMATION_CONTRACT.md"


def test_utm_edit_skill_exposes_only_the_public_password_change_contract() -> None:
    text = SKILL_FILE.read_text(encoding="utf-8")

    assert_shared_contract_reference(SKILL_FILE, text, SHARED_CONTRACT)
    assert "scripts/utm_8_change_password.py" in text
    for selector in ("--page-title", "--vm-name", "--vm-ip", "--vm-user"):
        assert selector in text
    assert "UTM_8=verified" in text
    assert "utm-key" in text
    assert "without printing a secret" in text


def test_password_change_entry_owns_action_and_readback_evidence() -> None:
    assert {
        "PASSWORD_CHANGE_SUBMISSION=clicked_once",
        "PASSWORD_CHANGE_RESULT=verified",
        "SYSTEM_SETTINGS_CLOSED=verified",
        "PASSWORD_CHANGE=verified",
    }.issubset(utm_8_change_password.REQUIRED_GUEST_MARKERS)


def test_password_change_entry_uses_project_notion_and_clean_cli_wrappers() -> None:
    source = (ROOT / "scripts" / "utm_8_change_password.py").read_text(
        encoding="utf-8"
    )

    assert "from scripts.notion_api import api_from_env" in source
    assert "run_clean_cli(" in source
    assert 'success_marker="UTM_8=verified"' in source
    assert "SUBMISSION_SSH_PRIVATE_KEY" not in source
