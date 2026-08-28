from pathlib import Path

import pytest

from scripts.utm_env_generate import write_env
from skill_contract_assertions import assert_shared_contract_reference


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
SHARED_CONTRACT = SKILLS / "_shared" / "AUTOMATION_CONTRACT.md"

LATE_SKILLS = (
    ("utm-env", "scripts/utm_env.py", "UTM_ENV=verified", "utm-script"),
    ("utm-script", "scripts/utm_18.py", "UTM_18=verified", "utm-image"),
    ("utm-image", "scripts/utm_image.py", "UTM_19=verified", "utm-p8"),
    ("utm-p8", "scripts/utm_p8.py", "UTM_P8=verified", "utm-21"),
    ("utm-21", "scripts/utm_21_prepare.py", "UTM_21=verified", "utm-22"),
    ("utm-22", "scripts/utm_22_upload.py", "UTM_22=verified", "utm-23"),
    ("utm-23", "scripts/utm_23.py", "UTM_23=verified", "utm-24"),
    ("utm-24", "scripts/session.mjs", "UTM_24=verified", None),
)


def sample_env() -> dict[str, str]:
    return {
        "APP_ID": "1234567890",
        "CONTACT_PHONE": "+15551234567",
        "CONTACT_EMAIL": "person@example.com",
        "VM_NAME": "abcd",
        "CONTACT_FIRST_NAME": "Ada",
        "CONTACT_LAST_NAME": "Lovelace",
        "COPYRIGHT": "Example",
        "BUNDLE_ID": "com.example.app",
        "PRIMARY_CATEGORY": "GRAPHICS_AND_DESIGN",
        "DESCRIPTION": "First paragraph.",
        "KEYWORDS": "photo,design",
        "TOP_LEVEL_DOMAIN": "example.com",
        "SUPPORT_URL": "https://example.com/support",
        "PRIVACY_POLICY_URL": "https://example.com/privacy",
        "PRIVACY_CHOICES_URL": "https://example.com/terms",
    }


def test_env_writer_is_atomic_private_and_idempotent(tmp_path: Path) -> None:
    output = write_env(sample_env(), tmp_path)
    inode = output.stat().st_ino
    first = output.read_bytes()

    assert output.name == ".env"
    assert output.stat().st_mode & 0o777 == 0o600
    assert b"APP_ID=1234567890" in first
    assert b"CONTACT_EMAIL=person@example.com" in first

    repeated = write_env(sample_env(), tmp_path)
    assert repeated == output
    assert repeated.stat().st_ino == inode
    assert repeated.read_bytes() == first


@pytest.mark.parametrize(
    ("skill_name", "entry", "marker", "handoff"),
    LATE_SKILLS,
)
def test_late_skill_contracts_expose_entry_result_and_handoff(
    skill_name: str,
    entry: str,
    marker: str,
    handoff: str | None,
) -> None:
    skill_file = SKILLS / skill_name / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")

    assert_shared_contract_reference(skill_file, text, SHARED_CONTRACT)
    assert entry in text
    assert marker in text
    if handoff is None:
        assert "no next skill" in text
    else:
        assert handoff in text


@pytest.mark.parametrize(
    "entry",
    sorted({entry for _, entry, _, _ in LATE_SKILLS}),
)
def test_late_public_entries_exist(entry: str) -> None:
    assert (ROOT / entry).is_file(), entry
