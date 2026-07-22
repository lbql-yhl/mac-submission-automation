#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.preflight import ORDERED  # noqa: E402


SKILLS = ROOT / "skills"


def completion_marker(name: str) -> str:
    return f"{name.replace('-', '_').upper()}=verified"


def main() -> None:
    assert len(ORDERED) == len(set(ORDERED)) == 31

    shared = (SKILLS / "_shared" / "AUTOMATION_CONTRACT.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for required in (
        "## 技能正文的详细步骤验收",
        "输入来源",
        "精确动作",
        "动作后复验",
        "成功标记",
        "连续交接",
    ):
        assert required in shared, required
    assert "技能详细正文硬规则" in agents

    utm_5 = (SKILLS / "utm-5" / "SKILL.md").read_text(encoding="utf-8")
    assert "SOCKS5_OUTPUT=verified" in utm_5
    assert 'Path.home() / "Desktop" / "共享文件"' not in utm_5

    clone = (SKILLS / "utm-clone-macos" / "SKILL.md").read_text(encoding="utf-8")
    assert 'Path(f"${SUBMISSION_VM_IMAGES_DIR}' not in clone
    assert "CLONE_MARKER=verified" in clone

    utm_2 = (SKILLS / "utm-2" / "SKILL.md").read_text(encoding="utf-8")
    assert 'public_key="${SUBMISSION_SSH_PUBLIC_KEY}"' in utm_2
    assert 'private_key="${SUBMISSION_SSH_PRIVATE_KEY}"' in utm_2
    assert 'IdentitiesOnly=yes -i "$private_key"' in utm_2
    assert '|192\\.168\\.64' not in utm_2
    assert "IOPlatformSerialNumber|IOPlatformUUID|IOPlatformUUID" not in utm_2
    assert "精确两行" in utm_2

    forbidden_direct_faults = (
        "立即向当前 run 的原 `chat_id` 发送 `notify-fault`",
        "属于异常故障：向当前 run 原 `chat_id` 发送 `notify-fault`",
        "is an abnormal fault and uses `notify-fault`/`wait-decision`",
        "is an abnormal fault: send `notify-fault`",
        "只有新的 `manual_continue` 才允许",
        "仅新的 `manual_continue` 允许",
        "only a fresh `manual_continue` permits",
    )

    for index, name in enumerate(ORDERED):
        text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        numbered_steps = re.findall(r"(?m)^\s*(?:\d+\.|#{2,3}\s+\d+[.\u3001])", text)

        assert "../_shared/AUTOMATION_CONTRACT.md" in text, name
        assert "## 本技能自动恢复矩阵" in text, name
        assert "`--recovery-result unrepairable` 必须同时追加 `--unrepairable`" in text, name
        assert len(numbered_steps) >= 3, f"{name}: executable numbered steps missing"
        assert completion_marker(name) in text, f"{name}: completion marker missing"
        assert any(word in text for word in ("确认", "验证", "核对", "回读", "verify")), name
        assert any(
            word in text
            for word in ("阻断", "Guardrails", "Hard Rules", "硬性规则", "异常故障条件")
        ), name

        if index + 1 < len(ORDERED):
            assert ORDERED[index + 1] in text, f"{name}: next-skill handoff missing"
        else:
            assert "最终技能" in text and "不再调用或交接其他技能" in text

        for forbidden in forbidden_direct_faults:
            assert forbidden not in text, f"{name}: direct fault-card shortcut: {forbidden}"

    print("DETAILED_SKILL_CONTRACT=verified")


if __name__ == "__main__":
    main()
