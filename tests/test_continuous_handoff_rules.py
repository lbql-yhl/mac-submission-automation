#!/usr/bin/env python3
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills"


def read_skill(name: str) -> str:
    return (SKILL_ROOT / name / "SKILL.md").read_text(encoding="utf-8")


def main() -> None:
    run_specific_values = ("rhnz", "Xrimo", "Jan Haren", "NXTKR5YYHJ", "1.0 Ready for Review")

    utm_2 = read_skill("utm-2")
    assert "only when that skill explicitly delegates SSH recovery" in utm_2
    assert "SSH_EXIT=255" in utm_2
    assert "return to this repair procedure before retrying the later command" not in utm_2

    utm_4 = read_skill("utm-4")
    assert "Only if the inherited connection is unreachable" in utm_4
    assert "or re-find it" not in utm_4

    vm_down = read_skill("vm-down")
    assert "rhnz" not in vm_down

    utm_16 = read_skill("utm-16")
    utm_16_doc = (ROOT / "docs/utm-16.md").read_text(encoding="utf-8")
    for text in (utm_16, utm_16_doc):
        assert "直接继承 `utm-15`" in text
        assert "只有继承 IP 不可达" in text
        assert "utmctl list" not in text

    assert "rhnz" not in read_skill("utm-19")

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    current_line = next(line for line in agents.splitlines() if line.startswith("- Current important skills in order:"))
    for skill_name in re.findall(r"`([^`]+)`", current_line):
        skill_text = read_skill(skill_name)
        for stale in run_specific_values:
            assert stale not in skill_text, f"{skill_name}: stale {stale}"

    for doc in (ROOT / "docs").glob("utm-*.md"):
        doc_text = doc.read_text(encoding="utf-8")
        for stale in run_specific_values:
            assert stale not in doc_text, f"{doc}: stale {stale}"

    for source in (ROOT / "README.md", ROOT / "docs/utm-feishu-bot.md"):
        text = source.read_text(encoding="utf-8")
        assert (
            "后续技能自身的恢复边界优先" in text
            or "后续技能自身的业务 attempt 边界优先" in text
        )
        assert "SSH 不通时先由 `utm-2`" not in text
        assert "SSH 不通时由 `utm-2` 自动" not in text
        utm_16_summary = next(
            line for line in text.splitlines() if line.startswith("22. `utm-16`") or line.startswith("- `utm-16`")
        )
        assert "直接继承 `utm-15`" in utm_16_summary
        assert "确认匹配 VM/IP/SSH 用户" not in utm_16_summary
        assert "再确认 VM/IP/SSH 用户" not in utm_16_summary

    utm_16_order = next(line for line in agents.splitlines() if line.startswith("  23. `utm-16`"))
    assert "directly inherit the current VM/IP/SSH identity from `utm-15`" in utm_16_order
    assert "identify the matching started VM and SSH user" not in utm_16_order

    ordered = (
        "notion-utm", "notion-utm-1", "utm-clone-macos", "utm-1", "utm-2", "utm-3",
        "vm-down", "utm-4", "utm-5", "files", "utm-clash", "utm-6", "utm-7", "utm-8",
        "utm-9", "utm-10", "utm-11", "utm-12", "utm-13", "utm-14", "utm-15", "utm-16",
        "utm-17", "utm-18", "utm-19", "utm-20", "utm-21", "utm-22", "utm-23", "utm-24", "utm-25",
    )
    markers = (
        "NOTION_UTM=verified", "NOTION_UTM_1=verified", "UTM_CLONE_MACOS=verified",
        "UTM_1=verified", "UTM_2=verified", "UTM_3=verified", "VM_DOWN=verified",
        "UTM_4=verified", "UTM_5=verified", "FILES=verified", "UTM_CLASH=verified",
        "UTM_6=verified", "UTM_7=verified", "UTM_8=verified", "UTM_9=verified",
        "UTM_10=verified", "UTM_11=verified", "UTM_12=verified", "UTM_13=verified",
        "UTM_14=verified", "UTM_15=verified", "UTM_16=verified", "UTM_17=verified",
        "UTM_18=verified", "UTM_19=verified", "UTM_20=verified", "UTM_21=verified",
        "UTM_22=verified", "UTM_23=verified", "UTM_24=verified", "UTM_25=verified",
    )
    assert len(ordered) == len(markers) == 31
    assert len(set(ordered)) == 31
    current_skills = tuple(re.findall(r"`([^`]+)`", current_line))
    assert current_skills == ordered

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_order = tuple(
        match.group(1)
        for match in re.finditer(r"(?m)^\d+\. `([^`]+)`：", readme)
    )
    assert readme_order == ordered

    bot_doc = (ROOT / "docs/utm-feishu-bot.md").read_text(encoding="utf-8")
    bot_doc_order = tuple(
        match.group(1)
        for match in re.finditer(r"(?m)^→ ((?:notion|utm|vm|files)[a-z0-9-]*)$", bot_doc)
    )
    assert bot_doc_order == ordered

    success_command_owners = tuple(
        name for name in ordered if "feishu_bot.py notify-review-success" in read_skill(name)
    )
    review_command_owners = tuple(
        name
        for name in ordered
        if re.search(r"feishu_bot\.py notify-review(?:\s|`)", read_skill(name))
    )
    automatic_review_owners = tuple(
        name for name in ordered if "record-auto-review-approval" in read_skill(name)
    )
    assert success_command_owners == ("utm-25",)
    assert review_command_owners == ()
    assert automatic_review_owners == ("utm-24",)
    for index, (name, marker) in enumerate(zip(ordered, markers)):
        text = read_skill(name)
        assert marker in text, f"{name}: missing {marker}"
        if index < len(ordered) - 1:
            assert f"`{ordered[index + 1]}`" in text, f"{name}: missing handoff to {ordered[index + 1]}"
        else:
            assert "最终技能" in text and "不再调用或交接其他技能" in text

    print("CONTINUOUS_HANDOFF_RULES=verified")


if __name__ == "__main__":
    main()
