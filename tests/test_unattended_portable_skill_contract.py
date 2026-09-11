from pathlib import Path

import pytest

from skill_contract_assertions import assert_shared_contract_reference


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills"
SHARED_CONTRACT = SKILL_ROOT / "_shared" / "AUTOMATION_CONTRACT.md"
ORDERED = (
    "utm-vm-clone",
    "utm-notion",
    "utm-clash-ip",
    "utm-login",
    "utm-edit",
    "utm-key",
    "utm-apps",
    "utm-business",
    "utm-env",
    "utm-script",
    "utm-image",
    "utm-p8",
    "utm-21",
    "utm-22",
    "utm-23",
    "utm-24",
)


STANDALONE = ("utm-iap",)


def test_project_owns_exactly_the_sixteen_canonical_skills() -> None:
    discovered = tuple(
        sorted(path.parent.name for path in SKILL_ROOT.glob("*/SKILL.md"))
    )

    assert set(discovered) == set(ORDERED) | set(STANDALONE)
    assert len(ORDERED) == len(set(ORDERED)) == 16
    assert "utm-iap" in discovered
    assert "utm-iap" not in ORDERED


@pytest.mark.parametrize("skill_name", ORDERED + STANDALONE)
def test_every_skill_inherits_the_portable_contract(skill_name: str) -> None:
    skill_file = SKILL_ROOT / skill_name / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")

    assert_shared_contract_reference(skill_file, text, SHARED_CONTRACT)
    assert 'eval "$(python3 scripts/preflight.py --project-only --emit-shell)"' in text


def test_shared_contract_keeps_paths_and_secrets_host_local() -> None:
    shared = SHARED_CONTRACT.read_text(encoding="utf-8")

    for required in (
        "resolve every repository file from `$PROJECT_ROOT`",
        "Do not hard-code a host user name",
        "must not read host secrets",
        "Never print the root `.env`",
        "Keep values in process memory",
        "protected stdin or environment channels",
        "Do not forward commands, tracebacks, helper logs",
    ):
        assert required in shared


def test_public_configuration_template_keeps_portable_host_keys() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    project_paths = (ROOT / "services" / "project_paths.py").read_text(
        encoding="utf-8"
    )

    for required in (
        "SUBMISSION_HOST_MACHINE=",
        "SUBMISSION_VM_IMAGES_DIRS=",
        "CODEUP_USERNAME=",
        "CODEUP_PASSWORD=",
    ):
        assert required in env_example

    assert "/Volumes/AutoA" not in env_example
    assert "/Volumes/AutoA" not in project_paths


def test_skill_installer_validates_sources_and_rolls_back_partial_installs() -> None:
    installer = (ROOT / "scripts" / "install_project_skills.sh").read_text(
        encoding="utf-8"
    )

    for required in (
        "validate_all_sources",
        "rollback_install",
        "unsafe install root",
        "PROJECT_SKILLS_INSTALLED=16",
        "PROJECT_STANDALONE_SKILLS_INSTALLED=1",
        "PROJECT_SHARED_CONTRACT=linked",
    ):
        assert required in installer
