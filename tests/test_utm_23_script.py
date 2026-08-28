from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_utm_23_guest_script_is_valid_playwright_and_self_tests_dynamic_counts() -> None:
    script = ROOT / "scripts" / "utm_23_prepare_review.mjs"
    checked = subprocess.run(
        ["node", "--check", str(script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stderr

    tested = subprocess.run(
        ["node", str(script), "--self-test"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tested.returncode == 0, tested.stderr
    assert tested.stdout.strip() == (
        "UTM_23_SCRIPT=self-test-passed;IAP_COUNT=7;ITEMS_READY=8"
    )

    source = script.read_text(encoding="utf-8")
    assert 'new URL("./session.mjs", import.meta.url)' in source
    assert "connectLocalBrowser" in source
    assert "secureScreenshot" in source
    assert "Create New Submission" in source
    for forbidden in (
        "computer-use",
        "Accessibility",
        "ApplicationServices",
        "Quartz",
        "selenium",
        "subagent",
    ):
        assert forbidden not in source, forbidden


def test_browser_probe_classification_restarts_only_when_edge_is_absent() -> None:
    from scripts.utm_23 import BrowserProbe, UTM23Error, classify_browser_probe

    assert classify_browser_probe(
        BrowserProbe(process_count=0, cdp_available=False, identity=None)
    ) == "start_and_login"
    assert classify_browser_probe(
        BrowserProbe(
            process_count=1,
            cdp_available=True,
            identity={
                "edge_pid": 123,
                "edge_websocket": "ws://127.0.0.1:9222/devtools/browser/example",
                "sessionId": "example",
            },
        )
    ) == "reuse"

    for ambiguous in (
        BrowserProbe(process_count=1, cdp_available=False, identity=None),
        BrowserProbe(process_count=0, cdp_available=True, identity=None),
        BrowserProbe(process_count=2, cdp_available=True, identity=None),
    ):
        with pytest.raises(UTM23Error, match="EDGE_PROCESS_STATE_AMBIGUOUS"):
            classify_browser_probe(ambiguous)


def test_browser_probe_checks_cdp_independently_from_recorded_identity() -> None:
    from scripts.utm_23 import guest_browser_probe_command

    command = guest_browser_probe_command("abcd")
    assert "http://127.0.0.1:9222/json/version" in command
    assert "cdp_available = Boolean" in command
    assert "cdp_available: identity !== null" not in command


def test_edge_identity_requires_session_id_matching_the_websocket() -> None:
    from scripts.utm_23 import UTM23Error, _edge_identity

    valid = {
        "edge_pid": 123,
        "edge_websocket": "ws://127.0.0.1:9222/devtools/browser/existing",
        "sessionId": "existing",
    }
    assert _edge_identity(valid) == (
        123,
        "ws://127.0.0.1:9222/devtools/browser/existing",
    )

    for invalid in (
        {key: value for key, value in valid.items() if key != "sessionId"},
        {**valid, "sessionId": "replacement"},
        {**valid, "sessionId": ""},
    ):
        with pytest.raises(UTM23Error, match="EDGE_SESSION_RESULT_INVALID"):
            _edge_identity(invalid)


def test_absent_browser_recovery_starts_then_runs_utm10_once() -> None:
    from scripts.utm_23 import BrowserProbe, ensure_guest_browser

    calls: list[str] = []
    identity = (321, "ws://127.0.0.1:9222/devtools/browser/new")
    result = ensure_guest_browser(
        BrowserProbe(process_count=0, cdp_available=False, identity=None),
        start_browser=lambda: calls.append("start"),
        login_utm10=lambda: calls.append("utm-10") or identity,
    )
    assert result == identity
    assert calls == ["start", "utm-10"]

    calls.clear()
    reused = ensure_guest_browser(
        BrowserProbe(
            process_count=1,
            cdp_available=True,
            identity={
                "edge_pid": 123,
                "edge_websocket": "ws://127.0.0.1:9222/devtools/browser/existing",
                "sessionId": "existing",
            },
        ),
        start_browser=lambda: calls.append("start"),
        login_utm10=lambda: calls.append("utm-10") or identity,
    )
    assert reused == (123, "ws://127.0.0.1:9222/devtools/browser/existing")
    assert calls == []


def test_absent_browser_recovery_uses_the_fixed_utm10_edge_commands() -> None:
    source = (ROOT / "scripts" / "session.mjs").read_text(encoding="utf-8")
    launch = source.split(
        "const UTM10_EDGE_LAUNCH_SCRIPT = String.raw`", 1
    )[1].split("`;", 1)[0]

    assert launch == """pkill "Microsoft Edge"

nohup "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \\
  --remote-debugging-port=9222 \\
  --user-data-dir=/tmp/edge-debug-profile \\
  --no-first-run \\
  --start-maximized \\
  >/dev/null 2>&1 &
"""


def test_guest_result_parser_accepts_dynamic_iap_count_and_exact_screenshot_paths() -> None:
    from scripts.utm_23 import parse_guest_result

    run_id = "run-12345678"
    vm_user = "abcd"
    base = f"/Users/{vm_user}/Downloads/utm-23-review/{run_id}"
    result = {
        "UTM_23": "verified",
        "BUILD_ATTACHED": "verified",
        "EXPORT_COMPLIANCE_STATUS": "cleared",
        "GAME_CENTER_CHECKBOX": "unchecked",
        "VERSION_PAGE": "saved",
        "DRAFT_SUBMISSIONS": 1,
        "IAP_READY_FOR_REVIEW": 7,
        "REVIEW_ITEMS_READY": 8,
        "APP_VERSION_DRAFT_LINK": "verified",
        "APP_STORE_REGULATIONS_PERMITS": "empty",
        "APP_STORE_SERVER_NOTIFICATIONS": "empty",
        "REVIEW_SCREENSHOT_02": "verified",
        "REVIEW_SCREENSHOT_03": "verified",
        "SUBMIT_FOR_REVIEW": "not_clicked",
        "screenshot_02_path": f"{base}/02-iap-drafts.png",
        "screenshot_03_path": f"{base}/03-app-information.png",
    }
    identity = {
        "edge_pid": 123,
        "edge_websocket": "ws://127.0.0.1:9222/devtools/browser/example",
        "sessionId": "example",
    }
    parsed = parse_guest_result(
        f"{json.dumps(result)}\n{json.dumps(identity)}\n",
        vm_user=vm_user,
        run_id=run_id,
    )
    assert parsed.iap_count == 7
    assert parsed.items_ready == 8
    assert parsed.edge_identity == (
        123,
        "ws://127.0.0.1:9222/devtools/browser/example",
    )

    incomplete = dict(result)
    incomplete.pop("BUILD_ATTACHED")
    with pytest.raises(Exception, match="UTM_23_RESULT_INVALID"):
        parse_guest_result(
            f"{json.dumps(incomplete)}\n{json.dumps(identity)}\n",
            vm_user=vm_user,
            run_id=run_id,
        )


def test_delivery_helper_accepts_an_explicit_utm23_file_set(tmp_path: Path) -> None:
    from scripts.utm_apps_delivery import stage_playwright_files

    staged = stage_playwright_files(
        tmp_path,
        filenames=("session.mjs", "utm_10_login.mjs", "utm_23_prepare_review.mjs"),
    )
    assert set(staged) == {
        "session.mjs",
        "utm_10_login.mjs",
        "utm_23_prepare_review.mjs",
        "node_modules/playwright-core",
    }


def test_review_script_uses_exact_dynamic_iap_identities_and_item_count() -> None:
    source = (ROOT / "scripts" / "utm_23_prepare_review.mjs").read_text(
        encoding="utf-8"
    )

    for required in (
        "function iapIdentity",
        "Complete IAP row has an unsupported status",
        "const expectedIdentities =",
        "const finalIdentities =",
        "const draftIdentities =",
        "readyCount !== reviewItemsReady(iapItems.length)",
    ):
        assert required in source, required
    assert "readyCount < iapCount + 1" not in source
