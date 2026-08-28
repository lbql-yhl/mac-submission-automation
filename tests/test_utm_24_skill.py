#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/utm-24/SKILL.md"
SESSION = ROOT / "scripts/session.mjs"
ENTRY = 'node "$PROJECT_ROOT/scripts/session.mjs" inspect'


def test_utm_24_skill_uses_the_existing_session_and_ends_the_workflow() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert skill.count(ENTRY) == 1
    for required in (
        "Only browser-session entry helper",
        "only attaches to and inspects the existing browser session",
        "There is no complete `utm-24` wrapper",
        "Never start or restart Edge",
        "UTM_23=verified",
        "inherited screenshots 02, 03, and 05",
        "01-media-manager.png",
        "04-privacy-agreement.png",
        "IAP_READY_FOR_REVIEW=<N>",
        "REVIEW_ITEMS_READY=<N+1>",
        "automatic self-check record",
        "one stable review-submit attempt",
        "click `Submit for Review` at most once",
        "one stable expedite attempt",
        "click `Send` at most once",
        "UTM_24=verified",
        "there is no next skill",
    ):
        assert required in skill, required
    for stale in (
        "Items Ready to Submit (15)",
        "14 IAP items",
        "ITEMS_READY=15",
        "15 Items Submitted",
    ):
        assert stale not in skill, stale


def test_session_identity_and_inspect_reject_browser_replacement() -> None:
    source = SESSION.read_text(encoding="utf-8")
    identity = source.split(
        "export async function currentSessionIdentity()", 1
    )[1].split("async function runShell", 1)[0]
    inspect_branch = source.split(
        '} else if (command === "inspect") {', 1
    )[1].split('} else if (command === "open") {', 1)[0]

    for required in (
        "state.sessionId !== liveSessionId",
        "state.pid !== pid",
        'edgeWebsocket.startsWith("ws://127.0.0.1:9222/")',
    ):
        assert required in identity, required
    assert "await inspectPages();" in inspect_branch
    assert "restartLocalBrowser" not in inspect_branch
