from __future__ import annotations

from pathlib import Path

import pytest

from scripts.utm_guest_desktop_login import (
    GuestDesktopLoginError,
    GuestDesktopState,
    activate_utm_guest_window,
    classify_console_state,
    desktop_ready,
    ensure_guest_desktop_login,
    login_sequence_key_groups,
    password_key_codes,
    redact_secrets,
    resolve_guest_username,
    system_events_activate_script,
    username_key_codes,
    utm_window_titles,
)
from services.host_config import ConfigurationError


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "utm_guest_desktop_login.py"
BUNDLE = Path("/tmp/abcd.utm")
PASSWORD = "9072"


def _state(console: str, finder: bool = False) -> GuestDesktopState:
    return GuestDesktopState(console, finder)


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
        vm_name="wdil",
        vm_ip="192.0.2.10",
        bundle=BUNDLE,
        read_state=lambda _user, _ip: _state("wdil", True),
        focus_window=lambda name, _bundle: focused.append(name) or 17,
        send_keys=lambda _pid, codes: sent.append(codes),
        password_fn=lambda: PASSWORD,
        sleep_fn=lambda _seconds: None,
        clock_fn=lambda: 0.0,
    )

    assert result.status == "already_interactive"
    assert result.console_user == "wdil"
    assert result.finder_running is True
    assert result.attempts == 0
    assert sent == []
    assert focused == []


def test_login_selects_user_before_password_then_requires_finder() -> None:
    states = iter(
        (
            _state("root", False),
            _state("wdil", False),
            _state("wdil", True),
        )
    )
    sent: list[tuple[int, ...]] = []

    result = ensure_guest_desktop_login(
        vm_name="wdil",
        vm_ip="192.0.2.10",
        bundle=BUNDLE,
        read_state=lambda _user, _ip: next(states),
        focus_window=lambda _name, _bundle: 17,
        send_keys=lambda _pid, codes: sent.append(codes),
        password_fn=lambda: PASSWORD,
        sleep_fn=lambda _seconds: None,
        clock_fn=lambda: 0.0,
    )

    assert result.status == "login_verified"
    assert result.console_user == "wdil"
    assert result.finder_running is True
    assert sent == list(login_sequence_key_groups("wdil", PASSWORD))
    assert sent[0] == username_key_codes("wdil") + (36,)
    assert sent[1] == password_key_codes(PASSWORD)


def test_console_user_alone_is_not_success() -> None:
    with pytest.raises(GuestDesktopLoginError, match="GUEST_DESKTOP_LOGIN_FAILED") as captured:
        ensure_guest_desktop_login(
            vm_name="wdil",
            vm_ip="192.0.2.10",
            bundle=BUNDLE,
            read_state=lambda _user, _ip: _state("wdil", False),
            focus_window=lambda *_args: pytest.fail("must not type when console user is already present"),
            send_keys=lambda *_args: pytest.fail("must not type when console user is already present"),
            password_fn=lambda: PASSWORD,
            sleep_fn=lambda _seconds: None,
            clock_fn=_clock([0.0, 50.0]),
            poll_timeout_seconds=1.0,
            max_attempts=1,
        )

    assert captured.value.code == "GUEST_DESKTOP_LOGIN_FAILED"
    assert "console_user=wdil" in str(captured.value)
    assert "finder=missing" in str(captured.value)
    assert PASSWORD not in str(captured.value)
    assert not desktop_ready(_state("wdil", False), "wdil")


def test_first_attempt_can_fail_then_second_succeeds() -> None:
    states = iter(
        (
            _state("root", False),
            _state("root", False),
            _state("wdil", True),
        )
    )
    focuses: list[int] = []
    sent: list[tuple[int, ...]] = []

    result = ensure_guest_desktop_login(
        vm_name="wdil",
        vm_ip="192.0.2.10",
        bundle=BUNDLE,
        read_state=lambda _user, _ip: next(states),
        focus_window=lambda _name, _bundle: focuses.append(1) or 17,
        send_keys=lambda _pid, codes: sent.append(codes),
        password_fn=lambda: PASSWORD,
        sleep_fn=lambda _seconds: None,
        clock_fn=_clock([0.0, 50.0, 0.0, 0.0]),
        poll_timeout_seconds=1.0,
        max_attempts=2,
    )

    assert result.status == "login_verified"
    assert result.attempts == 2
    assert len(focuses) == 2
    assert sent[0] == username_key_codes("wdil") + (36,)
    assert sent[1] == password_key_codes(PASSWORD)
    assert sent[2] == username_key_codes("wdil") + (48,)
    assert sent[3] == password_key_codes(PASSWORD)


def test_exhausted_retries_report_observed_state_without_password() -> None:
    with pytest.raises(GuestDesktopLoginError) as captured:
        ensure_guest_desktop_login(
            vm_name="wdil",
            vm_ip="192.0.2.10",
            bundle=BUNDLE,
            read_state=lambda _user, _ip: _state("root", False),
            focus_window=lambda _name, _bundle: 17,
            send_keys=lambda _pid, _codes: None,
            password_fn=lambda: PASSWORD,
            sleep_fn=lambda _seconds: None,
            clock_fn=_clock([0.0, 50.0, 50.0, 100.0]),
            poll_timeout_seconds=1.0,
            max_attempts=2,
        )

    assert captured.value.code == "GUEST_DESKTOP_LOGIN_FAILED"
    message = str(captured.value)
    assert "console_user=root" in message
    assert "finder=missing" in message
    assert "attempts=2" in message
    assert PASSWORD not in message


