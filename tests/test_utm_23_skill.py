#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/utm-23/SKILL.md"
ENTRY = 'python3 "$PROJECT_ROOT/scripts/utm_23.py"'


def test_utm_23_skill_publishes_one_complete_script_entry_and_hands_off_to_utm_24() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert len(skill.splitlines()) <= 55
    assert skill.count(ENTRY) == 1
    for required in (
        "Only public host entry",
        "owns the complete App Store Connect browser workflow",
        "scripts/session.mjs",
        "scripts/utm_10_login.mjs",
        "scripts/utm_23_prepare_review.mjs",
        "node '<guest>/session.mjs' start",
        "EDGE_PROCESS=absent",
        "UTM_10=verified",
        "VISUAL_BROWSER_CONTROL=forbidden",
        "SUBAGENT_BROWSER_CONTROL=forbidden",
        "UTM_22=verified",
        "BUILD_UPLOAD_FINAL_STATE=COMPLETE",
        "BUILD_PROCESSING_STATE=VALID",
        "DRAFT_SUBMISSIONS=1",
        "IAP_READY_FOR_REVIEW=<N>",
        "REVIEW_ITEMS_READY=<N+1>",
        "02-iap-drafts.png",
        "03-app-information.png",
        "SUBMIT_FOR_REVIEW=not_clicked",
        "UTM_23=verified",
        "utm-24",
    ):
        assert required in skill, required
    for stale in (
        'node "$PROJECT_ROOT/scripts/session.mjs" inspect',
        "There is no complete `utm-23` wrapper",
        "exactly 14 IAP",
        "14 IAP items",
        "IAP_READY_FOR_REVIEW=14",
        "## Browser recovery",
        "## Scripted workflow",
        "The entry resumes idempotently",
    ):
        assert stale not in skill, stale
