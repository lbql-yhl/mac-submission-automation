#!/usr/bin/env python3
"""Complete UTM-18 in one resumable host entry."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.notion_api import api_from_env  # noqa: E402
from scripts.clean_cli import run_clean_cli  # noqa: E402
from scripts.utm_18_attempt import (  # noqa: E402
    AttemptResult,
    UTM18AttemptError,
    archive_retryable_attempt,
    classify_attempt,
    create_attempt,
    inspect_remote,
    is_retryable_finished_attempt,
    load_single_attempt,
    mark_attempt,
    precommit_remote,
    run_remote,
)
from scripts.utm_18_edge import UTM18EdgeError, prepare_edge  # noqa: E402
from scripts.utm_18_ssh import build_invocation  # noqa: E402
from scripts.utm_18_skip_iap import prepare_guest_skip_iap  # noqa: E402
from scripts.utm_18_existing import run_existing_browser  # noqa: E402
from scripts.utm_apps import (  # noqa: E402
    AppleWebError,
    run_guest_stage,
    verify_guest_scripts,
)
from scripts.utm_direct_context import resolve_direct_context  # noqa: E402
from services.feishu_bot import find_run, load_config, run_host_machine  # noqa: E402
from services.host_config import optional_setting  # noqa: E402


DEFAULT_ATTEMPTS_ROOT = PROJECT_ROOT / "runtime" / "utm-18-attempts"
APPLE_LOGIN_DIAGNOSTIC = PROJECT_ROOT / "runtime" / "utm-18-apple-login.stderr"
GUEST_HELPER_DIR = "/Users/{vm_user}/Downloads/AppleAccountScriptsBackup"
FILL_DESCRIPTION_WAIT_SECONDS = 3600
FILL_DESCRIPTION_POLL_SECONDS = 5
EDGE_PROCESS_PROBE = (
    "/usr/bin/pgrep -f "
    "'/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge' "
    ">/dev/null"
)

APPLE_LOGIN_BRIDGE = r'''import json,pathlib,sys
base=pathlib.Path(sys.argv[1])
required=(base/"apple_web_workflow.py",base/"edge_accessibility.py")
if not base.is_dir() or base.is_symlink() or not all(path.is_file() and not path.is_symlink() and path.stat().st_size>0 for path in required): raise SystemExit(61)
sys.path.insert(0,str(base))
payload=json.load(sys.stdin)
from apple_web_workflow import ACCOUNT_URL,_ensure_apple_login
from edge_accessibility import EdgeAXBackend,edge_session_identity
backend=EdgeAXBackend()
before=edge_session_identity(backend.pid)
backend.open_url(ACCOUNT_URL)
_ensure_apple_login(backend,payload)
after=edge_session_identity(backend.pid)
if before != after: raise SystemExit(62)
print(json.dumps({"markers":["APPLE_DEVELOPER_ACCOUNT=verified"],"edge_pid":after[0],"edge_websocket":after[1]}))
'''

APPLE_EXISTING_SESSION_BRIDGE = r'''const moduleUrl = process.argv[1];
const allowed = new Set([
  "EDGE_SESSION_IDENTITY_INVALID",
  "APPLE_ACCOUNT_PAGE_COUNT_INVALID",
  "APPLE_ACCOUNT_PAGE_READ_FAILED",
  "APPLE_ACCOUNT_MEMBERSHIP_MARKER_INVALID",
  "APPLE_BUSINESS_SESSION_MARKER_INVALID",
  "EDGE_SESSION_CHANGED",
  "PROBE_INTERNAL_ERROR",
]);
const fail = (code) => { throw new Error(code); };
try {
  const session = await import(moduleUrl);
  let before;
  try {
    before = await session.currentSessionIdentity();
  } catch {
    fail("EDGE_SESSION_IDENTITY_INVALID");
  }
  let connected;
  try {
    connected = await session.connectLocalBrowser();
  } catch {
    fail("EDGE_SESSION_IDENTITY_INVALID");
  }
  const accountPages = connected.context.pages().filter((page) => {
    try {
      const url = new URL(page.url());
      return url.protocol === "https:" &&
        url.hostname === "developer.apple.com" &&
        ["/account", "/account/"].includes(url.pathname);
    } catch {
      return false;
    }
  });
  if (accountPages.length > 1) fail("APPLE_ACCOUNT_PAGE_COUNT_INVALID");
  if (accountPages.length === 1) {
    let membershipFrames = 0;
    try {
      for (const frame of accountPages[0].frames()) {
        const body = await frame.locator("body").innerText().catch(() => "");
        const passwordInputs = await frame.locator("input[type='password']").count().catch(() => 0);
        if (/Membership details/i.test(body) && passwordInputs === 0) membershipFrames += 1;
      }
    } catch {
      fail("APPLE_ACCOUNT_PAGE_READ_FAILED");
    }
    if (membershipFrames !== 1) fail("APPLE_ACCOUNT_MEMBERSHIP_MARKER_INVALID");
  } else {
    const businessPages = connected.context.pages().filter((page) => {
      try {
        const url = new URL(page.url());
        return url.protocol === "https:" &&
          url.hostname === "appstoreconnect.apple.com" &&
          url.pathname.startsWith("/business");
      } catch {
        return false;
      }
    });
    if (businessPages.length !== 1) fail("APPLE_ACCOUNT_PAGE_COUNT_INVALID");
    let authenticatedBusinessFrames = 0;
    try {
      for (const frame of businessPages[0].frames()) {
        const body = await frame.locator("body").innerText().catch(() => "");
        const passwordInputs = await frame.locator("input[type='password']").count().catch(() => 0);
        if (/Business/i.test(body) && /Agreements|Tax Forms|Bank Accounts/i.test(body) && passwordInputs === 0) {
          authenticatedBusinessFrames += 1;
        }
      }
    } catch {
      fail("APPLE_ACCOUNT_PAGE_READ_FAILED");
    }
    if (authenticatedBusinessFrames !== 1) fail("APPLE_BUSINESS_SESSION_MARKER_INVALID");
  }
  let after;
  try {
    after = await session.currentSessionIdentity();
  } catch {
    fail("EDGE_SESSION_CHANGED");
  }
  if (before.edge_pid !== after.edge_pid ||
      before.edge_websocket !== after.edge_websocket ||
      before.sessionId !== after.sessionId) {
    fail("EDGE_SESSION_CHANGED");
  }
  process.stdout.write(`${JSON.stringify({
    markers: ["APPLE_DEVELOPER_ACCOUNT=verified"],
    edge_pid: after.edge_pid,
    edge_websocket: after.edge_websocket,
  })}\n`, () => process.exit(0));
} catch (error) {
  const raw = String(error?.message || "PROBE_INTERNAL_ERROR");
  const code = allowed.has(raw) ? raw : "PROBE_INTERNAL_ERROR";
  process.stderr.write(
    `APPLE_EXISTING_SESSION_ERROR=${code}\n`,
    () => process.exit(1),
  );
}
'''


class UTM18Error(RuntimeError):
    """Raised when the complete UTM-18 entry cannot safely continue."""


_SAFE_APPLE_LOGIN_MARKER = re.compile(
    rb"AppleWebWorkflowError: ([A-Z][A-Z0-9_]*(?:=[A-Z0-9_]+|=\d+)?)"
)


def edge_process_present(
    vm_name: str,
    vm_ip: str,
    vm_user: str,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> bool:
    """Return whether the guest has an existing Edge main process."""
    command, environment = build_invocation(
        vm_name,
        vm_ip,
        ["/bin/zsh", "-lc", EDGE_PROCESS_PROBE],
        connect_timeout=8,
    )
    try:
        completed = runner(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=environment,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise UTM18Error("EDGE_PROCESS_PROBE_FAILED") from None
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise UTM18Error("EDGE_PROCESS_PROBE_FAILED")


def run_utm10_login(
    args: argparse.Namespace,
    *,
    api: Any,
    page_title: str,
) -> None:
    """Create and authenticate the UTM-10 browser session for this target."""
    payload = _apple_payload(api, page_title)
    payload["APPLE_ACCOUNT_USER_NAME"] = _required_field(
        api, page_title, "用户名："
    )
    # A missing or invalid session must initialize the fixed Edge profile anew.
    payload["UTM_10_REUSE_EXISTING_EDGE"] = False
    try:
        verify_guest_scripts(vm_ip=args.vm_ip, vm_user=args.vm_user)
        result = run_guest_stage(
            stage="utm-10",
            vm_name=args.vm_name,
            vm_ip=args.vm_ip,
            vm_user=args.vm_user,
            payload=payload,
        )
    except AppleWebError:
        raise UTM18Error("UTM_10_LOGIN_FAILED") from None
    if "UTM_10=verified" not in result.markers:
        raise UTM18Error("UTM_10_LOGIN_FAILED")


def start_edge_and_login_if_missing(
    args: argparse.Namespace, *, api: Any, page_title: str
) -> bool:
    """Start and log in only when the guest has no Edge process."""
    if edge_process_present(args.vm_name, args.vm_ip, args.vm_user):
        return False
    run_utm10_login(args, api=api, page_title=page_title)
    return True


def ensure_browser_session(
    args: argparse.Namespace, *, api: Any, page_title: str
) -> bool:
    return start_edge_and_login_if_missing(args, api=api, page_title=page_title)


def _required_field(api: Any, page_title: str, label: str) -> str:
    value = api.read_field(page_title, "账号信息", label).strip()
    if not value:
        raise UTM18Error("NOTION_REQUIRED_FIELD_MISSING")
    return value


def _apple_payload(api: Any, page_title: str) -> dict[str, str]:
    password = api.read_field(
        page_title, "账号信息", "修改后的密码："
    ).strip()
    if not password:
        password = _required_field(api, page_title, "初始密码：")
    payload = {
        "APPLE_ACCOUNT_EMAIL": _required_field(api, page_title, "邮箱："),
        "APPLE_ACCOUNT_PASSWORD": password,
        "APPLE_ACCOUNT_PHONE": _required_field(api, page_title, "电话："),
        "APPLE_ACCOUNT_SMS_URL": _required_field(
            api, page_title, "电话短信接收平台："
        ),
    }
    sms = urlparse(payload["APPLE_ACCOUNT_SMS_URL"])
    if sms.scheme not in {"http", "https"} or not sms.netloc:
        raise UTM18Error("NOTION_SMS_URL_INVALID")
    return payload


def verify_or_login_apple(
    api: Any,
    *,
    parent_title: str,
    page_title: str,
    vm_name: str,
    vm_ip: str,
    vm_user: str,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    if vm_user != vm_name or not re.fullmatch(r"[a-z]{4}", vm_name):
        raise UTM18Error("VM_IDENTITY_INVALID")
    api.verify_parent(parent_title)
    payload = _apple_payload(api, page_title)
    base = GUEST_HELPER_DIR.format(vm_user=vm_user)
    remote = shlex.join(
        ("python3", "-B", "-c", APPLE_LOGIN_BRIDGE, base)
    )
    command, environment = build_invocation(
        vm_name,
        vm_ip,
        ["/bin/zsh", "-lc", f"exec {remote}"],
        connect_timeout=8,
    )
    completed = runner(
        command,
        input=json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=environment,
        timeout=300,
    )
    if completed.returncode != 0:
        APPLE_LOGIN_DIAGNOSTIC.parent.mkdir(parents=True, exist_ok=True)
        APPLE_LOGIN_DIAGNOSTIC.write_bytes(bytes(completed.stderr))
        APPLE_LOGIN_DIAGNOSTIC.chmod(0o600)
        marker = _SAFE_APPLE_LOGIN_MARKER.search(bytes(completed.stderr))
        suffix = f":{marker.group(1).decode('ascii')}" if marker else ""
        raise UTM18Error(f"APPLE_DEVELOPER_LOGIN_FAILED{suffix}")
    try:
        result = json.loads(bytes(completed.stdout).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        raise UTM18Error("APPLE_DEVELOPER_RESULT_INVALID") from error
    if (
        not isinstance(result, dict)
        or result.get("markers") != ["APPLE_DEVELOPER_ACCOUNT=verified"]
        or not isinstance(result.get("edge_pid"), int)
        or not isinstance(result.get("edge_websocket"), str)
        or not result["edge_websocket"].startswith("ws://127.0.0.1:9222/")
    ):
        raise UTM18Error("APPLE_DEVELOPER_RESULT_INVALID")
    APPLE_LOGIN_DIAGNOSTIC.unlink(missing_ok=True)
    return result


def verify_existing_apple_session(
    *,
    vm_name: str,
    vm_ip: str,
    vm_user: str,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Read and verify the inherited Developer Account session without login."""
    if vm_user != vm_name or not re.fullmatch(r"[a-z]{4}", vm_name):
        raise UTM18Error("VM_IDENTITY_INVALID")
    base = GUEST_HELPER_DIR.format(vm_user=vm_user)
    session_path = f"{base}/session.mjs"
    node_command = shlex.join(
        (
            "node",
            "--input-type=module",
            "--eval",
            APPLE_EXISTING_SESSION_BRIDGE,
            f"file://{session_path}",
        )
    )
    remote_script = "\n".join(
        (
            "set -euo pipefail",
            f"base={shlex.quote(base)}",
            f"session={shlex.quote(session_path)}",
            '[[ -d "$base" && ! -L "$base" ]]',
            '[[ -f "$session" && ! -L "$session" && -O "$session" '
            '&& -r "$session" && -s "$session" ]]',
            f"exec /bin/zsh -lic {shlex.quote(node_command)}",
        )
    )
    command, environment = build_invocation(
        vm_name,
        vm_ip,
        ["/bin/zsh", "-lc", remote_script],
        connect_timeout=8,
    )
    completed = runner(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=environment,
        timeout=60,
    )
    if completed.returncode != 0:
        error_line = bytes(completed.stderr).strip()
        match = re.fullmatch(
            rb"APPLE_EXISTING_SESSION_ERROR=([A-Z][A-Z0-9_]*)",
            error_line,
        )
        code = match.group(1).decode("ascii") if match else "PROBE_FAILED"
        raise UTM18Error(f"APPLE_EXISTING_SESSION_NOT_VERIFIED:{code}")
    try:
        output_lines = [
            line for line in bytes(completed.stdout).decode("utf-8").splitlines()
            if line.strip()
        ]
        if len(output_lines) != 1:
            raise ValueError("unexpected output line count")
        result = json.loads(output_lines[0])
        websocket = str(result.get("edge_websocket") or "")
        websocket_url = urlparse(websocket)
        websocket_path = websocket_url.path
    except (AttributeError, TypeError, ValueError, UnicodeDecodeError) as error:
        raise UTM18Error("APPLE_EXISTING_SESSION_RESULT_INVALID") from error
    edge_pid = result.get("edge_pid")
    if (
        not isinstance(result, dict)
        or result.get("markers") != ["APPLE_DEVELOPER_ACCOUNT=verified"]
        or isinstance(edge_pid, bool)
        or not isinstance(edge_pid, int)
        or edge_pid <= 0
        or websocket_url.scheme != "ws"
        or websocket_url.hostname != "127.0.0.1"
        or websocket_url.port != 9222
        or websocket_url.username is not None
        or websocket_url.password is not None
        or websocket_url.query
        or websocket_url.fragment
        or not websocket_path.startswith("/devtools/browser/")
        or not websocket_path.removeprefix("/devtools/browser/")
    ):
        raise UTM18Error("APPLE_EXISTING_SESSION_RESULT_INVALID")
    return result


