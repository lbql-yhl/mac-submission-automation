#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/utm-20/SKILL.md"


def main() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    guide = (ROOT / "docs/utm-20.md").read_text(encoding="utf-8")
    combined = "\n".join(
        (
            skill,
            guide,
            (ROOT / "README.md").read_text(encoding="utf-8"),
            (ROOT / "AGENTS.md").read_text(encoding="utf-8"),
            (ROOT / "docs/utm-feishu-bot.md").read_text(encoding="utf-8"),
            (ROOT / "docs/feishu-host-routing.md").read_text(encoding="utf-8"),
        )
    )

    for value in (
        "NOTION_BUSINESS_EXISTING=blank|verified_equal",
        "银行现场恢复检查",
        "不得重复点击 `Add`",
        "异常自动恢复和最后故障卡",
        "不得一发现异常就发卡",
        "utm-20-bank-info-missing",
        "在 5 秒和 10 秒后",
        "共取得三轮实时结果",
        "AUTO_RECOVERY_ATTEMPTS=3",
        "AUTO_RECOVERY_ACTIONS=verify-parent+read-both-fields+clipboard-clear",
        "AUTO_RECOVERY_RESULT=unrepairable",
        "补充到当前匹配 Notion 页的 `账号信息`",
        "卡片回复本身视为银行信息已补充的证据",
    ):
        assert value in skill, value

    for value in (
        "立即、5 秒后、10 秒后共三轮",
        "三轮均为空才",
        "最后故障卡",
        "卡片回复不是补充证据",
    ):
        assert value in guide, value

    for stale in (
        "任一银行值仍为空时清空宿主剪贴板，记录 `utm-20-bank-info-missing`，向原",
        "收到卡片处理回应后再实时重读",
    ):
        assert stale not in combined, stale

    print("UTM_20_RECOVERY_FIRST=verified")


if __name__ == "__main__":
    main()
