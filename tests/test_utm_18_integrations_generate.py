"""Regression: integrations reuses disk key or generates via UI."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUEST = (ROOT / "scripts" / "utm_18_existing_guest.py").read_text(encoding="utf-8")


def _integrations_body() -> str:
    start = GUEST.index("def integrations(self):")
    end = GUEST.index("def _existing_key_from_disk(self):")
    return GUEST[start:end]


def test_integrations_prefers_disk_then_generate_ui() -> None:
    body = _integrations_body()
    assert "_existing_key_from_disk" in body
    assert "EXISTING_KEY_ON_DISK_REQUIRED" not in GUEST
    assert "access/integrations" in body
    assert "_generate_and_download_api_key" in body
    assert "Generate API Key" in GUEST
    assert "click_plus_beside_active" in GUEST
    assert "Admin" in GUEST
    assert "AuthKey_" in GUEST


def test_privacy_no_collect_not_regressed() -> None:
    assert "CONFIRM_COLLECT_DATA_radio_false" in GUEST
    assert "CONFIRM_COLLECT_DATA_radio_true" not in GUEST
    assert "Set Up Device ID" not in GUEST
    assert "SELECT_CATEGORIES_checkbox_DEVICE_ID" not in GUEST


def test_configuration_still_consumes_integration_state() -> None:
    start = GUEST.index("def configuration(self):")
    end = GUEST.index("def run(self):")
    body = GUEST[start:end]
    assert "self.state['integration']" in body
    assert "issuer_id:" in body
    assert "private_key_path:" in body
