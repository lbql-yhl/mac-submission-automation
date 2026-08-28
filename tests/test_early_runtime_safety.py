#!/usr/bin/env python3
from pathlib import Path

import pytest

from scripts.ssh_password import connection_options
from skill_contract_assertions import assert_shared_contract_reference


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
SHARED_CONTRACT = SKILLS / "_shared" / "AUTOMATION_CONTRACT.md"
EARLY_SKILLS = (
    ("utm-vm-clone", "scripts/utm_clone_and_initialize.py", "UTM_CLONE_AND_INITIALIZE=verified", "utm-notion"),
    ("utm-notion", "scripts/utm_notion.py", "status=verified", "utm-clash-ip"),
    ("utm-clash-ip", "scripts/utm_clash_ip.py", "UTM_CLASH_IP=verified", "utm-login"),
)


def test_password_ssh_disables_public_key_fallback() -> None:
    options = connection_options(connect_timeout=7)
    rendered = " ".join(options)

    assert "BatchMode=no" in rendered
    assert "PreferredAuthentications=password,keyboard-interactive" in rendered
    assert "PubkeyAuthentication=no" in rendered
    assert "NumberOfPasswordPrompts=1" in rendered
    assert "ConnectTimeout=7" in rendered
    assert "IdentityFile" not in rendered
    assert "BatchMode=yes" not in rendered


def test_password_channel_removes_plaintext_guest_password_from_child_env() -> None:
    source = (ROOT / "scripts" / "ssh_password.py").read_text(encoding="utf-8")

    assert 'env.pop("SUBMISSION_GUEST_PASSWORD", None)' in source
    assert "SUBMISSION_SSH_ASKPASS_SOCKET" in source
    assert "SUBMISSION_SSH_ASKPASS_CAPABILITY" in source
    assert '"SSH_ASKPASS_REQUIRE": "force"' in source


@pytest.mark.parametrize(
    ("skill_name", "entry", "marker", "handoff"),
    EARLY_SKILLS,
)
def test_early_skill_contracts_expose_entry_result_and_handoff(
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


def test_clone_entry_propagates_only_the_selected_external_vm_directory() -> None:
    source = (ROOT / "scripts" / "utm_clone_and_initialize.py").read_text(
        encoding="utf-8"
    )

    assert 'child_environment["SUBMISSION_VM_IMAGES_DIR"] = str(bundle_parent)' in source
    assert 'child_environment["SUBMISSION_VM_IMAGES_DIRS"] = json.dumps(' in source
    assert "[str(bundle_parent)]" in source
