#!/usr/bin/env python3
"""Prepare one exact App Store Connect review draft through guest Playwright."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping


SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from scripts.clean_cli import run_clean_cli  # noqa: E402
from scripts.notion_api import api_from_env  # noqa: E402
from scripts.ssh_password import connection_options, password_environment  # noqa: E402
from scripts.utm_apps import (  # noqa: E402
    _notion_payload,
    _registered_utm12_fields,
    _resolve_context,
    _session_from_result,
    _ssh_run,
    run_guest_stage,
    validate_target,
)
from scripts.utm_apps_delivery import sync_playwright_files  # noqa: E402
from services.project_paths import PROJECT_ROOT, SHARED_DIR  # noqa: E402


RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}")
VERSION_RE = re.compile(r"[0-9]+(?:\.[0-9]+)*")
BUILD_RE = re.compile(r"[1-9][0-9]*")
GUEST_DIR_TEMPLATE = "/Users/{vm_user}/Downloads/AppleAccountScriptsBackup"
GUEST_SCRIPT_NAME = "utm_23_prepare_review.mjs"
UTM23_GUEST_FILES = ("session.mjs", "utm_10_login.mjs", GUEST_SCRIPT_NAME)
GUEST_TIMEOUT_SECONDS = 900
SCREENSHOT_FILENAMES = ("02-iap-drafts.png", "03-app-information.png")


class UTM23Error(RuntimeError):
    """Raised when the scripted review workflow cannot be safely attributed."""


@dataclass(frozen=True)
class BrowserProbe:
    process_count: int
    cdp_available: bool
    identity: Mapping[str, Any] | None


@dataclass(frozen=True)
class UTM23Result:
    iap_count: int
    items_ready: int
    screenshot_02_path: str
    screenshot_03_path: str
    edge_identity: tuple[int, str]
    data: Mapping[str, Any]


@dataclass(frozen=True)
class ScreenshotEvidence:
    path: Path
    sha256: str


def _edge_identity(value: Mapping[str, Any] | None) -> tuple[int, str]:
    value = value or {}
    pid = value.get("edge_pid")
    websocket = value.get("edge_websocket")
    session_id = value.get("sessionId")
    if (
        not isinstance(pid, int)
        or isinstance(pid, bool)
        or pid <= 0
        or not isinstance(websocket, str)
        or not websocket.startswith("ws://127.0.0.1:9222/devtools/browser/")
        or not isinstance(session_id, str)
        or not session_id
        or websocket != f"ws://127.0.0.1:9222/devtools/browser/{session_id}"
    ):
        raise UTM23Error("EDGE_SESSION_RESULT_INVALID")
    return pid, websocket


def classify_browser_probe(probe: BrowserProbe) -> str:
    if probe.process_count == 0 and not probe.cdp_available and probe.identity is None:
        return "start_and_login"
    if probe.process_count == 1 and probe.cdp_available and probe.identity is not None:
        _edge_identity(probe.identity)
        return "reuse"
    raise UTM23Error("EDGE_PROCESS_STATE_AMBIGUOUS")


def ensure_guest_browser(
    probe: BrowserProbe,
    *,
    start_browser: Callable[[], Any],
    login_utm10: Callable[[], tuple[int, str]],
) -> tuple[int, str]:
    action = classify_browser_probe(probe)
    if action == "reuse":
        return _edge_identity(probe.identity)
    start_browser()
    return login_utm10()


def guest_script_path(vm_user: str, filename: str = GUEST_SCRIPT_NAME) -> str:
    if not re.fullmatch(r"[a-z]{4}", vm_user) or Path(filename).name != filename:
        raise UTM23Error("UTM_23_GUEST_PATH_INVALID")
    return f"{GUEST_DIR_TEMPLATE.format(vm_user=vm_user)}/{filename}"


def guest_browser_probe_command(vm_user: str) -> str:
    session = guest_script_path(vm_user, "session.mjs")
    source = "\n".join(
        (
            'import { execFileSync } from "node:child_process";',
            f'import {{ currentSessionIdentity }} from {json.dumps(f"file://{session}")};',
            "let pids = [];",
            "try { pids = execFileSync('/usr/bin/pgrep', ['-x', 'Microsoft Edge'], { encoding: 'utf8' }).split(/\\s+/).filter(Boolean); } catch {}",
            "let cdp_available = false;",
            "try { const response = await fetch('http://127.0.0.1:9222/json/version', { signal: AbortSignal.timeout(5000) }); const info = response.ok ? await response.json() : null; cdp_available = Boolean(String(info?.webSocketDebuggerUrl || '').startsWith('ws://127.0.0.1:9222/')); } catch {}",
            "let identity = null;",
            "try { identity = await currentSessionIdentity(); } catch {}",
            "console.log(JSON.stringify({ process_count: pids.length, cdp_available, identity }));",
        )
    )
    return shlex.join(("node", "--input-type=module", "-e", source))


def parse_browser_probe(stdout: bytes | str) -> BrowserProbe:
    text = stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else stdout
    try:
        payload = json.loads(text.strip())
    except (TypeError, ValueError) as error:
        raise UTM23Error("EDGE_PROCESS_PROBE_INVALID") from error
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("process_count"), int)
        or isinstance(payload.get("process_count"), bool)
        or payload["process_count"] < 0
        or not isinstance(payload.get("cdp_available"), bool)
        or (payload.get("identity") is not None and not isinstance(payload["identity"], dict))
    ):
        raise UTM23Error("EDGE_PROCESS_PROBE_INVALID")
    return BrowserProbe(
        process_count=payload["process_count"],
        cdp_available=payload["cdp_available"],
        identity=payload.get("identity"),
    )


def probe_guest_browser(
    *,
    vm_ip: str,
    vm_user: str,
    runner: Callable[..., Any] = subprocess.run,
    password_env: Mapping[str, str] | None = None,
) -> BrowserProbe:
    completed = _ssh_run(
        vm_user,
        vm_ip,
        guest_browser_probe_command(vm_user),
        input_bytes=b"",
        timeout=15,
        runner=runner,
        password_env=password_env,
    )
    if completed.returncode != 0:
        raise UTM23Error("EDGE_PROCESS_PROBE_FAILED")
    return parse_browser_probe(completed.stdout)


def start_guest_browser(
    *,
    vm_ip: str,
    vm_user: str,
    runner: Callable[..., Any] = subprocess.run,
    password_env: Mapping[str, str] | None = None,
) -> None:
    session = guest_script_path(vm_user, "session.mjs")
    completed = _ssh_run(
        vm_user,
        vm_ip,
        shlex.join(("node", session, "start")),
        input_bytes=b"",
        timeout=30,
        runner=runner,
        password_env=password_env,
    )
    if completed.returncode != 0:
        raise UTM23Error("EDGE_PROCESS_START_FAILED")
    try:
        payload = json.loads(
            completed.stdout.decode("utf-8")
            if isinstance(completed.stdout, bytes)
            else completed.stdout
        )
    except (TypeError, ValueError) as error:
        raise UTM23Error("EDGE_PROCESS_START_RESULT_INVALID") from error
    if payload.get("verified") is not True:
        raise UTM23Error("EDGE_PROCESS_START_RESULT_INVALID")


def guest_execution_command(vm_user: str) -> str:
    target = guest_script_path(vm_user)
    base = str(Path(target).parent)
    identity_probe = (
        "import { currentSessionIdentity } from "
        f"{json.dumps(f'file://{base}/session.mjs')};"
        "console.log(JSON.stringify(await currentSessionIdentity()))"
    )
    node_stage = "\n".join(
        (
            "set -euo pipefail",
            "set +e",
            shlex.join(
                (
                    "/usr/bin/perl",
                    "-e",
                    "alarm shift; exec @ARGV",
                    str(GUEST_TIMEOUT_SECONDS),
                    "node",
                    target,
                )
            ),
            "stage_status=$?",
            "set -e",
            f'if [[ "$stage_status" -eq 142 ]]; then print -u2 -- "UTM_23_ERROR=TIMEOUT_{GUEST_TIMEOUT_SECONDS}_SECONDS"; fi',
            'if [[ "$stage_status" -ne 0 ]]; then exit "$stage_status"; fi',
            shlex.join(("node", "--input-type=module", "-e", identity_probe)),
        )
    )
    script = "\n".join(
        (
            "set -euo pipefail",
            f"expected_user={shlex.quote(vm_user)}",
            f"base={shlex.quote(base)}",
            f"target={shlex.quote(target)}",
            '[[ "$(/usr/bin/id -un)" == "$expected_user" ]]',
            '[[ "$HOME" == "/Users/$expected_user" ]]',
            '[[ -d "$base" && ! -L "$base" ]]',
            '[[ -f "$target" && ! -L "$target" && -O "$target" && -s "$target" ]]',
            f"exec /bin/zsh -lic {shlex.quote(node_stage)}",
        )
    )
    return shlex.join(("/bin/zsh", "-lc", script))


def parse_guest_result(
    stdout: bytes | str, *, vm_user: str, run_id: str
) -> UTM23Result:
    text = stdout.decode("utf-8", errors="replace") if isinstance(stdout, bytes) else stdout
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != 2:
        raise UTM23Error("UTM_23_RESULT_LINE_COUNT_INVALID")
    try:
        result = json.loads(lines[0])
        identity = json.loads(lines[1])
    except (TypeError, ValueError) as error:
        raise UTM23Error("UTM_23_RESULT_JSON_INVALID") from error
    if not isinstance(result, dict) or not isinstance(identity, dict):
        raise UTM23Error("UTM_23_RESULT_SHAPE_INVALID")
    iap_count = result.get("IAP_READY_FOR_REVIEW")
    items_ready = result.get("REVIEW_ITEMS_READY")
    expected_base = f"/Users/{vm_user}/Downloads/utm-23-review/{run_id}"
    screenshot_02 = result.get("screenshot_02_path")
    screenshot_03 = result.get("screenshot_03_path")
    required = {
        "UTM_23": "verified",
        "BUILD_ATTACHED": "verified",
        "EXPORT_COMPLIANCE_STATUS": "cleared",
        "GAME_CENTER_CHECKBOX": "unchecked",
        "VERSION_PAGE": "saved",
        "DRAFT_SUBMISSIONS": 1,
        "APP_VERSION_DRAFT_LINK": "verified",
        "APP_STORE_REGULATIONS_PERMITS": "empty",
        "APP_STORE_SERVER_NOTIFICATIONS": "empty",
        "REVIEW_SCREENSHOT_02": "verified",
        "REVIEW_SCREENSHOT_03": "verified",
        "SUBMIT_FOR_REVIEW": "not_clicked",
    }
    if (
        any(result.get(key) != value for key, value in required.items())
        or not isinstance(iap_count, int)
        or isinstance(iap_count, bool)
        or iap_count < 1
        or items_ready != iap_count + 1
        or screenshot_02 != f"{expected_base}/02-iap-drafts.png"
        or screenshot_03 != f"{expected_base}/03-app-information.png"
    ):
        raise UTM23Error("UTM_23_RESULT_INVALID")
    return UTM23Result(
        iap_count=iap_count,
        items_ready=items_ready,
        screenshot_02_path=screenshot_02,
        screenshot_03_path=screenshot_03,
        edge_identity=_edge_identity(identity),
        data=result,
    )


def run_guest_workflow(
    *,
    vm_ip: str,
    vm_user: str,
    payload: Mapping[str, Any],
    run_id: str,
    runner: Callable[..., Any] = subprocess.run,
    password_env: Mapping[str, str] | None = None,
) -> UTM23Result:
    completed = _ssh_run(
        vm_user,
        vm_ip,
        guest_execution_command(vm_user),
        input_bytes=json.dumps(
            dict(payload), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8"),
        timeout=GUEST_TIMEOUT_SECONDS + 10,
        runner=runner,
        password_env=password_env,
    )
    if completed.returncode != 0:
        raise UTM23Error("UTM_23_GUEST_WORKFLOW_FAILED")
    return parse_guest_result(completed.stdout, vm_user=vm_user, run_id=run_id)


def copy_review_screenshot(
    *,
    vm_ip: str,
    vm_user: str,
    remote_path: str,
    run_id: str,
    filename: str,
    scp_runner: Callable[..., Any] = subprocess.run,
    password_env: Mapping[str, str] | None = None,
) -> ScreenshotEvidence:
    if not RUN_ID_RE.fullmatch(run_id) or filename not in SCREENSHOT_FILENAMES:
        raise UTM23Error("SCREENSHOT_IDENTITY_INVALID")
    expected_remote = f"/Users/{vm_user}/Downloads/utm-23-review/{run_id}/{filename}"
    if remote_path != expected_remote:
        raise UTM23Error("SCREENSHOT_REMOTE_PATH_MISMATCH")
    screenshot_root = (PROJECT_ROOT / "runtime" / "review-screenshots").resolve()
    target_dir = (screenshot_root / run_id).resolve()
    if target_dir.parent != screenshot_root:
        raise UTM23Error("SCREENSHOT_TARGET_ESCAPED")
    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target_dir.chmod(0o700)
    target = target_dir / filename
    environment = dict(password_env) if password_env is not None else password_environment()
    with tempfile.NamedTemporaryFile(
        dir=target_dir, prefix=f".{filename}.", delete=False
    ) as handle:
        temporary = Path(handle.name)
    try:
        copied = scp_runner(
            [
                "/usr/bin/scp",
                "-q",
                *connection_options(8),
                f"{vm_user}@{vm_ip}:{remote_path}",
                str(temporary),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=environment,
        )
        if copied.returncode != 0:
            raise UTM23Error("SCREENSHOT_COPY_FAILED")
        payload = temporary.read_bytes()
        if not payload.startswith(b"\x89PNG\r\n\x1a\n") or len(payload) < 100:
            raise UTM23Error("SCREENSHOT_PNG_INVALID")
        temporary.chmod(0o600)
        os.replace(temporary, target)
        target.chmod(0o600)
        if target.stat().st_mode & 0o777 != 0o600:
            raise UTM23Error("SCREENSHOT_MODE_INVALID")
        return ScreenshotEvidence(target, hashlib.sha256(payload).hexdigest())
    finally:
        temporary.unlink(missing_ok=True)


def _validate_version_build(version: str, build_number: str) -> tuple[str, str]:
    version = str(version or "").strip()
    build_number = str(build_number or "").strip()
    if not VERSION_RE.fullmatch(version) or not BUILD_RE.fullmatch(build_number):
        raise UTM23Error("APP_VERSION_BUILD_INVALID")
    return version, build_number


def run(
    args: argparse.Namespace,
    *,
    api: Any | None = None,
    runner: Callable[..., Any] = subprocess.run,
    scp_runner: Callable[..., Any] = subprocess.run,
    password_env: Mapping[str, str] | None = None,
) -> int:
    validate_target(args.vm_name, args.vm_ip, args.vm_user)
    version, build_number = _validate_version_build(args.app_version, args.build_number)
    notion = api if api is not None else api_from_env()
    _direct, context_id, parent_title, page_title, expected_app_name = _resolve_context(args)
    if not RUN_ID_RE.fullmatch(context_id):
        raise UTM23Error("RUN_ID_INVALID")
    notion.verify_parent(parent_title)
    payload: dict[str, Any] = _notion_payload(notion, page_title)
    registered = _registered_utm12_fields(notion, page_title)
    if not registered:
        raise UTM23Error("NOTION_APP_ID_MISSING")
    if page_title != f"{payload['APP_NAME']}-{args.vm_user}":
        raise UTM23Error("NOTION_PAGE_IDENTITY_MISMATCH")
    if payload["APP_NAME"] != expected_app_name:
        raise UTM23Error("NOTION_PAGE_APP_MISMATCH")

    sync_playwright_files(
        SHARED_DIR,
        vm_user=args.vm_user,
        vm_ip=args.vm_ip,
        filenames=UTM23_GUEST_FILES,
    )
    probe = probe_guest_browser(
        vm_ip=args.vm_ip,
        vm_user=args.vm_user,
        runner=runner,
        password_env=password_env,
    )

    def start() -> None:
        start_guest_browser(
            vm_ip=args.vm_ip,
            vm_user=args.vm_user,
            runner=runner,
            password_env=password_env,
        )

    def login() -> tuple[int, str]:
        login_payload = dict(payload)
        login_payload["UTM_10_REUSE_EXISTING_EDGE"] = True
        result = run_guest_stage(
            stage="utm-10",
            vm_name=args.vm_name,
            vm_ip=args.vm_ip,
            vm_user=args.vm_user,
            payload=login_payload,
            runner=runner,
            password_env=password_env,
        )
        return _session_from_result(result)

    initial_identity = ensure_guest_browser(
        probe, start_browser=start, login_utm10=login
    )
    workflow_payload = {
        "RUN_ID": context_id,
        "APP_NAME": payload["APP_NAME"],
        "APP_ID": registered["numeric_app_id"],
        "BUNDLE_ID": payload["BUNDLE_ID"],
        "APP_VERSION": version,
        "BUILD_NUMBER": build_number,
    }
    result = run_guest_workflow(
        vm_ip=args.vm_ip,
        vm_user=args.vm_user,
        payload=workflow_payload,
        run_id=context_id,
        runner=runner,
        password_env=password_env,
    )
    if result.edge_identity != initial_identity:
        raise UTM23Error("EDGE_PROCESS_CHANGED")
    screenshot_02 = copy_review_screenshot(
        vm_ip=args.vm_ip,
        vm_user=args.vm_user,
        remote_path=result.screenshot_02_path,
        run_id=context_id,
        filename="02-iap-drafts.png",
        scp_runner=scp_runner,
        password_env=password_env,
    )
    screenshot_03 = copy_review_screenshot(
        vm_ip=args.vm_ip,
        vm_user=args.vm_user,
        remote_path=result.screenshot_03_path,
        run_id=context_id,
        filename="03-app-information.png",
        scp_runner=scp_runner,
        password_env=password_env,
    )
    if screenshot_02.sha256 == screenshot_03.sha256:
        raise UTM23Error("REVIEW_SCREENSHOT_HASH_CONFLICT")
    print(f"IAP_READY_FOR_REVIEW={result.iap_count}")
    print(f"REVIEW_ITEMS_READY={result.items_ready}")
    print("DRAFT_SUBMISSIONS=1")
    print("REVIEW_SCREENSHOT_02=verified")
    print("REVIEW_SCREENSHOT_03=verified")
    print("SUBMIT_FOR_REVIEW=not_clicked")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the complete scripted UTM-23 workflow")
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--run-id")
    selector.add_argument("--page-title")
    parser.add_argument("--vm-name", required=True)
    parser.add_argument("--vm-ip", required=True)
    parser.add_argument("--vm-user", required=True)
    parser.add_argument("--app-version", required=True)
    parser.add_argument("--build-number", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return run_clean_cli(
        skill_name="utm-23",
        success_marker="UTM_23=verified",
        operation=lambda: run(args),
        preserve_error_detail=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
