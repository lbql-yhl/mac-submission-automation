#!/usr/bin/env python3
"""Log a cold-started UTM guest into its desktop from the host.

The helper inspects guest ``/dev/console`` and Finder, then types into the
exact UTM display window. It never enables auto-login and never writes guest
settings. Password key events never enter osascript argv.
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from services.host_config import ConfigurationError, guest_password


DEFAULT_POLL_TIMEOUT_SECONDS = 45.0
DEFAULT_POLL_INTERVAL_SECONDS = 3.0
DEFAULT_STEP_DELAY_SECONDS = 3.0
DEFAULT_MAX_ATTEMPTS = 2
RETURN_KEY = 36
TAB_KEY = 48
CLEAR_KEY = 51
CLEAR_COUNT = 32

ReadState = Callable[[str, str], "GuestDesktopState"]
FocusWindow = Callable[[str, Path], int]
SendKeys = Callable[[int, tuple[int, ...]], None]
PasswordLoader = Callable[[], str]
SleepFn = Callable[[float], None]
ClockFn = Callable[[], float]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class GuestDesktopLoginError(RuntimeError):
    """Non-sensitive desktop-login failure with a stable error code."""

    def __init__(
        self,
        code: str,
        detail: str = "",
        *,
        state: GuestDesktopState | None = None,
    ) -> None:
        self.code = code
        self.state = state
        super().__init__(code if not detail else f"{code}: {detail}")


@dataclass(frozen=True)
class GuestDesktopState:
    console_user: str
    finder_running: bool

    def label(self) -> str:
        finder = "ready" if self.finder_running else "missing"
        return f"console_user={self.console_user or 'empty'} finder={finder}"


@dataclass(frozen=True)
class GuestDesktopLoginResult:
    status: str
    console_user: str
    finder_running: bool
    attempts: int


def redact_secrets(message: str, secrets: tuple[str, ...]) -> str:
    """Replace secret values so they never appear in logs or exceptions."""
    redacted = str(message)
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    return redacted


def resolve_guest_username(vm_name: str, guest_user: str | None = None) -> str:
    """Prefer an explicit guest user; otherwise use the four-letter VM name."""
    user = str(guest_user or "").strip() or str(vm_name).strip()
    if not re.fullmatch(r"[a-z]{4}", user):
        raise GuestDesktopLoginError("GUEST_DESKTOP_USER_INVALID")
    return user


def classify_console_state(console_user: str, expected_user: str) -> str:
    """Classify the guest console using the same /dev/console owner rule."""
    current = str(console_user or "").strip()
    if current == expected_user:
        return "interactive"
    if current in {"", "root"}:
        return "login_window"
    return "unknown"


def desktop_ready(state: GuestDesktopState, expected_user: str) -> bool:
    return state.console_user == expected_user and state.finder_running


def load_guest_password(*, password_fn: PasswordLoader | None = None) -> str:
    """Read ``SUBMISSION_GUEST_PASSWORD`` without echoing its value."""
    try:
        value = password_fn() if password_fn is not None else guest_password()
    except ConfigurationError as error:
        raise GuestDesktopLoginError(
            "GUEST_DESKTOP_PASSWORD_MISSING",
            redact_secrets(str(error), ()),
        ) from None
    if re.fullmatch(r"[0-9]{4}", value) is None:
        raise GuestDesktopLoginError("GUEST_DESKTOP_PASSWORD_INVALID")
    return value


def username_key_codes(user: str) -> tuple[int, ...]:
    from scripts.utm_post_clone_guest import LOGIN_NAME_KEY_CODES

    if not re.fullmatch(r"[a-z]{4}", user):
        raise GuestDesktopLoginError("GUEST_DESKTOP_USER_INVALID")
    return (CLEAR_KEY,) * CLEAR_COUNT + tuple(
        LOGIN_NAME_KEY_CODES[character] for character in user
    )


def password_key_codes(password: str) -> tuple[int, ...]:
    from scripts.utm_post_clone_guest import DIGIT_KEY_CODES

    if re.fullmatch(r"[0-9]{4}", password) is None:
        raise GuestDesktopLoginError("GUEST_DESKTOP_PASSWORD_INVALID")
    return (CLEAR_KEY,) * CLEAR_COUNT + tuple(
        DIGIT_KEY_CODES[digit] for digit in password
    ) + (RETURN_KEY,)


def login_sequence_key_groups(
    user: str,
    password: str,
    *,
    field_mode: bool = False,
) -> tuple[tuple[int, ...], ...]:
    """Always select the user first, then type the password and press Return."""
    if field_mode:
        return (
            username_key_codes(user) + (TAB_KEY,),
            password_key_codes(password),
        )
    return (username_key_codes(user) + (RETURN_KEY,), password_key_codes(password))


def utm_window_titles(vm_name: str) -> tuple[str, ...]:
    return (vm_name, f"UTM – {vm_name}", f"UTM - {vm_name}", f"UTM — {vm_name}")


def system_events_activate_script() -> str:
    """Raise the unique UTM display window. The VM name arrives via argv only."""
    return """on run argv
  if (count of argv) is not 1 then error "UTM_GUEST_WINDOW_NAME_MISSING"
  set vmName to item 1 of argv
  tell application "System Events"
    tell process "UTM"
      set frontmost to true
      set accepted to {vmName, "UTM – " & vmName, "UTM - " & vmName, "UTM — " & vmName}
      set matches to {}
      repeat with w in windows
        if accepted contains (name of w as text) then set end of matches to w
      end repeat
      if (count of matches) is not 1 then error "UTM_GUEST_WINDOW_NOT_UNIQUE"
      perform action "AXRaise" of item 1 of matches
    end tell
  end tell
