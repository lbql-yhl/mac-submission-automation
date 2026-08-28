#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/utm-21/SKILL.md"
ENTRY = "$PROJECT_ROOT/scripts/utm_21_prepare.py"


def test_utm_21_skill_exposes_the_complete_command_only_workflow() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert skill.count(ENTRY) == 1
    for required in (
        "UTM_P8=verified",
        "Feishu OpenAPI",
        "代码 URL",
        "main",
        "dev",
        "release",
        "<app-name>-git",
        "Downloads/<app-name>-git",
        "HOST_CONTENT_MANIFEST=verified",
        "GUEST_CONTENT_MANIFEST=verified",
        "scripts/notion_api.py",
        "APP_ID：",
        "正式包名: ",
        "5372311233",
        "jltest.test.test",
        "uildbet.brovaxtere",
        "xycoins.2027.test",
        "org.toolbox.fastcleaner",
        "SSH stdin JSON",
        "非级联字节替换",
        "宿主共享目录中的原始代码保持不变",
        "不存在时计数为 0 并继续",
        "VISUAL_CONTROL=forbidden",
        "AGENT_CONTROL=forbidden",
        "UTM_21=verified",
        "utm-22",
    ):
        assert required in skill, required
    assert "runtime/feishu-runs.json" not in skill
    for required in (
        "utm_21_clone.py",
        "Codeup",
        "CODEUP_",
        "placeholder",
        "origin/main",
        "git diff --check",
        "Runner.xcworkspace",
    ):
        assert required not in skill, required
