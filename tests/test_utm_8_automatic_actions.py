#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    ROOT / "skills/utm-8/SKILL.md",
    ROOT / "docs/utm-8.md",
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "docs/utm-feishu-bot.md",
)


def main() -> None:
    combined = "\n".join(source.read_text(encoding="utf-8") for source in SOURCES)
    assert "自动点击一次最终 `Change`/`Continue`" in combined
    assert "重填验证通过后再次自动点击一次最终 `Change`/`Continue`" in combined
    assert "UTM_8=verified" in combined
    for forbidden in (
        "最终 `Change` 由用户确认并点击",
        "不得代替用户激活",
        "用户完成该点击",
        "user-click checkpoint",
        "change-password-generate-password",
    ):
        assert forbidden not in combined, forbidden
    print("UTM_8_AUTOMATIC_ACTIONS=verified")


if __name__ == "__main__":
    main()
