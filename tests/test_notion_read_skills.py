import ast
from pathlib import Path

import pytest

from skill_contract_assertions import assert_shared_contract_reference


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
SHARED_CONTRACT = SKILLS / "_shared" / "AUTOMATION_CONTRACT.md"

NOTION_SKILLS = (
    "utm-notion",
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
    "utm-24",
)

DIRECT_NOTION_API_ENTRIES = (
    "utm_notion.py",
    "utm_7_login.py",
    "utm_8_change_password.py",
    "utm_9.py",
    "utm_apps.py",
    "utm_business.py",
    "utm_18.py",
    "utm_image.py",
    "utm_21_clone.py",
)

API_ONLY_BOUNDARIES = (
    "只有 Feishu OpenAPI 接口可读取 Feishu 资源",
    "只有 Notion API 接口可读写 Notion 资源",
    "scripts/notion_api.py",
    "不得用宿主 Chrome、Notion 插件、CUA、坐标或浏览器剪贴板读写 Notion",
    "Wiki URL 路由和 Base 三元组路由必须二选一且不得混用",
)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_shared_contract_carries_the_authoritative_api_only_boundaries() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    shared = SHARED_CONTRACT.read_text(encoding="utf-8")

    for required in API_ONLY_BOUNDARIES:
        assert required in agents
        assert required in shared


@pytest.mark.parametrize("skill_name", NOTION_SKILLS)
def test_notion_using_skills_inherit_the_shared_api_boundary(skill_name: str) -> None:
    skill_file = SKILLS / skill_name / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")

    assert_shared_contract_reference(skill_file, text, SHARED_CONTRACT)


@pytest.mark.parametrize("script_name", DIRECT_NOTION_API_ENTRIES)
def test_public_entries_import_the_project_notion_api(script_name: str) -> None:
    modules = imported_modules(ROOT / "scripts" / script_name)
    assert "scripts.notion_api" in modules, script_name


def test_indirect_notion_entries_still_route_through_project_wrappers() -> None:
    env_source = (ROOT / "scripts" / "utm_env.py").read_text(encoding="utf-8")
    p8_source = (ROOT / "scripts" / "utm_p8.py").read_text(encoding="utf-8")

    assert "from scripts.utm_env_generate import generate_env_from_notion" in env_source
    assert 'NOTION_API = PROJECT_ROOT / "scripts" / "notion_api.py"' in p8_source
