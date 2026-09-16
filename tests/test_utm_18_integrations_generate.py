"""Regression: trimmed Integrations Generate API Key path."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUEST = (ROOT / "scripts" / "utm_18_existing_guest.py").read_text(encoding="utf-8")


def _integrations_body() -> str:
    start = GUEST.index("def integrations(self):")
    end = GUEST.index("def description(self):")
    return GUEST[start:end]


def test_integrations_only_generate_api_key_no_active_fallback() -> None:
    assert "click_plus_beside_active" not in GUEST
    assert "def begin_key_generation" not in GUEST
    assert "def integration_values" not in GUEST
    body = _integrations_body()
    assert "Generate API Key" in body
    assert "Active" not in body or "click_plus" not in GUEST
    assert "INTEGRATIONS_ENTRY_MISSING" in body


def test_integrations_reads_dialog_fields_only() -> None:
    assert "_values_from_visible_key_fields" in GUEST
    assert "integration_values(" not in GUEST
    assert "AXRow" not in GUEST[GUEST.index("_values_from_visible_key_fields"):GUEST.index("def integrations")]


def test_integrations_p8_downloads_only_no_config_copy() -> None:
    assert "_downloads_p8_for_key" in GUEST
    assert "_ensure_p8_in_downloads" not in GUEST
    assert "shutil.copy2" not in _integrations_body()
    helper = GUEST[
        GUEST.index("def _downloads_p8_for_key") : GUEST.index("def _values_from_visible_key_fields")
    ]
    assert "apple-store-bm" not in helper
    assert "self.downloads" in helper


def test_integrations_resumes_via_substeps_without_reopen() -> None:
    body = _integrations_body()
    assert body.count("self.open(") == 1
    assert "if step == 'open':" in body
    assert "integrations_step" in GUEST


def test_privacy_and_configuration_untouched() -> None:
    assert "CONFIRM_COLLECT_DATA_radio_false" in GUEST
    assert "Set Up Device ID" not in GUEST
    start = GUEST.index("def configuration(self):")
    end = GUEST.index("def run(self):")
    body = GUEST[start:end]
    assert "self.state['integration']" in body
    assert "apple-store-bm" in body
