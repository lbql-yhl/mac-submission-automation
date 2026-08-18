from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mac_password_prompt as prompt  # noqa: E402


def test_secure_field_accepts_exact_length_when_macos_uses_private_mask_glyphs(
    monkeypatch,
) -> None:
    synthetic_value = "9072"
    monkeypatch.setattr(prompt, "guest_password", lambda: synthetic_value)
    secure_info = {"role": "AXTextField", "subrole": "AXSecureTextField"}

    assert prompt.mac_password_readback_matches("◦" * len(synthetic_value), secure_info)
    assert not prompt.mac_password_readback_matches("◦" * (len(synthetic_value) - 1), secure_info)


def test_nonsecure_field_uses_the_runtime_password_or_known_mask(monkeypatch) -> None:
    synthetic_value = "9072"
    monkeypatch.setattr(prompt, "guest_password", lambda: synthetic_value)
    plain_info = {"role": "AXTextField", "subrole": None}

    assert prompt.mac_password_readback_matches(synthetic_value, plain_info)
    assert prompt.mac_password_readback_matches("•" * len(synthetic_value), plain_info)
    assert not prompt.mac_password_readback_matches("◦" * len(synthetic_value), plain_info)


def test_prompt_source_has_no_import_time_password_capture() -> None:
    source = (ROOT / "scripts" / "mac_password_prompt.py").read_text(encoding="utf-8")

    assert "guest_password()" in source
    assert "MAC_PASSWORD_VALUE" not in source
