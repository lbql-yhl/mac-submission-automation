from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mac_password_prompt as prompt


def test_secure_field_accepts_exact_length_when_macos_uses_private_mask_glyphs() -> None:
    secure_info = {"role": "AXTextField", "subrole": "AXSecureTextField"}

    assert prompt.mac_password_readback_matches("◦◦◦◦", secure_info)
    assert not prompt.mac_password_readback_matches("◦◦◦", secure_info)


def test_nonsecure_field_still_requires_exact_value_or_known_mask() -> None:
    plain_info = {"role": "AXTextField", "subrole": None}

    assert prompt.mac_password_readback_matches("1234", plain_info)
    assert prompt.mac_password_readback_matches("••••", plain_info)
    assert not prompt.mac_password_readback_matches("◦◦◦◦", plain_info)
