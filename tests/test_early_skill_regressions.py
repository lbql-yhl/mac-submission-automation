#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def read(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def main() -> None:
    notion_1 = read("notion-utm-1")
    assert "5/15/30 秒 GET 重试" in notion_1
    assert "2/5/10 秒 GET 重试" not in notion_1
    assert "fresh card decision" not in notion_1
    assert notion_1.count("scripts/notion_api.py verify-parent") >= 4
    assert "APPLICATION_INFO_READBACK=exact" in notion_1

    clone = read("utm-clone-macos")
    for unsafe in ("test ! -e", "du -sh", "test $? -ne 0"):
        assert unsafe not in clone, unsafe
    for required in (
        "CLONE_ATTEMPT_ID",
        "CLONE_DESTINATION=absent|resume_verified|conflict",
        "CLONE_SOURCE_MANIFEST_SHA256",
        "UTM_REGISTRATION_MATCH_COUNT=1",
    ):
        assert required in clone, required

    utm_1 = read("utm-1")
    assert "~/Desktop/共享文件" not in utm_1
    for required in (
        "SHARING_MATCH_COUNT=1",
        "SHARING_READ_ONLY=verified",
        "LOGIN_USER=demo",
        "LOGIN_DESKTOP=verified",
    ):
        assert required in utm_1, required

    utm_3 = read("utm-3")
    assert "key=${SUBMISSION_SSH_PRIVATE_KEY}" not in utm_3
    for required in (
        "ACCOUNT_ATTEMPT_ID",
        'private_key="${SUBMISSION_SSH_PRIVATE_KEY}"',
        'public_key="${SUBMISSION_SSH_PUBLIC_KEY}"',
        'IdentitiesOnly=yes -i "$private_key"',
        "ACCOUNT_MARKER=verified",
    ):
        assert required in utm_3, required

    vm_down = read("vm-down")
    assert "shutdown -r now" not in vm_down
    assert "&& { rm -f \"$probe\"; exit 1; } || cat" not in vm_down
    assert "Do not change CPU, memory, display, disk, network, sharing" not in vm_down
    for required in (
        'private_key="${SUBMISSION_SSH_PRIVATE_KEY}"',
        'IdentitiesOnly=yes -i "$private_key"',
        "MOUNT_PATH=/Volumes/My Shared Files/共享文件",
        "READONLY_PROBE=verified",
    ):
        assert required in vm_down, required

    utm_4 = read("utm-4")
    assert "sysadminctl -deleteUser demo -secure ||" not in utm_4
    assert "/usr/bin/id demo 2>&1 || true" not in utm_4
    for required in (
        "DEMO_DELETE_ATTEMPT_ID",
        "DEMO_STATE=absent",
        'IdentitiesOnly=yes -i "$private_key"',
    ):
        assert required in utm_4, required

    files = read("files")
    assert "Same-name destination entries are refreshed by `ditto`" not in files
    for required in (
        "COPY_PREFLIGHT=verified",
        "SOURCE_ENTRIES=>0",
        "DEST_CONFLICTS=0",
        "SOCKS5_COPY_HASH=verified",
        'IdentitiesOnly=yes -i "$private_key"',
    ):
        assert required in files, required

    clash = read("utm-clash")
    assert "-print -quit" not in clash
    assert "pgrep -fl \"Clash Verge|clash-verge|verge\" || true" not in clash
    for required in (
        "CONFIG_DIR_MATCH_COUNT=1",
        "CONFIG_WRITE=atomic_verified",
        "CLASH_PROCESS=verified",
        "RUNTIME_TUN=verified",
        'IdentitiesOnly=yes -i "$private_key"',
    ):
        assert required in clash, required

    print("EARLY_SKILL_REGRESSIONS=verified")


if __name__ == "__main__":
    main()
