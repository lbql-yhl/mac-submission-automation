#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/utm-1/SKILL.md"
DOC = ROOT / "docs/utm-1.md"


def main() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    for text in (skill, doc):
        for required in (
            "UTM_1_ATTEMPT_ID",
            "UTM_1_ATTEMPT_MODE=600",
            "handoff_verified",
            "sharing_verified",
            "network_verified",
            "running_verified",
            "login_verified",
            "CLONE_START_GUARD=blocked",
            "UTM_1=verified",
            "LOGIN_DESKTOP=verified",
        ):
            assert required in text, required
    assert "若判断登录步骤不需要" not in skill
    assert "macOS 登录界面" in skill
    assert "demo" in skill
    print("UTM_1_SKILL_CONTRACT=verified")


if __name__ == "__main__":
    main()
