from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FlatDependency(types.ModuleType):
    def __getattr__(self, _name: str) -> object:
        return 0


def load_guest_module():
    sys.modules["ApplicationServices"] = FlatDependency("ApplicationServices")
    appkit = FlatDependency("AppKit")
    appkit.NSRunningApplication = object()
    sys.modules["AppKit"] = appkit
    sys.modules["Quartz"] = FlatDependency("Quartz")
    path = ROOT / "scripts" / "find_system_settings_general.py"
    spec = importlib.util.spec_from_file_location("sms_parser_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_extract_latest_sms_code_uses_newest_twelve_hour_timestamp() -> None:
    module = load_guest_module()
    page_text = """
    83356 Your Apple Account Code is: 405965. 2026-08-20 04:30 PM
    83356 Your Apple Account Code is: 933818. 2026-08-20 11:55 AM
    83356 Your Apple Account Code is: 881061. 2026-08-20 04:22 PM
    """

    assert module.extract_latest_sms_code(page_text) == "405965"


def test_extract_latest_sms_code_uses_top_message_when_page_has_no_time() -> None:
    module = load_guest_module()
    page_text = """
    83356 Your Apple Account Code is: 405965.
    83356 Your Apple Account Code is: 933818.
    83356 Your Apple Account Code is: 881061.
    """

    assert module.extract_latest_sms_code(page_text) == "405965"


def test_extract_latest_sms_code_prefers_visible_untimed_apple_code_when_embedded_history_is_stale() -> None:
    module = load_guest_module()
    page_text = """
    SMS INBOX Valid until: 09/09/2026, 04:56 PM
    Your Apple Account Code is: 405965. Don't share it with anyone.
    const embeddedHistory = `
      Your Apple Account Code is: 933818. 2026-08-20 11:55 AM
      Your Apple Account Code is: 881061. 2026-08-20 04:22 PM
    `;
    """
    requested_at = module._parse_sms_timestamp("2026-08-21 09:00 AM")
    now = module._parse_sms_timestamp("2026-08-21 09:01 AM")

    assert module.extract_latest_sms_code(
        page_text,
        not_before=requested_at,
        now=now,
    ) == "405965"


def test_verification_waits_ten_seconds_after_request_before_fetching_sms(
    monkeypatch,
) -> None:
    module = load_guest_module()
    current_time = [100.0]
    events: list[tuple[str, float]] = []
    candidate = module.NavigationCandidate(None, 0, {}, None, 0, {}, "press")

    monkeypatch.setenv("APPLE_ACCOUNT_SMS_URL", "https://sms.example.test/latest")
    monkeypatch.setattr(module.time, "time", lambda: current_time[0])

    def sleep(seconds: float) -> None:
        events.append(("sleep", seconds))
        current_time[0] += seconds

    def fetch_code(_sms_url: str, *, not_before: float | None = None) -> str:
        events.append(("fetch", current_time[0]))
        assert not_before == 100.0
        return "405965"

    monkeypatch.setattr(module.time, "sleep", sleep)
    monkeypatch.setattr(module, "current_search_roots", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(module, "find_verification_code_fields", lambda _roots: [object()])
    monkeypatch.setattr(module, "fetch_latest_sms_code", fetch_code)
    monkeypatch.setattr(module, "set_verification_code", lambda _fields, _code: 0)
    monkeypatch.setattr(
        module,
        "find_enabled_pressable_text_candidate",
        lambda _roots, _text: candidate,
    )
    monkeypatch.setattr(module, "activate", lambda _candidate: 0)
    monkeypatch.setattr(module, "is_signed_in_apple_account_page", lambda *_args: True)

    result = module.complete_verification_code_workflow(
        123,
        "APPLE_ACCOUNT_SMS_URL",
        "account@example.test",
        verification_requested_at=100.0,
    )

    assert result == 0
    assert events[:2] == [("sleep", 10.0), ("fetch", 110.0)]