def _classify_with_resident_rechecks(
    attempt: Any,
    *,
    sleeper: Callable[[float], None] = time.sleep,
) -> AttemptResult:
    mode_options = {"skip_iap": bool(getattr(attempt, "skip_iap", True))}
    log, status, process_running = inspect_remote(attempt)
    result = classify_attempt(
        log,
        status,
        process_running=process_running,
        expected_attempt_id=attempt.attempt_id,
        **mode_options,
    )
    max_polls = FILL_DESCRIPTION_WAIT_SECONDS // FILL_DESCRIPTION_POLL_SECONDS
    for _ in range(max_polls):
        pending = (
            result.state == "ambiguous"
            and result.mode == "incomplete"
            and (
                process_running
                or any(
                    f"RUN_STATE={state}" in result.reason
                    for state in ("prepared", "launching", "running")
                )
            )
        )
        if not pending:
            break
        sleeper(FILL_DESCRIPTION_POLL_SECONDS)
        log, status, process_running = inspect_remote(attempt)
        result = classify_attempt(
            log,
            status,
            process_running=process_running,
            expected_attempt_id=attempt.attempt_id,
            **mode_options,
        )
    else:
        return AttemptResult(
            "ambiguous",
            "timeout",
            reason=(
                f"FILL_DESCRIPTION_TIMEOUT_SECONDS={FILL_DESCRIPTION_WAIT_SECONDS};"
                f"{result.reason}"
            ),
        )
    if result.mode == "completed_after_transport_stop":
        expected_count = result.product_count
        for delay in (5, 10):
            sleeper(delay)
            next_log, next_status, next_running = inspect_remote(attempt)
            next_result = classify_attempt(
                next_log,
                next_status,
                process_running=next_running,
                expected_attempt_id=attempt.attempt_id,
                **mode_options,
            )
            if (
                next_result.mode != "completed_after_transport_stop"
                or next_result.product_count != expected_count
            ):
                return AttemptResult(
                    "ambiguous", "transport_stop_recheck_mismatch"
                )
        return AttemptResult(
            "verified", "completed_after_transport_stop", expected_count
        )
    if result.mode != "resident_after_summary":
        return result
    for delay in (5, 10):
        sleeper(delay)
        next_log, next_status, next_running = inspect_remote(attempt)
        next_result = classify_attempt(
            next_log,
            next_status,
            process_running=next_running,
            expected_attempt_id=attempt.attempt_id,
            **mode_options,
        )
        if next_result.mode != "resident_after_summary":
            return AttemptResult("ambiguous", "resident_recheck_mismatch")
        log, status, result = next_log, next_status, next_result
    return result