def test_missing_password_raises_without_value() -> None:
    def missing() -> str:
        raise ConfigurationError("missing required host setting: SUBMISSION_GUEST_PASSWORD")

    with pytest.raises(
        GuestDesktopLoginError, match="GUEST_DESKTOP_PASSWORD_MISSING"
    ) as captured:
        ensure_guest_desktop_login(
            vm_name="wdil",
            vm_ip="192.0.2.10",
            bundle=BUNDLE,
            read_state=lambda _user, _ip: _state("root", False),
            password_fn=missing,
            focus_window=lambda *_args: pytest.fail("must not focus without a password"),
            send_keys=lambda *_args: pytest.fail("must not type without a password"),
        )

    assert PASSWORD not in str(captured.value)


def test_password_never_appears_in_exception_or_osascript_argv() -> None:
    def boom(_name: str, _bundle: Path) -> int:
        raise RuntimeError(f"window focus leaked {PASSWORD}")

    with pytest.raises(GuestDesktopLoginError) as captured:
        ensure_guest_desktop_login(
            vm_name="wdil",
            vm_ip="192.0.2.10",
            bundle=BUNDLE,
            read_state=lambda _user, _ip: _state("root", False),
            focus_window=boom,
            send_keys=lambda *_args: pytest.fail("must not type after focus failure"),
            password_fn=lambda: PASSWORD,
        )

    assert captured.value.code == "GUEST_DESKTOP_WINDOW_TARGET_FAILED"
    assert PASSWORD not in str(captured.value)
    script = system_events_activate_script()
    assert "System Events" in script
    assert PASSWORD not in script
    assert "keystroke" not in script


def test_system_events_activates_only_the_named_utm_window() -> None:
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(list(command))
        assert PASSWORD not in " ".join(str(part) for part in command)
        assert PASSWORD not in str(kwargs.get("input") or "")
        assert kwargs["input"] == system_events_activate_script()
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    activate_utm_guest_window("wdil", run_command=fake_run)
    assert commands == [["osascript", "-", "wdil"]]
    assert "wdil" in utm_window_titles("wdil")
    assert "UTM – wdil" in utm_window_titles("wdil")


def test_username_defaults_to_vm_name_and_explicit_user_wins() -> None:
    assert resolve_guest_username("wdil") == "wdil"
    assert resolve_guest_username("wdil", "abcd") == "abcd"
    with pytest.raises(GuestDesktopLoginError, match="GUEST_DESKTOP_USER_INVALID"):
        resolve_guest_username("WDIL")

    seen: list[str] = []

    def read_state(user: str, _ip: str) -> GuestDesktopState:
        seen.append(user)
        return _state(user, True)

    result = ensure_guest_desktop_login(
        vm_name="wdil",
        vm_ip="192.0.2.10",
        bundle=BUNDLE,
        guest_user="abcd",
        read_state=read_state,
        password_fn=lambda: PASSWORD,
    )
    assert result.status == "already_interactive"
    assert seen == ["abcd"]


def test_unknown_console_owner_is_rejected() -> None:
    with pytest.raises(GuestDesktopLoginError, match="GUEST_DESKTOP_CONSOLE_UNKNOWN"):
        ensure_guest_desktop_login(
            vm_name="wdil",
            vm_ip="192.0.2.10",
            bundle=BUNDLE,
            read_state=lambda _user, _ip: _state("demo", False),
            password_fn=lambda: PASSWORD,
        )


def test_helper_does_not_write_guest_login_settings() -> None:
    source = HELPER.read_text(encoding="utf-8")
    assert "defaults write" not in source
    assert "autoLoginUser" not in source
    assert "kcpassword" not in source
    assert classify_console_state("root", "wdil") == "login_window"
    assert redact_secrets(f"boom {PASSWORD}", (PASSWORD,)) == "boom <redacted>"


def test_clash_ip_calls_helper_after_start_and_before_console_state() -> None:
    source = (ROOT / "scripts" / "utm_clash_ip.py").read_text(encoding="utf-8")
    prepare = source.split("def prepare_vm", 1)[1].split("def ensure_guest_desktop", 1)[0]
    run = source.split("    def run(self)", 1)[1].split("def build_parser", 1)[0]
    assert "ensure_exact_vm_started" in prepare
    assert "self.ensure_guest_desktop()" in prepare
    assert prepare.index("ensure_exact_vm_started") < prepare.index(
        "self.ensure_guest_desktop()"
    )
    assert run.index("self.prepare_vm()") < run.index("self.verify_identity()")
    assert "def _auto_login_console" not in source
    assert "osascript" not in source


def test_utm_login_calls_helper_before_apple_account_work() -> None:
    source = (ROOT / "scripts" / "utm_7_login.py").read_text(encoding="utf-8")
    run = source.split("def run(args", 1)[1].split("def main", 1)[0]
    assert "_ensure_guest_desktop_session(args.vm_user, args.vm_ip)" in run
    assert run.index("_ensure_guest_desktop_session") < run.index("api_from_env")
    assert "ensure_guest_desktop_login" in source
