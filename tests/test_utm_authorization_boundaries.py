#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills"


def sources_for(skill_name: str) -> str:
    paths = (
        SKILL_ROOT / skill_name / "SKILL.md",
        ROOT / f"docs/{skill_name}.md",
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "docs/utm-feishu-bot.md",
    )
    return "\n".join(path.read_text(encoding="utf-8") for path in paths if path.exists())


def main() -> None:
    utm_8 = sources_for("utm-8")
    assert "自动点击一次最终 `Change`/`Continue`" in utm_8
    assert "重填验证通过后再次自动点击一次最终 `Change`/`Continue`" in utm_8

    utm_14 = sources_for("utm-14")
    assert "自动点击一次" in utm_14
    assert "不等待用户确认" in utm_14

    utm_20 = sources_for("utm-20")
    assert "自动勾选条款并只点击一次 `Add`" in utm_20
    assert "2FA 出现后自动继续短信验证" in utm_20

    utm_24 = sources_for("utm-24")
    assert "record-auto-review-approval" in utm_24
    assert "source=automatic_self_check" in utm_24
    assert "notify-review" not in (SKILL_ROOT / "utm-24" / "SKILL.md").read_text(encoding="utf-8")
    assert "--decision-kind review_submit" not in utm_24
    assert "AUTOMATIC_REVIEW_APPROVAL=verified" in utm_24
    assert "notify-review-success" not in (SKILL_ROOT / "utm-24" / "SKILL.md").read_text(encoding="utf-8")
    assert "只点击一次 `Send`" in utm_24

    utm_25 = sources_for("utm-25")
    assert "notify-review-success" in utm_25
    assert "不得点击 `Submit for Review`" in utm_25
    assert "不得点击加急页 `Send`" in utm_25

    combined = "\n".join((utm_8, utm_14, utm_20, utm_24, utm_25))
    for stale in (
        "最终 `Change` 由用户确认并点击",
        "用户完成该点击",
        "user-click checkpoint",
        "两次最终 `Submit` 都必须分别取得用户明确授权",
        "用户对本次证书提交的明确授权",
        "用户对本次 W-8BEN 提交的明确授权",
        "只有用户明确授权同意条款并新增银行账户后",
        "只有用户明确要求使用前面技能相同的短信验证方法后",
    ):
        assert stale not in combined, stale
    print("UTM_AUTHORIZATION_BOUNDARIES=verified")


if __name__ == "__main__":
    main()
