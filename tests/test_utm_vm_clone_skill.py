from pathlib import Path

from scripts import preflight


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "utm-vm-clone" / "SKILL.md"


def test_utm_vm_clone_skill_documents_the_single_entry_and_storage_selection() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert "name: utm-vm-clone" in text
    assert "Use when" in text
    assert 'python3 "$PROJECT_ROOT/scripts/utm_clone_and_initialize.py"' in text
    assert "UTM_CLONE_AND_INITIALIZE=verified" in text
    assert "SUBMISSION_VM_IMAGES_DIRS" in text
    assert "first eligible configured external directory" in text
    assert "300 decimal GB" in text
    assert "0/5/10 seconds" in text
    assert "AutoA" not in text
    assert "macos2" not in text
    assert not (ROOT / "docs" / "utm-vm-clone.md").exists()
    assert not (ROOT / "docs" / "utm-post-clone.md").exists()

    assert len(text.splitlines()) <= 70


def test_utm_vm_clone_storage_pool_is_in_public_configuration() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    configuration = (ROOT / "docs" / "configuration.md").read_text(
        encoding="utf-8"
    )

    assert "SUBMISSION_VM_IMAGES_DIRS=" in env_example
    assert "`SUBMISSION_VM_IMAGES_DIRS`" in configuration
    assert "300 GB" in configuration


def test_utm_vm_clone_starts_the_16_skill_mainline_without_utm_a() -> None:
    result = preflight.check(project_only=True)

    assert len(preflight.ORDERED) == 16
    assert preflight.ORDERED[0] == "utm-vm-clone"
    assert preflight.STANDALONE == ("utm-iap",)
    assert result["skills_count"] == 16
    assert result["standalone_skills_count"] == 1
    assert result["skill_set_exact"] is True
    assert result["ok"] is True

    installer = (ROOT / "scripts" / "install_project_skills.sh").read_text(
        encoding="utf-8"
    )
    assert (
        'install_entries=("${skills[@]}" "${standalone_skills[@]}" "_shared")'
        in installer
    )
    assert installer.count("PROJECT_SKILLS_INSTALLED=16") == 2
    assert installer.count("PROJECT_STANDALONE_SKILLS_INSTALLED=1") == 2
    assert "PROJECT_SKILLS_INSTALLED=25" not in installer


def test_project_only_bootstrap_does_not_require_chat_host_tools(monkeypatch) -> None:
    monkeypatch.setattr(preflight, "executable_exists", lambda _command: False)

    result = preflight.check(project_only=True)

    assert "codex" not in result
    assert "submission_runner_entry" not in result
    assert result["ok"] is True
