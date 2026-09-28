from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from scripts.utm_guest_desktop_login import (
    GuestDesktopLoginError,
    classify_console_state,
    ensure_guest_desktop_login,
    login_sequence_key_groups,
    password_key_codes,
    redact_secrets,
    resolve_guest_username,
    username_key_codes,
)
from services.host_config import ConfigurationError


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "utm_guest_desktop_login.py"
BUNDLE = Path("/tmp/abcd.utm")
PASSWORD = "9072"


def _clock(values: list[float]):
    ticks = iter(values)

    def now() -> float:
        try:
            return next(ticks)
        except StopIteration:
            return values[-1] + 1000.0

    return now


def test_already_interactive_sends_no_input() -> None:
    sent: list[tuple[int, ...]] = []
    focused: list[str] = []

    result = ensure_guest_desktop_login(
        vm_name="abcd",
        vm_ip="192.0.2.10",
        bundle=BUNDLE,
        read_console=lambda _user, _ip: "abcd",
        focus_window=lambda name, _bundle: focused.append(name) or 17,
        send_keys=lambda _pid, codes: sent.append(codes),
        password_fn=lambda: PASSWORD,
        sleep_fn=lambda _seconds: None,
        clock_fn=lambda: 0.0,
    )

    assert result.status == "already_interactive"
    assert result.console_user == "abcd"
    assert result.attempts == 0
    assert sent == []
    assert focused == []


def test_login_window_types_username_and_password_then_polls_interactive() -> None:
    consoles = iter(("root", "root", "abcd"))
    sent: list[tuple[int, ...]] = []

    result = ensure_guest_desktop_login(
        vm_name="abcd",
        vm_ip="192.0.2.10",
        bundle=BUNDLE,
        read_console=lambda _user, _ip: next(consoles),
        focus_window=lambda _name, _bundle: 17,
        send_keys=lambda _pid, codes: sent.append(codes),
        full_name_enabled=lambda _user, _ip: True,
        password_fn=lambda: PASSWORD,
        sleep_fn=lambda _seconds: None,
        clock_fn=lambda: 0.0,
        poll_timeout_seconds=9.0,
        poll_interval_seconds=3.0,
    )

    assert result.status == "login_verified"
    assert result.console_user == "abcd"
    assert result.attempts == 1
    assert sent == list(
        login_sequence_key_groups("abcd", PASSWORD, full_name_login=True)
    )


def test_selected_user_login_sends_only_password() -> None:
    consoles = iter(("root", "abcd"))
    sent: list[tuple[int, ...]] = []

    result = ensure_guest_desktop_login(
        vm_name="abcd",
        vm_ip="192.0.2.10",
        bundle=BUNDLE,
        read_console=lambda _user, _ip: next(consoles),
        focus_window=lambda _name, _bundle: 17,
        send_keys=lambda _pid, codes: sent.append(codes),
        full_name_enabled=lambda _user, _ip: False,
        password_fn=lambda: PASSWORD,
        sleep_fn=lambda _seconds: None,
        clock_fn=lambda: 0.0,
    )

    assert result.status == "login_verified"
    assert sent == [password_key_codes(PASSWORD)]


def test_poll_timeout_raises_clear_code() -> None:
    with pytest.raises(GuestDesktopLoginError, match="GUEST_DESKTOP_LOGIN_TIMEOUT") as captured:
        ensure_guest_desktop_login(
            vm_name="abcd",
            vm_ip="192.0.2.10",
            bundle=BUNDLE,
            read_console=lambda _user, _ip: "root",
            focus_window=lambda _name, _bundle: 17,
            send_keys=lambda _pid, _codes: None,
            full_name_enabled=lambda _user, _ip: True,
            password_fn=lambda: PASSWORD,
            sleep_fn=lambda _seconds: None,
            clock_fn=_clock([0.0, 0.0, 50.0]),
            poll_timeout_seconds=45.0,
            max_attempts=1,
        )

    assert captured.value.code == "GUEST_DESKTOP_LOGIN_TIMEOUT"
    assert PASSWORD not in str(captured.value)


def test_missing_password_raises_without_value() -> None:
    def missing() -> str:
        raise ConfigurationError("missing required host setting: SUBMISSION_GUEST_PASSWORD")

    with pytest.raises(
        GuestDesktopLoginError, match="GUEST_DESKTOP_PASSWORD_MISSING"
    ) as captured:
        ensure_guest_desktop_login(
            vm_name="abcd",
            vm_ip="192.0.2.10",
            bundle=BUNDLE,
            read_console=lambda _user, _ip: "root",
            password_fn=missing,
            focus_window=lambda *_args: pytest.fail("must not focus without a password"),
            send_keys=lambda *_args: pytest.fail("must not type without a password"),
        )

    assert PASSWORD not in str(captured.value)
    assert "9072" not in str(captured.value)


