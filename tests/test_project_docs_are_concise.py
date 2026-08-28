import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PROJECT_DOCS = {
    ROOT / "AGENTS.md": 55,
    ROOT / "README.md": 100,
    ROOT / "docs/project-workflow.md": 65,
    ROOT / "docs/utm-feishu-bot.md": 220,
    ROOT / "shared-files/README.md": 30,
}

FOUR_SEGMENTS = "\n".join((
    "1. 虚拟机准备：utm-vm-clone",
    "2. 环境准备：utm-notion → utm-clash-ip → utm-login → utm-edit → utm-key → utm-apps → utm-business",
    "3. 脚本准备、执行：utm-env → utm-script → utm-image → utm-p8",
    "4. 代码处理：utm-21 → utm-22 → utm-23 → utm-24",
))

IMPLEMENTATION_RESIDUE = (
    "utm_10_login.mjs",
    "utm_11_one.mjs",
    "utm_12_one.mjs",
    "utm_13_one.mjs",
    "utm_business_one.mjs",
    "utm_env_generate.py",
    "utm_image_source.py",
    "AppleAccountScriptsBackup",
    "Playwright DOM",
    "Accessibility",
    "socks5.yml",
    "prod.yml",
    "页面锚点",
    "自动恢复矩阵",
)


def test_project_docs_are_short_indexes_not_script_explanations() -> None:
    for path, maximum_lines in PROJECT_DOCS.items():
        text = path.read_text(encoding="utf-8")
        assert len(text.splitlines()) <= maximum_lines, path
        for residue in IMPLEMENTATION_RESIDUE:
            assert residue not in text, (path, residue)


def test_core_project_docs_publish_the_exact_four_segments() -> None:
    for path in (ROOT / "AGENTS.md", ROOT / "README.md", ROOT / "docs/project-workflow.md"):
        assert FOUR_SEGMENTS in path.read_text(encoding="utf-8"), path


def test_project_docs_do_not_restore_old_skill_names() -> None:
    old_skill = re.compile(
        r"`(?:utm-(?:7|8|9|10|11|12|13|14|15|16|17|18|19|20|25)|"
        r"notion-utm(?:-1)?|utm-clash|utm-clone-macos|vm-down|files)`"
    )
    for path in PROJECT_DOCS:
        assert not old_skill.search(path.read_text(encoding="utf-8")), path


def test_project_docs_point_execution_to_skill_commands() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    workflow = (ROOT / "docs/project-workflow.md").read_text(encoding="utf-8")

    assert "skills/` 是 16 个主线技能的唯一正文源" in agents
    assert "skills/<skill>/SKILL.md" in readme
    assert "每段可单独运行，每个技能也可人工单独指定执行" in readme
    assert "四段均可单独运行，每个技能也可人工单独指定执行" in workflow
    assert "单技能执行以链接的 `SKILL.md` 为唯一可执行真值" in workflow
