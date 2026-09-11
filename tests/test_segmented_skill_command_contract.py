import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills"

SEGMENTS = (
    (1, "虚拟机准备", ("utm-vm-clone",)),
    (
        2,
        "环境准备",
        (
            "utm-notion",
            "utm-clash-ip",
            "utm-login",
            "utm-edit",
            "utm-key",
            "utm-apps",
            "utm-business",
        ),
    ),
    (3, "脚本准备、执行", ("utm-env", "utm-script", "utm-image", "utm-p8")),
    (4, "代码处理", ("utm-21", "utm-22", "utm-23", "utm-24")),
)

ORDERED = tuple(name for _, _, skills in SEGMENTS for name in skills)
STANDALONE = ("utm-iap",)

ENTRY_SCRIPTS = {
    "utm-vm-clone": "scripts/utm_clone_and_initialize.py",
    "utm-notion": "scripts/utm_notion.py",
    "utm-clash-ip": "scripts/utm_clash_ip.py",
    "utm-login": "scripts/utm_7_login.py",
    "utm-edit": "scripts/utm_8_change_password.py",
    "utm-key": "scripts/utm_9.py",
    "utm-apps": "scripts/utm_apps.py",
    "utm-business": "scripts/utm_business.py",
    "utm-env": "scripts/utm_env.py",
    "utm-script": "scripts/utm_18.py",
    "utm-image": "scripts/utm_image.py",
    "utm-p8": "scripts/utm_p8.py",
    "utm-21": "scripts/utm_21_prepare.py",
    "utm-22": "scripts/utm_22_upload.py",
    "utm-23": "scripts/utm_23.py",
    "utm-24": "scripts/session.mjs",
}

def _skill_path(name: str) -> Path:
    return SKILL_ROOT / name / "SKILL.md"


def _skill_text(name: str) -> str:
    return _skill_path(name).read_text(encoding="utf-8")


def _contract_text(name: str) -> str:
    skill_file = _skill_path(name)
    match = re.search(
        r"\]\(([^)\n]*AUTOMATION_CONTRACT\.md)\)", _skill_text(name)
    )
    assert match, name
    return (skill_file.parent / match.group(1)).resolve().read_text(encoding="utf-8")


def test_agents_is_the_authoritative_source_for_exact_segments_and_order() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    current_line = next(
        line
        for line in agents.splitlines()
        if line.startswith("- Current skills in exact order:")
    )
    assert tuple(re.findall(r"`([^`]+)`", current_line)) == ORDERED

    declared_segments = []
    for number, label, skills in re.findall(
        r"(?m)^(\d+)\. ([^：\n]+)：([^\n]+)$", agents
    ):
        declared_segments.append(
            (int(number), label, tuple(re.findall(r"[a-z]+(?:-[a-z0-9]+)+", skills)))
        )
    assert tuple(declared_segments) == SEGMENTS


def test_every_skill_uses_an_existing_portable_repository_entry() -> None:
    assert set(ENTRY_SCRIPTS) == set(ORDERED)
    for name, relative_entry in ENTRY_SCRIPTS.items():
        text = _skill_text(name)
        assert (ROOT / relative_entry).is_file(), name
        assert f"$PROJECT_ROOT/{relative_entry}" in text, name

        referenced_entries = set(
            re.findall(r"\$PROJECT_ROOT/([A-Za-z0-9_./-]+\.(?:py|mjs|sh))", text)
        )
        assert relative_entry in referenced_entries, name
        for referenced_entry in referenced_entries:
            assert (ROOT / referenced_entry).is_file(), (name, referenced_entry)


def test_utm_21_entry_owns_the_complete_nonvisual_workflow() -> None:
    text = _skill_text("utm-21")
    assert "完整 UTM-21 工作流" in text
    assert "VISUAL_CONTROL=forbidden" in text
    assert "AGENT_CONTROL=forbidden" in text

    text = _skill_text("utm-23")
    assert "complete App Store Connect browser workflow" in text
    assert "VISUAL_BROWSER_CONTROL=forbidden" in text
    assert "SUBAGENT_BROWSER_CONTROL=forbidden" in text

    for name in ("utm-24",):
        text = _skill_text(name)
        assert "browser-session entry helper" in text, name
        assert "session.mjs" in text and "inspect" in text, name
        assert f"complete `{name}` wrapper" in text, name


def test_all_mainline_skills_are_owned_by_the_repository_skill_tree() -> None:
    discovered = tuple(
        sorted(path.parent.name for path in SKILL_ROOT.glob("*/SKILL.md"))
    )
    assert set(discovered) == set(ORDERED) | set(STANDALONE)
    assert "utm-iap" not in ORDERED
    assert "utm-iap" in discovered
