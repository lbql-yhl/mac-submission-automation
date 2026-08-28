#!/usr/bin/env python3
from pathlib import Path

from scripts import utm_18


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/utm-script/SKILL.md"
ENTRY = "$PROJECT_ROOT/scripts/utm_18.py"


def test_utm_script_skill_publishes_only_the_complete_host_entry() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert skill.count(ENTRY) == 1
    for required in (
        "Only public host entry",
        "--run-id '<run-id>'",
        "--page-title '<page-title>'",
        "Preserve the current attempt ledger and browser identity",
        "UTM_18=verified",
        "utm-image",
    ):
        assert required in skill, required
    for helper in ("utm_18_edge.py", "utm_18_ssh.py", "utm_18_attempt.py"):
        assert helper not in skill


def test_utm_18_entry_supports_exact_selectors_and_preserves_failure_detail() -> None:
    run_args = utm_18.build_parser().parse_args(
        [
            "--run-id",
            "run-12345678",
            "--vm-name",
            "abcd",
            "--vm-ip",
            "192.0.2.10",
            "--vm-user",
            "abcd",
        ]
    )
    direct_args = utm_18.build_parser().parse_args(
        [
            "--page-title",
            "Example-abcd",
            "--vm-name",
            "abcd",
            "--vm-ip",
            "192.0.2.10",
            "--vm-user",
            "abcd",
        ]
    )

    assert run_args.run_id == "run-12345678"
    assert direct_args.page_title == "Example-abcd"
    result = utm_18.AttemptResult(
        "blocked",
        "business_error",
        reason="remote summary was not verified",
    )
    assert utm_18._attempt_failure_message(result) == (
        "FILL_DESCRIPTION_BLOCKED=blocked:business_error;"
        "remote summary was not verified"
    )
