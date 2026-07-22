#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
FAULT_SKILLS = (
    "notion-utm", "notion-utm-1", "utm-clone-macos", "utm-1", "utm-2",
    "utm-3", "vm-down", "utm-4", "utm-5", "files", "utm-clash", "utm-6",
    "utm-7", "utm-8", "utm-9", "utm-10", "utm-11", "utm-12", "utm-13",
    "utm-14", "utm-15", "utm-16", "utm-17", "utm-18", "utm-19", "utm-20",
    "utm-21", "utm-22", "utm-23", "utm-24", "utm-25",
)


def main() -> None:
    shared = (SKILLS / "_shared/AUTOMATION_CONTRACT.md").read_text(encoding="utf-8")
    for required in (
        "自动诊断 → 自动修复 → 自动复验 → 最后才发故障卡",
        "每个步骤的五段式执行",
        "每次 GUI 动作后的固定闭环",
        "误点检测",
        "可逆误点恢复",
        "不可逆动作的两阶段门禁",
        "有界恢复预算",
        "飞书卡片是最后出口",
        "AUTO_RECOVERY_ATTEMPTS",
        "AUTO_RECOVERY_ACTIONS",
        "AUTO_RECOVERY_RESULT=exhausted|unrepairable",
        "OP-NATIVE-PASTE",
        "OP-BROWSER-URL-NO-SCHEME",
        "OP-APPLE-PHONE-OTP",
        "OP-FIXED-PASSWORD-1234",
        "OP-USER-CONFIRMATION",
        "scripts/shared_operations.py browser-url",
        "少于三轮时禁止调用 `notify-fault`",
        "不存在 `0` 次直接发卡例外",
    ):
        assert required in shared, required

    for name in FAULT_SKILLS:
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        for required in (
            "../_shared/AUTOMATION_CONTRACT.md",
            "## 全局自动恢复与最后故障卡规则",
            "## 本技能自动恢复矩阵",
            "自动诊断、自动修复、自动复验",
            "只有智能体确实无法修复时",
            "--recovery-attempts",
            "--recovery-actions",
            "--recovery-result '<exhausted|unrepairable>'",
            "--unrepairable",
            "<actual-count-at-least-3>",
            "可安全修复的故障必须做满三轮“诊断→实际修复→独立复验”",
            "OP-BROWSER-URL-NO-SCHEME",
            "OP-USER-CONFIRMATION",
            "--decision-kind fault",
            "--timeout-seconds 3600",
            "`stop`",
            "`manual_continue`",
            "`retry_skill`",
            f"--recovery-skill '{name}'",
        ):
            assert required in text, f"{name}: {required}"
        assert text.count("services/feishu_bot.py notify-fault") == 1, name
        assert "notify-stop" not in text, name

    active_docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "README.md",
            ROOT / "AGENTS.md",
            ROOT / "docs/utm-feishu-bot.md",
        )
    )
    for required in (
        "最后故障卡",
        "recovery_attempts",
        "recovery_actions",
        "recovery_result",
        "恢复穷尽",
        "首次确认送达",
        "3600 秒",
        "decision_timeout_stop",
        "等待期间不发送提醒卡",
        "不再重发、不再轮询、不再恢复",
        "record-auto-review-approval",
        "source=automatic_self_check",
        "notify-confirmation",
        "confirm_continue",
        "USER_CONFIRMATION=verified",
        "recovery_attempts>=3",
        "scripts/shared_operations.py browser-url",
    ):
        assert required in active_docs, required

    source = (ROOT / "services/feishu_bot.py").read_text(encoding="utf-8")
    for required in (
        "def validate_fault_recovery_evidence(",
        "recovery_attempts",
        "recovery_actions",
        "recovery_result",
        "unrepairable",
        "attempts < 3",
        "def create_or_update_confirmation(",
        "def build_confirmation_card(",
        "def notify_confirmation(",
        '"submission_confirmation_decision"',
        '"confirm_continue"',
        "notify-confirmation requires --stage",
        '"decision_id": uuid.uuid4().hex',
        "Another decision card is already waiting",
        "stale_fault_decision",
        "def record_automatic_review_approval(",
        '"source": "automatic_self_check"',
        '"operator_id": "automation:self-check"',
    ):
        assert required in source, required
    for stale in ("notify-stop", "def notify_stop(", "resend_fault_decision_if_due"):
        assert stale not in source, stale

    all_skills_and_docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (*sorted(SKILLS.glob("*/SKILL.md")), *sorted((ROOT / "docs").glob("*.md")))
    )
    for stale in (
        "--recovery-attempts 0",
        "AUTO_RECOVERY_ATTEMPTS=2",
        "type_text` is allowed for this one-time code",
        "两轮可逆修复后",
        "两轮安全修复后",
        "两轮安全重贴后",
        "最多两轮安全",
        "重新定位两轮，再做第三轮",
    ):
        assert stale not in all_skills_and_docs, stale

    print("FEISHU_RECOVERY_FIRST_CONTRACT=verified")


if __name__ == "__main__":
    main()