end run
"""


def activate_utm_guest_window(
    vm_name: str,
    *,
    run_command: CommandRunner | None = None,
) -> None:
    """Activate only the named UTM guest window through System Events."""
    if not re.fullmatch(r"[a-z]{4}", vm_name):
        raise GuestDesktopLoginError("GUEST_DESKTOP_USER_INVALID")
    runner = run_command or subprocess.run
    result = runner(
        ["osascript", "-", vm_name],
        input=system_events_activate_script(),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = redact_secrets(
            (result.stderr or result.stdout or "osascript failed").strip(),
            (),
        )
        raise GuestDesktopLoginError("GUEST_DESKTOP_WINDOW_TARGET_FAILED", detail)


def _default_read_state(user: str, ip: str) -> GuestDesktopState:
    from scripts.utm_post_clone_guest import ssh_python

    source = (
        "import subprocess\n"
        "console=subprocess.run("
        "['/usr/bin/stat','-f','%Su','/dev/console'],"
        "capture_output=True,text=True,check=True"
        ").stdout.strip()\n"
        "finder=subprocess.run("
        "['/usr/bin/pgrep','-x','Finder'],"
        "capture_output=True,text=True"
        ").returncode==0\n"
        "print('CONSOLE_USER='+console)\n"
        "print('FINDER='+('ready' if finder else 'missing'))\n"
    )
    output = ssh_python(user, ip, source)
    values = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return GuestDesktopState(
        values.get("CONSOLE_USER", ""),
        values.get("FINDER") == "ready",
    )


def _default_focus_guest_window(vm_name: str, bundle: Path) -> int:
    from scripts.utm_post_clone_guest import _focus_guest_input

    activate_utm_guest_window(vm_name)
    pid, _bounds = _focus_guest_input(vm_name, bundle)
    return pid


def _default_send_key_codes(pid: int, codes: tuple[int, ...]) -> None:
    from scripts.utm_post_clone_guest import _key_codes

    _key_codes(pid, codes)


def _failed(
    *,
    state: GuestDesktopState,
    attempts: int,
    secrets: tuple[str, ...],
) -> GuestDesktopLoginError:
    return GuestDesktopLoginError(
        "GUEST_DESKTOP_LOGIN_FAILED",
        redact_secrets(f"{state.label()} attempts={attempts}", secrets),
    )


def _wait_until_ready(
    *,
    expected_user: str,
    user: str,
    ip: str,
    timeout_seconds: float,
    interval_seconds: float,
    read_state: ReadState,
    sleep_fn: SleepFn,
    clock_fn: ClockFn,
    secrets: tuple[str, ...],
) -> GuestDesktopState:
    deadline = clock_fn() + timeout_seconds
    last = GuestDesktopState("", False)
    while True:
        try:
            last = read_state(user, ip)
        except GuestDesktopLoginError:
            raise
        except Exception as error:
            raise GuestDesktopLoginError(
                "GUEST_DESKTOP_CONSOLE_PROBE_FAILED",
                redact_secrets(str(error), secrets),
            ) from None
        if desktop_ready(last, expected_user):
            return last
        if classify_console_state(last.console_user, expected_user) == "unknown":
            raise GuestDesktopLoginError("GUEST_DESKTOP_CONSOLE_UNKNOWN")
        if clock_fn() >= deadline:
            raise GuestDesktopLoginError(
                "GUEST_DESKTOP_LOGIN_TIMEOUT", last.label(), state=last
            )
        sleep_fn(interval_seconds)


def ensure_guest_desktop_login(
    *,
    vm_name: str,
    vm_ip: str,
    bundle: Path,
    guest_user: str | None = None,
    poll_timeout_seconds: float = DEFAULT_POLL_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    step_delay_seconds: float = DEFAULT_STEP_DELAY_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    password_fn: PasswordLoader | None = None,
    read_state: ReadState | None = None,
    focus_window: FocusWindow | None = None,
    send_keys: SendKeys | None = None,
    sleep_fn: SleepFn | None = None,
    clock_fn: ClockFn | None = None,
) -> GuestDesktopLoginResult:
    """Bring the exact guest to an interactive desktop, or no-op if already there."""
    if max_attempts < 1:
        raise GuestDesktopLoginError("GUEST_DESKTOP_LOGIN_FAILED", "attempts=0")
    expected_user = resolve_guest_username(vm_name, guest_user)
    reader = read_state or _default_read_state
    focuser = focus_window or _default_focus_guest_window
    typer = send_keys or _default_send_key_codes
    sleeper = sleep_fn or time.sleep
    clock = clock_fn or time.monotonic
    try:
        state = reader(expected_user, vm_ip)
    except GuestDesktopLoginError:
        raise
    except Exception as error:
        raise GuestDesktopLoginError(
            "GUEST_DESKTOP_CONSOLE_PROBE_FAILED",
            redact_secrets(str(error), ()),
        ) from None
    if desktop_ready(state, expected_user):
        return GuestDesktopLoginResult("already_interactive", state.console_user, True, 0)
    console_state = classify_console_state(state.console_user, expected_user)
    if console_state == "unknown":
        raise GuestDesktopLoginError("GUEST_DESKTOP_CONSOLE_UNKNOWN")

    secrets: tuple[str, ...] = ()
    needs_typing = console_state == "login_window"
    if needs_typing:
        password = load_guest_password(password_fn=password_fn)
        secrets = (password,)

    last_state = state
    for attempt in range(1, max_attempts + 1):
        if needs_typing:
            try:
                pid = focuser(vm_name, Path(bundle))
                groups = login_sequence_key_groups(
                    expected_user,
                    password,
                    field_mode=attempt > 1,
                )
                for index, group in enumerate(groups):
                    if index:
                        sleeper(step_delay_seconds)
                    typer(pid, group)
            except GuestDesktopLoginError as error:
                raise GuestDesktopLoginError(
                    error.code, redact_secrets(str(error), secrets)
                ) from None
            except Exception as error:
                raise GuestDesktopLoginError(
                    "GUEST_DESKTOP_WINDOW_TARGET_FAILED",
                    redact_secrets(str(error), secrets),
                ) from None
        try:
            last_state = _wait_until_ready(
                expected_user=expected_user,
                user=expected_user,
                ip=vm_ip,
                timeout_seconds=poll_timeout_seconds,
                interval_seconds=poll_interval_seconds,
                read_state=reader,
                sleep_fn=sleeper,
                clock_fn=clock,
                secrets=secrets,
            )
            return GuestDesktopLoginResult(
                "login_verified" if needs_typing else "already_interactive",
                last_state.console_user,
                True,
                attempt if needs_typing else 0,
            )
        except GuestDesktopLoginError as error:
            if error.code == "GUEST_DESKTOP_LOGIN_TIMEOUT" and attempt < max_attempts:
                if error.state is not None:
                    last_state = error.state
                sleeper(poll_interval_seconds)
                continue
            if error.code == "GUEST_DESKTOP_LOGIN_TIMEOUT":
                raise _failed(
                    state=error.state or last_state,
                    attempts=attempt,
                    secrets=secrets,
                ) from None
            raise GuestDesktopLoginError(
                error.code, redact_secrets(str(error), secrets)
            ) from None
    raise _failed(state=last_state, attempts=max_attempts, secrets=secrets)