def _run_context(run_id: str, vm_name: str) -> tuple[str, str, str]:
    run = find_run(run_id)
    if not isinstance(run, dict) or run.get("vm_name") != vm_name:
        raise UTM18Error("FEISHU_RUN_CONTEXT_MISMATCH")
    app_name = str(run.get("app_name") or "").strip()
    parent_title = str(load_config().submission_host_machine or "").strip()
    if not app_name or not parent_title or run_host_machine(run) != parent_title:
        raise UTM18Error("FEISHU_RUN_CONTEXT_MISMATCH")
    return parent_title, app_name, f"{app_name}-{vm_name}"


def _attempt_failure_message(result: AttemptResult) -> str:
    message = f"FILL_DESCRIPTION_BLOCKED={result.state}:{result.mode}"
    if result.reason:
        message = f"{message};{result.reason}"
    return message


def archive_authorized_attempt(attempt: Any) -> Path:
    """Archive one explicitly user-authorized attempt before a forced replay."""
    archive_dir = attempt.ledger_path.parent.parent / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    archive_dir.chmod(0o700)
    archived = archive_dir / attempt.ledger_path.name
    if archived.exists() or archived.is_symlink():
        raise UTM18Error("FORCE_REPLAY_ARCHIVE_CONFLICT")
    os.replace(attempt.ledger_path, archived)
    archived.chmod(0o600)
    return archived


