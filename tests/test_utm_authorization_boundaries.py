from pathlib import Path

import pytest

from skill_contract_assertions import assert_shared_contract_reference


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
SHARED_CONTRACT = SKILLS / "_shared" / "AUTOMATION_CONTRACT.md"
HIGH_RISK_SKILLS = (
    "utm-vm-clone",
    "utm-clash-ip",
    "utm-edit",
    "utm-key",
    "utm-apps",
    "utm-business",
    "utm-image",
    "utm-p8",
    "utm-21",
    "utm-22",
    "utm-23",
    "utm-24",
)

EXPLICIT_AUTHORIZATION = (
    "有状态或破坏性动作，只能在用户对精确对象与范围明确授权后执行"
)
NO_AMBIGUOUS_EXPANSION = "授权不得从“继续”“完成”或其他模糊用语扩张"


def test_shared_contract_preserves_the_project_authorization_boundary() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    shared = SHARED_CONTRACT.read_text(encoding="utf-8")

    for required in (EXPLICIT_AUTHORIZATION, NO_AMBIGUOUS_EXPANSION):
        assert required in agents
        assert required in shared


@pytest.mark.parametrize("skill_name", HIGH_RISK_SKILLS)
def test_high_risk_skills_inherit_authorization_instead_of_redefining_it(
    skill_name: str,
) -> None:
    skill_file = SKILLS / skill_name / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")

    assert_shared_contract_reference(skill_file, text, SHARED_CONTRACT)


def test_authorized_replacement_is_bound_to_one_exact_image_operation() -> None:
    image = (SKILLS / "utm-image" / "SKILL.md").read_text(encoding="utf-8")

    assert "user-authorized replacement" in image
    assert "--force-development --replace-existing" in image
    assert "These flags are inseparable for replacement" in image
    assert "clear only that target panel" in image


def test_irreversible_or_unknown_results_are_never_replayed_speculatively() -> None:
    shared = SHARED_CONTRACT.read_text(encoding="utf-8")

    assert "Perform one minimum action." in shared
    assert "must never be repeated speculatively" in shared
    assert "Never hand off a partial, blocked, ambiguous, or result-unknown state." in shared