def test_password_never_appears_in_exception_or_argv() -> None:
    def boom(_name: str, _bundle: Path) -> int:
        raise RuntimeError(f"window focus leaked {PASSWORD}")

    with pytest.raises(GuestDesktopLoginError) as captured:
        ensure_guest_desktop_login(
            vm_name="abcd",
            vm_ip="192.0.2.10",
            bundle=BUNDLE,
            read_console=lambda _user, _ip: "root",
            focus_window=boom,
            send_keys=lambda *_args: pytest.fail("must not type after focus failure"),
            full_name_enabled=lambda _user, _ip: True,
            password_fn=lambda: PASSWORD,
        )

    assert captured.value.code == "GUEST_DESKTOP_WINDOW_TARGET_FAILED"
    assert PASSWORD not in str(captured.value)
    source = HELPER.read_text(encoding="utf-8")
    assert "osascript" not in source
    assert "keystroke" not in source
    assert "sys.argv" not in source


def test_attempt_count_is_capped() -> None:
    focuses: list[int] = []

    with pytest.raises(GuestDesktopLoginError, match="GUEST_DESKTOP_LOGIN_TIMEOUT"):
        ensure_guest_desktop_login(
            vm_name="abcd",
            vm_ip="192.0.2.10",
            bundle=BUNDLE,
            read_console=lambda _user, _ip: "root",
            focus_window=lambda _name, _bundle: focuses.append(1) or 17,
            send_keys=lambda _pid, _codes: None,
            full_name_enabled=lambda _user, _ip: True,
            password_fn=lambda: PASSWORD,
            sleep_fn=lambda _seconds: None,
            clock_fn=_clock([0.0, 50.0, 50.0, 100.0, 100.0]),
            poll_timeout_seconds=1.0,
            max_attempts=2,
        )

    assert len(focuses) == 2


def test_username_defaults_to_vm_name_and_explicit_user_wins() -> None:
    assert resolve_guest_username("abcd") == "abcd"
    assert resolve_guest_username("abcd", "wxyz") == "wxyz"
    with pytest.raises(GuestDesktopLoginError, match="GUEST_DESKTOP_USER_INVALID"):
        resolve_guest_username("ABCD")

    seen: list[str] = []

    def read_console(user: str, _ip: str) -> str:
        seen.append(user)
        return user

    result = ensure_guest_desktop_login(
        vm_name="abcd",
        vm_ip="192.0.2.10",
        bundle=BUNDLE,
        guest_user="wxyz",
        read_console=read_console,
        password_fn=lambda: PASSWORD,
    )
    assert result.status == "already_interactive"
    assert seen == ["wxyz"]


def test_unknown_console_owner_is_rejected() -> None:
    with pytest.raises(GuestDesktopLoginError, match="GUEST_DESKTOP_CONSOLE_UNKNOWN"):
        ensure_guest_desktop_login(
            vm_name="abcd",
            vm_ip="192.0.2.10",
            bundle=BUNDLE,
            read_console=lambda _user, _ip: "demo",
            password_fn=lambda: PASSWORD,
        )


def test_helper_does_not_write_guest_login_settings() -> None:
    source = HELPER.read_text(encoding="utf-8")
    assert "defaults write" not in source
    assert "autoLoginUser" not in source
    assert "kcpassword" not in source
    assert classify_console_state("root", "abcd") == "login_window"
    assert classify_console_state("", "abcd") == "login_window"
    assert classify_console_state("abcd", "abcd") == "interactive"
    assert redact_secrets(f"boom {PASSWORD}", (PASSWORD,)) == "boom <redacted>"


def test_key_groups_are_keyboard_only_and_hide_password_digits() -> None:
    groups = login_sequence_key_groups("abcd", PASSWORD, full_name_login=True)
    assert groups[0] == username_key_codes("abcd") + (36,)
    assert groups[1] == password_key_codes(PASSWORD)
    assert PASSWORD not in repr(groups)
    source = inspect.getsource(ensure_guest_desktop_login)
    assert "_focus_guest_input" not in source
    assert "focus_window" in source


def test_clash_ip_calls_helper_after_start_and_before_console_state() -> None:
    source = (ROOT / "scripts" / "utm_clash_ip.py").read_text(encoding="utf-8")
    prepare = source.split("def prepare_vm", 1)[1].split("def ensure_guest_desktop", 1)[0]
    run = source.split("    def run(self)", 1)[1].split("def build_parser", 1)[0]
    assert "ensure_exact_vm_started" in prepare
    assert "self.ensure_guest_desktop()" in prepare
    assert prepare.index("ensure_exact_vm_started") < prepare.index(
        "self.ensure_guest_desktop()"
    )
    assert "self.prepare_vm()" in run
    assert "self.verify_identity()" in run
    assert run.index("self.prepare_vm()") < run.index("self.verify_identity()")
    assert "def _auto_login_console" not in source
    assert "osascript" not in source


def test_utm_login_calls_helper_before_apple_account_work() -> None:
    source = (ROOT / "scripts" / "utm_7_login.py").read_text(encoding="utf-8")
    run = source.split("def run(args", 1)[1].split("def main", 1)[0]
    assert "_ensure_guest_desktop_session(args.vm_user, args.vm_ip)" in run
    assert run.index("_ensure_guest_desktop_session") < run.index("api_from_env")
    assert "ensure_guest_desktop_login" in source
