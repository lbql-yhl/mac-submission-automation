#!/usr/bin/env python3
"""Log a cold-started UTM guest into its desktop from the host.

The helper only inspects guest ``/dev/console`` and, when the login window is
up, types into the exact UTM display window. It never enables auto-login and
never writes guest settings.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from services.host_config import ConfigurationError, guest_password


DEFAULT_POLL_TIMEOUT_SECONDS = 45.0
DEFAULT_POLL_INTERVAL_SECONDS = 3.0
DEFAULT_MAX_ATTEMPTS = 2
RETURN_KEY = 36
TAB_KEY = 48
CLEAR_KEY = 51
CLEAR_COUNT = 32

ReadConsole = Callable[[str, str], str]
FocusWindow = Callable[[str, Path], int]
SendKeys = Callable[[int, tuple[int, ...]], None]
FullNameMode = Callable[[str, str], bool]
PasswordLoader = Callable[[], str]
SleepFn = Callable[[float], None]
ClockFn = Callable[[], float]


class GuestDesktopLoginError(RuntimeError):
    """Non-sensitive desktop-login failure with a stable error code."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(code if not detail else f"{code}: {detail}")


@dataclass(frozen=True)
class GuestDesktopLoginResult:
    status: str
    console_user: str
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
    full_name_login: bool,
    alternate: bool = False,
) -> tuple[tuple[int, ...], ...]:
    """Build keyboard-only login groups; password stays as key codes only."""
    if alternate:
        return (username_key_codes(user) + (TAB_KEY,) + password_key_codes(password)[CLEAR_COUNT:],)
    if full_name_login:
        return (username_key_codes(user) + (RETURN_KEY,), password_key_codes(password))
    return (password_key_codes(password),)


def _default_read_console_user(user: str, ip: str) -> str:
    from scripts.utm_post_clone_guest import ssh_python

    source = (
        "import subprocess\n"
        "print(subprocess.run("
        "['/usr/bin/stat','-f','%Su','/dev/console'],"
        "capture_output=True,text=True,check=True"
        ").stdout.strip())\n"
    )
    output = ssh_python(user, ip, source).strip()
    return output.splitlines()[-1] if output else ""


def _default_focus_guest_window(vm_name: str, bundle: Path) -> int:
    from scripts.utm_post_clone_guest import _focus_guest_input

    pid, _bounds = _focus_guest_input(vm_name, bundle)
    return pid


def _default_send_key_codes(pid: int, codes: tuple[int, ...]) -> None:
    from scripts.utm_post_clone_guest import _key_codes

    _key_codes(pid, codes)


def _default_full_name_enabled(user: str, ip: str) -> bool:
    from scripts.utm_post_clone_guest import loginwindow_full_name_enabled

    return loginwindow_full_name_enabled(user, ip)


def _wait_for_console_user(
    *,
    expected_user: str,
    user: str,
    ip: str,
    timeout_seconds: float,
    interval_seconds: float,
    read_console: ReadConsole,
    sleep_fn: SleepFn,
    clock_fn: ClockFn,
    secrets: tuple[str, ...],
) -> str:
    deadline = clock_fn() + timeout_seconds
    last = ""
    while True:
        try:
            last = read_console(user, ip)
        except Exception as error:
            raise GuestDesktopLoginError(
                "GUEST_DESKTOP_CONSOLE_PROBE_FAILED",
                redact_secrets(str(error), secrets),
            ) from None
        if classify_console_state(last, expected_user) == "interactive":
            return last
        if clock_fn() >= deadline:
            raise GuestDesktopLoginError("GUEST_DESKTOP_LOGIN_TIMEOUT")
        sleep_fn(interval_seconds)


def ensure_guest_desktop_login(
    *,
    vm_name: str,
    vm_ip: str,
    bundle: Path,
    guest_user: str | None = None,
    poll_timeout_seconds: float = DEFAULT_POLL_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    password_fn: PasswordLoader | None = None,
    read_console: ReadConsole | None = None,
    focus_window: FocusWindow | None = None,
    send_keys: SendKeys | None = None,
    full_name_enabled: FullNameMode | None = None,
    sleep_fn: SleepFn | None = None,
    clock_fn: ClockFn | None = None,
) -> GuestDesktopLoginResult:
    """Bring the exact guest to an interactive desktop, or no-op if already there."""
    if max_attempts < 1:
        raise GuestDesktopLoginError("GUEST_DESKTOP_LOGIN_ATTEMPTS_EXHAUSTED")
    expected_user = resolve_guest_username(vm_name, guest_user)
    reader = read_console or _default_read_console_user
    focuser = focus_window or _default_focus_guest_window
    typer = send_keys or _default_send_key_codes
    sleeper = sleep_fn or time.sleep
    clock = clock_fn or time.monotonic
    try:
        console_user = reader(expected_user, vm_ip)
    except GuestDesktopLoginError:
        raise
    except Exception as error:
        raise GuestDesktopLoginError(
            "GUEST_DESKTOP_CONSOLE_PROBE_FAILED",
            redact_secrets(str(error), ()),
        ) from None
    state = classify_console_state(console_user, expected_user)
    if state == "interactive":
        return GuestDesktopLoginResult("already_interactive", console_user, 0)
    if state == "unknown":
        raise GuestDesktopLoginError("GUEST_DESKTOP_CONSOLE_UNKNOWN")

    password = load_guest_password(password_fn=password_fn)
    secrets = (password,)
    name_mode = full_name_enabled or _default_full_name_enabled
    try:
        full_name_login = name_mode(expected_user, vm_ip)
    except Exception as error:
        raise GuestDesktopLoginError(
            "GUEST_DESKTOP_LOGINWINDOW_MODE_FAILED",
            redact_secrets(str(error), secrets),
        ) from None

    for attempt in range(1, max_attempts + 1):
        try:
            pid = focuser(vm_name, Path(bundle))
            groups = login_sequence_key_groups(
                expected_user,
                password,
                full_name_login=full_name_login,
                alternate=attempt > 1,
            )
            for group in groups:
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
            console_user = _wait_for_console_user(
                expected_user=expected_user,
                user=expected_user,
                ip=vm_ip,
                timeout_seconds=poll_timeout_seconds,
                interval_seconds=poll_interval_seconds,
                read_console=reader,
                sleep_fn=sleeper,
                clock_fn=clock,
                secrets=secrets,
            )
            return GuestDesktopLoginResult("login_verified", console_user, attempt)
        except GuestDesktopLoginError as error:
            if error.code != "GUEST_DESKTOP_LOGIN_TIMEOUT" or attempt >= max_attempts:
                raise GuestDesktopLoginError(
                    error.code, redact_secrets(str(error), secrets)
                ) from None
            sleeper(poll_interval_seconds)
    raise GuestDesktopLoginError("GUEST_DESKTOP_LOGIN_ATTEMPTS_EXHAUSTED")
