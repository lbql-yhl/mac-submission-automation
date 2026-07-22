#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
SKILL_NAMES = (
    "notion-utm", "notion-utm-1", "utm-clone-macos", "utm-1", "utm-2", "utm-3",
    "vm-down", "utm-4", "utm-5", "files", "utm-clash", "utm-6", "utm-7", "utm-8",
    "utm-9", "utm-10", "utm-11", "utm-12", "utm-13", "utm-14", "utm-15", "utm-16",
    "utm-17", "utm-18", "utm-19", "utm-20", "utm-21", "utm-22", "utm-23", "utm-24", "utm-25",
)


def main() -> None:
    skill_texts = {
        name: (SKILLS / name / "SKILL.md").read_text(encoding="utf-8") for name in SKILL_NAMES
    }
    active_docs = [ROOT / "README.md", ROOT / "AGENTS.md", *sorted((ROOT / "docs").glob("utm-*.md"))]
    canonical = "\n".join((*skill_texts.values(), *(path.read_text(encoding="utf-8") for path in active_docs)))

    assert "自动点击一次最终 `Change`/`Continue`" in skill_texts["utm-8"]
    assert "automatically click `Submit` once" in skill_texts["utm-11"]
    assert "两次最终 `Submit` 都在各自页面" in skill_texts["utm-14"]
    assert "自动勾选条款并只点击一次 `Add`" in skill_texts["utm-20"]
    assert "record-auto-review-approval" in skill_texts["utm-24"]
    assert "notify-review" not in skill_texts["utm-24"]
    assert "--decision-kind review_submit" not in skill_texts["utm-24"]
    assert "notify-review-success" not in skill_texts["utm-24"]
    assert "notify-review-success" in skill_texts["utm-25"]
    assert "EXPEDITED_REVIEW_RESULT=verified" in skill_texts["utm-24"]
    assert "REVIEW_SUCCESS_NOTIFICATION=not_sent" in skill_texts["utm-24"]
    assert "REVIEW_SUCCESS_NOTIFICATION=sent" in skill_texts["utm-25"]
    assert "AUTOMATIC_REVIEW_APPROVAL=verified" in skill_texts["utm-24"]
    assert "source=automatic_self_check" in skill_texts["utm-24"]
    assert "automatically click `Allow` once" in skill_texts["utm-clash"]
    assert "No user confirmation or authorization is required" in skill_texts["utm-clash"]

    for relative_path in ("README.md", "AGENTS.md", "docs/utm-feishu-bot.md"):
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "自动" in text, relative_path
        assert "最后故障卡" in text, relative_path

    for stale in (
        "最终 `Change` 由用户确认并点击",
        "user-click checkpoint",
        "两次最终 `Submit` 都必须分别取得用户明确授权",
        "用户明确授权后",
        "用户明确提供",
        "用户对本次证书提交的明确授权",
        "用户对本次 W-8BEN 提交的明确授权",
        "keychain-auth-prompt",
        "apple-device-2fa",
        "change-password-generate-password",
        "computer-use/1.0.",
        "REQUIRED SUB-SKILL",
        "空值时回退",
        "or current-template `截图链接: `",
    ):
        assert stale not in canonical, stale

    for name in ("notion-utm-1", "utm-7", "utm-8", "utm-14", "utm-17", "utm-24", "utm-25"):
        text = skill_texts[name]
        assert "notify-fault" in text, name
        assert "wait-decision" in text, name
    assert "正常运行没有等待节点" in skill_texts["utm-24"]
    print("AUTOMATIC_SKILL_ACTIONS=verified")


if __name__ == "__main__":
    main()
