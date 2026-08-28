#!/usr/bin/env python3
from pathlib import Path

import pytest

from skill_contract_assertions import assert_shared_contract_reference


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
SHARED_CONTRACT = SKILLS / "_shared" / "AUTOMATION_CONTRACT.md"
SKILL_NAMES = (
    "utm-vm-clone",
    "utm-notion",
    "utm-clash-ip",
    "utm-login",
    "utm-edit",
    "utm-key",
    "utm-apps",
    "utm-business",
    "utm-env",
    "utm-script",
    "utm-image",
    "utm-p8",
    "utm-21",
    "utm-22",
    "utm-23",
    "utm-24",
)


def test_shared_contract_keeps_fault_notification_behind_bounded_recovery() -> None:
    shared = SHARED_CONTRACT.read_text(encoding="utf-8")

    for required in (
        "Retry only the exact failed checkpoint while preserving the same run and target.",
        "at most three rounds with delays of 0, 5, and 10 seconds",
        "diagnose, apply one safe reversible repair, then independently reverify",
        "Only after the bounded budget is exhausted",
        "three read-only checks prove an external state",
        "must never be repeated speculatively",
        "attempt count, recovery actions, and last verified checkpoint",
    ):
        assert required in shared

    assert shared.index("skill-failure") < shared.index("notify-fault")
    assert shared.index("notify-fault") < shared.index("wait-decision")


def test_shared_contract_keeps_feishu_delivery_on_the_exact_project_route() -> None:
    shared = SHARED_CONTRACT.read_text(encoding="utf-8")

    for required in (
        "FEISHU_ALLOWED_CHAT_ID",
        "one exact project-group route",
        "requires returned message IDs and delivery verification",
        "reports only redacted verification markers",
        "never prints configured identifiers or API payloads",
        "exactly three actions: `stop`; `manual_continue`",
        "`retry_skill`",
    ):
        assert required in shared


@pytest.mark.parametrize("skill_name", SKILL_NAMES)
def test_every_skill_inherits_the_shared_recovery_contract(skill_name: str) -> None:
    skill_file = SKILLS / skill_name / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")

    assert_shared_contract_reference(skill_file, text, SHARED_CONTRACT)
