#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/utm-p8/SKILL.md"


def test_utm_p8_uses_only_the_host_entry_in_the_skill_contract() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    for required in (
        "$PROJECT_ROOT/scripts/utm_p8.py",
        "UTM_P8=verified",
        "SHARED_APP_ASSETS_CLEANED=verified",
        "--cleanup-only",
        "omit `--vm-ip`/`--vm-user`",
        "hand the same verified context to `utm-21`",
        "../_shared/AUTOMATION_CONTRACT.md",
    ):
        assert required in skill, required

    for forbidden in (
        "Team Keys",
        "appstoreconnect.apple.com/access/integrations/api",
        "ACTIVE_API_KEY_COUNT",
        "notify-review-success",
        "REVIEW_SUCCESS_NOTIFICATION",
        "随机哨兵",
        "完整 Downloads",
        "第一条",
    ):
        assert forbidden not in skill, forbidden


def test_utm_p8_is_a_single_script_entry() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    assert skill.count("$PROJECT_ROOT/scripts/utm_p8.py") == 1
    assert "Only public host entry" in skill
    assert "stop at the segment boundary" in skill
    assert "python3 -c" not in skill
    assert "ssh " not in skill
