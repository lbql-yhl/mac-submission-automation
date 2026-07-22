#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/notion-utm-1/SKILL.md"


def main() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    for value in (
        "金币表格", "研发金币图链接", "截图链接",
        "COIN_TABLE_URL=blank", "COIN_TABLE_URL=invalid",
        "RND_COIN_IMAGE_URL=blank", "RND_COIN_IMAGE_URL=invalid",
        "SCREENSHOT_URL=blank", "SCREENSHOT_URL=invalid",
        "5/15/30 秒 GET 重试", "三轮后仍无唯一结果才 `exhausted`",
        "AUTO_RECOVERY_ATTEMPTS=3", "AUTO_RECOVERY_RESULT=unrepairable",
        "此时才使用文件开头的统一 `notify-fault`",
        "重新实时读取同一应用的唯一飞书记录",
        "自动覆盖现有 `应用信息`", "--replace-existing",
        "无需用户确认，也不发送故障卡",
    ):
        assert value in skill, value

    docs = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ("README.md", "AGENTS.md", "docs/utm-feishu-bot.md")
    )
    for value in (
        "金币表格", "研发金币图链接", "截图链接",
        "空值", "URL 无效", "三轮", "最后故障卡", "自动覆盖",
    ):
        assert value in docs, value

    print("NOTION_UTM_1_RECOVERY_FIRST=verified")


if __name__ == "__main__":
    main()
