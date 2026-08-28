#!/usr/bin/env python3
from pathlib import Path

import pytest

from scripts import utm_apps


ROOT = Path(__file__).resolve().parents[1]
ENTRY = "$PROJECT_ROOT/scripts/utm_apps.py"


def test_utm_apps_skill_publishes_one_portable_entry_and_handoff() -> None:
    skill = (ROOT / "skills/utm-apps/SKILL.md").read_text(encoding="utf-8")

    assert skill.count(ENTRY) == 1
    for required in (
        "Only public host entry",
        "--run-id '<run-id>'",
        "--page-title '<page-title>'",
        "UTM-10 through UTM-13",
        "05-small-business.png",
        "UTM_APPS=verified",
        "utm-business",
    ):
        assert required in skill, required
    for internal_entry in utm_apps.GUEST_WRAPPERS.values():
        assert internal_entry not in skill
    assert "/Users/" not in skill


def test_utm_apps_entry_owns_all_stages_and_rejects_session_changes() -> None:
    assert utm_apps.GUEST_WRAPPERS == {
        "utm-10": "utm_10_login.mjs",
        "utm-11": "utm_11_one.mjs",
        "utm-12": "utm_12_one.mjs",
        "utm-13": "utm_13_one.mjs",
    }
    assert utm_apps.STAGE_MARKERS["utm-11"] == (
        "UTM_11=verified",
        "SMALL_BUSINESS_SUCCESS_MESSAGES=verified",
        "REVIEW_SCREENSHOT_05=verified",
    )
    result = utm_apps.GuestWorkflowResult(
        markers=(),
        data={
            "edge_pid": 123,
            "edge_websocket": "ws://127.0.0.1:9222/devtools/browser/session-a",
        },
    )

    assert utm_apps._session_from_result(result) == (
        123,
        "ws://127.0.0.1:9222/devtools/browser/session-a",
    )
    with pytest.raises(utm_apps.AppleWebError, match="EDGE_PROCESS_CHANGED"):
        utm_apps._assert_same_session(
            result,
            (124, "ws://127.0.0.1:9222/devtools/browser/session-b"),
        )
