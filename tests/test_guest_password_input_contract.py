from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUEST = ROOT / "scripts" / "find_system_settings_general.py"


def _function_source(name: str, next_name: str) -> str:
    source = GUEST.read_text(encoding="utf-8")
    start = source.index(f"def {name}(")
    end = source.index(f"\ndef {next_name}(", start)
    return source[start:end]


def test_password_change_wakes_the_button_with_a_verified_final_key_event() -> None:
    source = _function_source(
        "set_password_change_field", "handle_sign_out_other_devices_prompt"
    )
    assert "set_login_field(element, value[:-1])" in source
    assert "prefix_length != len(value) - 1" in source
    assert "CGEventCreateKeyboardEvent" in source
    assert "CGEventKeyboardSetUnicodeString(key_down, 1, value[-1])" in source
    assert "CGEventPost(QUARTZ.kCGHIDEventTap, key_down)" in source
    assert "full_length == len(value)" in source
    assert 'return AX.kAXErrorSuccess, "verified"' in source


def test_password_wakeup_does_not_depend_on_system_events_consent() -> None:
    whole_source = GUEST.read_text(encoding="utf-8")
    function = _function_source(
        "set_password_change_field", "handle_sign_out_other_devices_prompt"
    )
    assert "handle_system_events_consent_prompt" not in whole_source
    assert "System Events" not in whole_source
    assert "AX.kAXFrontmostAttribute" in function
    assert "AX.kAXFocusedAttribute" in function
    assert "QUARTZ.kCGHIDEventTap" in function


def test_password_change_keeps_other_devices_signed_in() -> None:
    whole_source = GUEST.read_text(encoding="utf-8")
    function = _function_source(
        "handle_sign_out_other_devices_prompt",
        "close_system_settings_after_password_change",
    )
    assert (
        'SIGN_OUT_OTHER_DEVICES_TEXT = "Sign out other devices using your Apple Account?"'
        in whole_source
    )
    assert "DONT_SIGN_OUT_TEXTS" in whole_source
    assert "tree_contains_text(roots, SIGN_OUT_OTHER_DEVICES_TEXT)" in function
    assert 'tree_contains_text(roots, "Sign out other devices")' in function
    assert "tree_contains_text(roots, APPLE_ACCOUNT_TEXT)" in function
    assert "for label in DONT_SIGN_OUT_TEXTS" in function
    assert 'print("PASSWORD_CHANGE_OTHER_DEVICES=kept_signed_in")' in function
