from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

SSH_SKILLS = (
    "utm-2",
    "utm-3",
    "vm-down",
    "utm-4",
    "files",
    "utm-clash",
    "utm-6",
    "utm-9",
    "utm-16",
    "utm-17",
    "utm-18",
    "utm-19",
    "utm-21",
    "utm-22",
)


def main() -> None:
    texts = {
        name: (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        for name in SSH_SKILLS
    }

    for name, text in texts.items():
        assert "## SSH 全自动约束" in text, name
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("ssh "):
                assert "BatchMode=yes" in stripped, f"{name}: {stripped}"

    utm2 = texts["utm-2"]
    for value in (
        "${SUBMISSION_SSH_PUBLIC_KEY}",
        "ssh-copy-id",
        "ssh-keygen -lf",
        "authorized_keys",
        "SSH_DEMO_KEY=verified",
        "SSH_SERVICE=verified",
        "SSH_KEY_AUTH=blocked",
        "notify-fault",
        "wait-decision",
        "--recovery-skill 'utm-2'",
        "manual_continue",
        "retry_skill",
    ):
        assert value in utm2, value
    assert "do not wait for `manual_continue`" not in utm2

    utm3 = texts["utm-3"]
    for value in (
        "${SUBMISSION_SSH_PUBLIC_KEY}",
        "ssh-copy-id",
        "authorized_keys",
        "SSH_KEY_AUTH=verified",
        "BatchMode=yes",
        "utm-3-user-exists",
        "notify-fault",
        "wait-decision",
        "--recovery-skill 'utm-3'",
        "manual_continue",
        "retry_skill",
        "AUTO_RECOVERY_RESULT=unrepairable",
    ):
        assert value in utm3, value
    assert "If it returns a user ID, stop." not in utm3

    for path in (ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "docs/utm-feishu-bot.md"):
        text = path.read_text(encoding="utf-8")
        for value in (
            "utm-3-user-exists",
            "自动",
            "最后故障卡",
        ):
            assert value in text, f"{path.name}: {value}"
        assert "重复故障必须发送新卡" not in text, path.name

    for name in ("utm-3", "vm-down", "utm-4"):
        text = texts[name]
        for stale in (
            "unless the user explicitly supplies another password",
            "unless the user explicitly supplied a different password",
            "unless the run explicitly recorded another password",
            "approved account password",
        ):
            assert stale not in text, f"{name}: {stale}"

    for path in (ROOT / "README.md", ROOT / "AGENTS.md"):
        text = path.read_text(encoding="utf-8")
        for value in (
            "SSH 全自动硬规则",
            "SSH_KEY_AUTH=verified",
            "${SUBMISSION_SSH_PUBLIC_KEY}",
            "不得向用户索取密码、SSH Key、IP",
            "SSH_AUTO_RECOVERY=blocked",
        ):
            assert value in text, f"{path.name}: {value}"
        assert "自动恢复仍失败" in text or "三轮仍失败" in text, path.name
        assert "三按钮故障卡" in text, path.name

    print("UTM_SSH_AUTOMATION=verified")


if __name__ == "__main__":
    main()