def run(args: argparse.Namespace) -> int:
    if getattr(args, "existing_browser", False):
        return run_existing_browser(args)
    skip_iap = getattr(args, "skip_iap", True)
    if args.vm_user != args.vm_name:
        raise UTM18Error("VM_USER_MISMATCH")
    attempts_root = Path(args.attempts_root)
    supplied_run_id = getattr(args, "run_id", None)
    direct_mode = not supplied_run_id
    legacy_parent = str(getattr(args, "parent_title", "") or "").strip()
    legacy_page = str(getattr(args, "page_title", "") or "").strip()
    check_notion_app = True
    if direct_mode:
        context = resolve_direct_context(
            parent_title=optional_setting("SUBMISSION_HOST_MACHINE"),
            page_title=legacy_page,
            vm_name=args.vm_name,
            vm_ip=args.vm_ip,
            vm_user=args.vm_user,
        )
        context_id = context.context_id
        parent_title, page_title, app_name = (
            context.parent_title,
            context.page_title,
            context.app_name,
        )
    elif legacy_parent and legacy_page:
        context_id = str(supplied_run_id)
        parent_title, page_title = legacy_parent, legacy_page
        suffix = f"-{args.vm_name}"
        app_name = page_title[: -len(suffix)] if page_title.endswith(suffix) else ""
        check_notion_app = False
    else:
        context_id = str(supplied_run_id)
        parent_title, app_name, page_title = _run_context(context_id, args.vm_name)
    api = api_from_env()
    api.verify_parent(parent_title)
    if check_notion_app:
        notion_app = api.read_field(page_title, "应用信息", "应用名: ").strip()
        if notion_app != app_name:
            raise UTM18Error("NOTION_PAGE_APP_MISMATCH")

    ensure_browser_session(args, api=api, page_title=page_title)

    attempt = load_single_attempt(attempts_root, context_id)
    if attempt is not None:
        if getattr(attempt, "skip_iap", True) != skip_iap:
            raise UTM18Error("ATTEMPT_IAP_MODE_MISMATCH")
        if (
            attempt.vm_name != args.vm_name
            or attempt.vm_ip != args.vm_ip
            or attempt.run_id != context_id
        ):
            raise UTM18Error("ATTEMPT_CONTEXT_MISMATCH")
        if attempt.state == "verified":
            print("UTM_18_RESUME=verified")
            print("UTM_18=verified")
            return 0
        if getattr(args, "force_replay", False):
            archive_authorized_attempt(attempt)
            attempt = None
        elif attempt.state in {"running", "completion_observed"}:
            previous_log, previous_status, previous_running = inspect_remote(attempt)
            launch_not_started = (
                not previous_running
                and "RUN_STATE=prepared" in previous_status
            )
            if is_retryable_finished_attempt(
                attempt,
                log=previous_log,
                status=previous_status,
                process_running=previous_running,
            ):
                archive_retryable_attempt(
                    attempt,
                    log=previous_log,
                    status=previous_status,
                    process_running=previous_running,
                )
                attempt = None
            elif launch_not_started:
                attempt = mark_attempt(attempt, state="precommitted")

    if attempt is None:
        verify_existing_apple_session(
            vm_name=args.vm_name, vm_ip=args.vm_ip, vm_user=args.vm_user,
        )

    if skip_iap and (attempt is None or attempt.state == "prepared"):
        prepare_guest_skip_iap(args.vm_name, args.vm_ip, args.vm_user)

    if attempt is None:
        attempt = create_attempt(
            attempts_root,
            run_id=context_id,
            vm_name=args.vm_name,
            vm_ip=args.vm_ip,
            skip_iap=skip_iap,
        )

    if attempt.state == "prepared":
        precommit_remote(attempt)
        print("UTM_18_LOG_PATH=precommitted")
        attempt = mark_attempt(attempt, state="precommitted")

    if attempt.state == "precommitted":
        attempt = mark_attempt(attempt, state="running")
        ssh_exit = run_remote(attempt)
        print(f"SSH_EXIT={ssh_exit}")

    if attempt.state not in {"running", "completion_observed"}:
        raise UTM18Error(f"ATTEMPT_STATE_INVALID={attempt.state}")

    result = _classify_with_resident_rechecks(attempt)
    if result.state != "verified" or result.product_count is None:
        raise UTM18Error(_attempt_failure_message(result))
    attempt = mark_attempt(attempt, state="verified", mode=result.mode)
    print("UTM_18_ATTEMPT_ID=verified")
    print("UTM_18_LOG=verified")
    print(f"SUMMARY_PRODUCT_COUNT={result.product_count}")
    print(f"FILL_DESCRIPTION_PROCESS={result.mode}")
    print("FILL_DESCRIPTION=verified")
    if direct_mode:
        print("UTM_18_DIRECT_CONTEXT=verified")
    print("UTM_18=verified")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Complete UTM-18 in one entry")
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--run-id")
    selector.add_argument("--page-title")
    parser.add_argument("--vm-name", required=True)
    parser.add_argument("--vm-ip", required=True)
    parser.add_argument("--vm-user", required=True)
    parser.add_argument("--existing-browser", action="store_true", help="Use the current Edge accessibility session without a debugging port or restart")
    parser.add_argument(
        "--skip-iap",
        action="store_true",
        default=True,
        help="Skip in-app purchase creation (default). Use standalone utm-iap later if needed.",
    )
    parser.add_argument(
        "--with-iap",
        action="store_false",
        dest="skip_iap",
        help="Include in-app purchase creation in this utm-script attempt (legacy opt-in).",
    )
    parser.add_argument("--force-replay", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--attempts-root",
        type=Path,
        default=DEFAULT_ATTEMPTS_ROOT,
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    def operation() -> int:
        started_at = time.monotonic()
        status = run(args)
        print("UTM-18 应用描述步骤已完成")
        print(f"UTM_18_ELAPSED_SECONDS={round(time.monotonic() - started_at)}")
        return status

    return run_clean_cli(
        skill_name="utm-script",
        success_marker="UTM_18=verified",
        operation=operation,
        preserve_error_detail=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
