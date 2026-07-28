#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

FORBIDDEN = (
    "截图",
    "screenshot",
    "最新截图",
    "GUI",
    "图形",
    "点击",
    "click ",
    "窗口",
    "桌面",
    "login screen",
    "登录界面",
    "Computer Use",
    "坐标",
    "鼠标",
    "键盘注入",
)

REQUIRED = {
    "utm-clone-macos": (
        "UTM CLI/Registry",
        "CLONE_CONFIG_IDENTITY=verified",
        "UTM_REGISTRATION_MATCH_COUNT=1",
    ),
    "utm-2": (
        "VM_CONFIG_MAC=verified",
        "GUEST_IDENTIFIER_LINES=2",
        "ifconfig",
        "REMOTE_LOGIN=verified",
    ),
    "vm-down": (
        "UTM_SHARE_READONLY=verified",
        "READONLY_PROBE=verified",
        "pmset -a",
        "REMOTE_LOGIN_PERSISTENCE=verified",
        "SCREENSAVER_IDLETIME=0",
    ),
}


def main() -> None:
    for name, required in REQUIRED.items():
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        for value in required:
            assert value in text, f"{name}: missing {value}"
        lowered = text.lower()
        for forbidden in FORBIDDEN:
            assert forbidden.lower() not in lowered, f"{name}: visual residue {forbidden}"
    print("NONVISUAL_VM_BOOTSTRAP_SKILLS=verified")


if __name__ == "__main__":
    main()
