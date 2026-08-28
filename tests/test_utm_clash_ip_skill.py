from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "utm-clash-ip" / "SKILL.md"


def test_utm_clash_ip_unifies_notion_proxy_clash_egress_and_environment() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert "name: utm-clash-ip" in text
    assert "utm-login" in text
    assert "UTM_CLASH_IP=verified" in text
    assert "$PROJECT_ROOT/scripts/utm_clash_ip.py" in text
    assert "--application-name '<app-name>'" in text
    assert "../_shared/AUTOMATION_CONTRACT.md" in text
    assert "Only public host entry" in text


def test_utm_clash_ip_skill_excludes_script_implementation() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    assert "## Contract" in skill
    assert "## Result and handoff" in skill
    assert "socks-port: 7891" not in skill
    assert "DOMAIN-SUFFIX" not in skill


def test_utm_clash_ip_skill_publishes_only_the_mainline_entry() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    assert "$PROJECT_ROOT/scripts/utm_clash_ip.py" in skill
    assert "--application-name '<app-name>'" in skill
    assert "$PROJECT_ROOT/scripts/utm_clash_ip_explicit_test.py" not in skill
    assert "UTM_CLASH_IP=verified" in skill


def test_utm_clash_ip_skill_does_not_describe_internal_recovery() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    for forbidden in (
        "CalledProcessError",
        "CONFIG_ROLLBACK=verified",
        "CONFIG_RECOVERY_DIAGNOSTICS=verified",
        "CONFIG_REPAIR_RETRY=verified",
        "CONFIG_REPAIR_RETRY_LIMIT=exhausted",
        "mode-600",
        "5 秒",
        "脚本自动",
        "同一目标只允许一次修复重试",
        "再次失败",
    ):
        assert forbidden not in skill
