#!/usr/bin/env python3

from skill_contract_assertions import assert_shared_contract_reference
from test_segmented_skill_command_contract import (
    ENTRY_SCRIPTS,
    ORDERED,
    ROOT,
    _contract_text,
    _skill_path,
    _skill_text,
)


SHARED_CONTRACT = ROOT / "skills" / "_shared" / "AUTOMATION_CONTRACT.md"
BOOTSTRAP = 'eval "$(python3 scripts/preflight.py --project-only --emit-shell)"'


def test_contract() -> None:
    shared = SHARED_CONTRACT.read_text(encoding="utf-8")
    for heading in (
        "Portable bootstrap",
        "Immutable run context",
        "One public host entry",
        "Observe, act, verify",
        "Bounded recovery",
        "Continuous handoff",
    ):
        assert f"## {heading}" in shared, heading
    assert BOOTSTRAP in shared

    problems = []
    for name in ORDERED:
        skill_file = _skill_path(name)
        text = _skill_text(name)
        try:
            assert_shared_contract_reference(skill_file, text, SHARED_CONTRACT)
        except AssertionError as error:
            problems.append(str(error))
        if BOOTSTRAP not in text:
            problems.append(f"{name}: missing portable bootstrap")
        if f"$PROJECT_ROOT/{ENTRY_SCRIPTS[name]}" not in text:
            problems.append(f"{name}: missing portable public entry")

    for name in ORDERED[:12]:
        try:
            contract = _contract_text(name)
            assert "public host entry" in contract, (
                "missing public entry responsibility"
            )
        except AssertionError as error:
            problems.append(f"{name}: {error}")

    text = _skill_text("utm-21")
    if "完整 UTM-21 工作流" not in text:
        problems.append("utm-21: missing complete workflow responsibility")
    if "VISUAL_CONTROL=forbidden" not in text:
        problems.append("utm-21: visual control is not forbidden")
    if "AGENT_CONTROL=forbidden" not in text:
        problems.append("utm-21: agent control is not forbidden")

    text = _skill_text("utm-23")
    if "complete App Store Connect browser workflow" not in text:
        problems.append("utm-23: missing complete browser-workflow responsibility")
    if "scripts/utm_23.py" not in text:
        problems.append("utm-23: missing complete public host entry")
    if "VISUAL_BROWSER_CONTROL=forbidden" not in text:
        problems.append("utm-23: visual browser control is not forbidden")
    if "SUBAGENT_BROWSER_CONTROL=forbidden" not in text:
        problems.append("utm-23: subagent browser control is not forbidden")

    for name in ("utm-24",):
        text = _skill_text(name)
        lowered = text.casefold()
        if "browser-session entry helper" not in text:
            problems.append(f"{name}: missing browser-helper responsibility")
        if "session.mjs" not in text or "inspect" not in text:
            problems.append(f"{name}: missing session inspection entry")
        if f"complete `{name}` wrapper" not in text or not any(
            token in lowered for token in ("no complete", "does not")
        ):
            problems.append(f"{name}: browser helper claims full-skill responsibility")

    assert not problems, "\n".join(problems)
    print("DETAILED_SKILL_CONTRACT=verified")


if __name__ == "__main__":
    test_contract()
