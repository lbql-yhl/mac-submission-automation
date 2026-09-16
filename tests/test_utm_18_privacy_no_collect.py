"""Regression: App Privacy Get Started selects no-collect and skips Device ID."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUEST = (ROOT / "scripts" / "utm_18_existing_guest.py").read_text(encoding="utf-8")


def test_privacy_get_started_selects_no_collect_and_saves() -> None:
    assert "CONFIRM_COLLECT_DATA_radio_false" in GUEST
    assert "CONFIRM_COLLECT_DATA_radio_true" not in GUEST
    assert "SELECT_CATEGORIES_checkbox_DEVICE_ID" not in GUEST
    assert "Set Up Device ID" not in GUEST
    assert "SELECT_PURPOSES_checkbox_THIRD_PARTY_ADVERTISING" not in GUEST
    assert "CONFIRM_LINKING_DEVICE_ID_radioButton_false" not in GUEST
    assert "CONFIRM_TRACKING_DEVICE_ID_radioButton_true" not in GUEST
    # Get Started path must Save (not Next into categories).
    start = GUEST.index("def privacy(self):")
    end = GUEST.index("def pricing(self):")
    body = GUEST[start:end]
    assert "Get Started" in body
    assert "self.save()" in body
    assert "SELECT_CATEGORIES" not in body


def test_privacy_keeps_url_fill_and_publish() -> None:
    start = GUEST.index("def privacy(self):")
    end = GUEST.index("def pricing(self):")
    body = GUEST[start:end]
    assert "privacyPolicyUrl" in body
    assert "privacyChoicesUrl" in body
    assert "PRIVACY_POLICY_URL" in body
    assert "PRIVACY_CHOICES_URL" in body
    assert "Publish" in body
    assert "Published" in body
    assert "checkpoint('privacy')" in body
