"""Regression: integrations UI-only with mid-attempt resume."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUEST = (ROOT / "scripts" / "utm_18_existing_guest.py").read_text(encoding="utf-8")


def _integrations_body() -> str:
    start = GUEST.index("def integrations(self):")
    end = GUEST.index("def description(self):")
    return GUEST[start:end]


def test_integrations_opens_ui_without_disk_first() -> None:
    body = _integrations_body()
    assert "_existing_key_from_disk" not in GUEST
    assert "EXISTING_KEY_ON_DISK_REQUIRED" not in GUEST
    assert "access/integrations" in body
    assert "Request Access" in body
    assert "Generate API Key" in body
    assert "Admin" in body
    assert "Download" in body


def test_integrations_resumes_via_substeps_without_reopen() -> None:
    body = _integrations_body()
    assert "integrations_step" in GUEST
    assert "_set_integrations_step" in GUEST
    # open URL only in the open step
    assert body.count("self.open(") == 1
    assert "if step == 'open':" in body
    for step in (
        "request_access",
        "open_generate",
        "fill_name",
        "select_admin",
        "click_generate",
        "read_values",
        "download",
    ):
        assert f"if step == '{step}':" in body


def test_privacy_no_collect_not_regressed() -> None:
    assert "CONFIRM_COLLECT_DATA_radio_false" in GUEST
    assert "CONFIRM_COLLECT_DATA_radio_true" not in GUEST
    assert "Set Up Device ID" not in GUEST


def test_configuration_still_consumes_integration_state() -> None:
    start = GUEST.index("def configuration(self):")
    end = GUEST.index("def run(self):")
    body = GUEST[start:end]
    assert "self.state['integration']" in body
    assert "issuer_id:" in body
    assert "private_key_path:" in body
