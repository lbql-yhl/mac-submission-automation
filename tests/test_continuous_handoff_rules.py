#!/usr/bin/env python3
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills"

ORDERED = (
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

MARKERS = {
    "utm-vm-clone": "UTM_CLONE_AND_INITIALIZE=verified",
    "utm-notion": "status=verified",
    "utm-clash-ip": "UTM_CLASH_IP=verified",
    "utm-login": "UTM_7=verified",
    "utm-edit": "UTM_8=verified",
    "utm-key": "UTM_9=verified",
    "utm-apps": "UTM_APPS=verified",
    "utm-business": "UTM_BUSINESS=verified",
    "utm-env": "UTM_ENV=verified",
    "utm-script": "UTM_18=verified",
    "utm-image": "UTM_19=verified",
    "utm-p8": "UTM_P8=verified",
    "utm-21": "UTM_21=verified",
    "utm-22": "UTM_22=verified",
    "utm-23": "UTM_23=verified",
    "utm-24": "UTM_24=verified",
}

SEGMENT_TAILS = {
    "utm-vm-clone": "utm-notion",
    "utm-business": "utm-env",
    "utm-p8": "utm-21",
}


def read_skill(name: str) -> str:
    return (SKILL_ROOT / name / "SKILL.md").read_text(encoding="utf-8")


def result_section(name: str) -> str:
    text = read_skill(name)
    heading = "Result and endpoint" if name == "utm-24" else "Result and handoff"
    marker = f"## {heading}"
    if marker not in text:
        return ""
    body = text.split(marker, 1)[1]
    return body.split("\n## ", 1)[0]


def test_agents_order_matches_the_handoff_chain() -> None:
    assert len(ORDERED) == len(MARKERS) == 16
    assert len(set(ORDERED)) == 16

    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    current_line = next(
        line
        for line in agents.splitlines()
        if line.startswith("- Current skills in exact order:")
    )
    assert tuple(re.findall(r"`([^`]+)`", current_line)) == ORDERED


def test_each_skill_owns_its_canonical_success_marker() -> None:
    missing = tuple(
        name for name in ORDERED if MARKERS[name] not in result_section(name)
    )
    assert missing == (), f"missing canonical success markers: {missing}"


def test_each_successful_skill_hands_the_same_context_to_the_next_skill() -> None:
    missing = tuple(
        (name, next_name)
        for name, next_name in zip(ORDERED, ORDERED[1:])
        if f"`{next_name}`" not in result_section(name)
    )
    endpoint = result_section("utm-24")
    assert "end the workflow" in endpoint
    assert not any(f"`{name}`" in endpoint for name in ORDERED[:-1])
    assert missing == (), f"missing handoffs: {missing}"


def test_segment_tails_make_cross_segment_handoffs_conditional() -> None:
    invalid = []
    for name, next_name in SEGMENT_TAILS.items():
        result = result_section(name).casefold()
        if (
            f"`{next_name}`" not in result
            or "segment" not in result
            or not any(token in result for token in ("if ", "unless"))
        ):
            invalid.append(name)
    assert not invalid, f"invalid conditional segment handoffs: {tuple(invalid)}"


def test_only_the_workflow_endpoint_owns_automatic_review_approval() -> None:
    owners = tuple(
        name for name in ORDERED if "record-auto-review-approval" in read_skill(name)
    )
    assert owners == ("utm-24",)

    shared = (SKILL_ROOT / "_shared" / "AUTOMATION_CONTRACT.md").read_text(
        encoding="utf-8"
    )
    assert "## Continuous handoff" in shared
    assert "`utm-24`" in shared

    print("CONTINUOUS_HANDOFF_RULES=verified")


if __name__ == "__main__":
    test_agents_order_matches_the_handoff_chain()
    test_each_skill_owns_its_canonical_success_marker()
    test_each_successful_skill_hands_the_same_context_to_the_next_skill()
    test_segment_tails_make_cross_segment_handoffs_conditional()
    test_only_the_workflow_endpoint_owns_automatic_review_approval()
