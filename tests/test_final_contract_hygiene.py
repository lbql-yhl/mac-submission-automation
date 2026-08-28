import ast
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
DOCS = tuple((ROOT / "docs").rglob("*.md"))
SEARCHABLE_CONTRACTS = DOCS + (
    ROOT / "README.md",
    ROOT / "AGENTS.md",
    ROOT / "skills/utm-24/SKILL.md",
    ROOT / "skills/utm-p8/SKILL.md",
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_string(node.left)
        right = _constant_string(node.right)
        if left is not None or right is not None:
            return (left or "{dynamic}") + (right or "{dynamic}")
    if isinstance(node, ast.JoinedStr):
        return "".join(
            value.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
            else "{dynamic}"
            for value in node.values
        )
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "join"
        and len(node.args) == 1
        and not node.keywords
        and isinstance(node.args[0], (ast.List, ast.Tuple))
    ):
        separator = _constant_string(node.func.value)
        if separator is not None:
            return separator.join(
                _constant_string(value) or "{dynamic}" for value in node.args[0].elts
            )
    return None


def _removed_runbook_literal(node: ast.AST) -> str | None:
    value = _constant_string(node)
    if value is None:
        return None
    normalized = value.replace("\\", "/").rstrip("/")
    name = normalized.rsplit("/", 1)[-1]
    if name == "feishu-host-routing.md":
        return normalized
    if name.startswith("utm-") and name.endswith(".md"):
        if name != "utm-feishu-bot.md":
            return normalized
    return None


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _qualified_name(node.value)
        if owner is not None:
            return f"{owner}.{node.attr}"
    return None


def _existence_target(node: ast.AST) -> ast.AST | None:
    if not isinstance(node, ast.Call):
        return None
    function = node.func
    if (
        isinstance(function, ast.Attribute)
        and function.attr in {"exists", "is_file"}
        and not node.args
        and not node.keywords
    ):
        return function.value
    if (
        _qualified_name(function) in {"os.path.exists", "os.path.isfile"}
        and len(node.args) == 1
        and not node.keywords
    ):
        return node.args[0]
    return None


def _negative_existence_target(node: ast.AST) -> ast.AST | None:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _existence_target(node.operand)
    if (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], (ast.Is, ast.Eq))
        and len(node.comparators) == 1
    ):
        left = node.left
        right = node.comparators[0]
        if isinstance(right, ast.Constant) and right.value is False:
            return _existence_target(left)
        if isinstance(left, ast.Constant) and left.value is False:
            return _existence_target(right)
    return None


def _unittest_assert_false_target(node: ast.AST) -> ast.AST | None:
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "assertFalse"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
    ):
        return None
    keywords = {keyword.arg: keyword.value for keyword in node.keywords}
    if None in keywords or len(keywords) != len(node.keywords):
        return None
    if len(node.args) == 1 and set(keywords) <= {"msg"}:
        expression = node.args[0]
    elif len(node.args) == 2 and not keywords:
        expression = node.args[0]
    elif not node.args and set(keywords) in ({"expr"}, {"expr", "msg"}):
        expression = keywords["expr"]
    else:
        return None
    return _existence_target(expression)


def _negative_guard_path_nodes(tree: ast.AST) -> set[ast.AST]:
    allowed: set[ast.AST] = set()
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.Assert):
            target = _negative_existence_target(node.test)
        elif isinstance(node, ast.Expr):
            target = _unittest_assert_false_target(node.value)
        if target is not None:
            allowed.update(ast.walk(target))
    return allowed


def _removed_runbook_references(tree: ast.AST) -> set[tuple[int, str]]:
    allowed = _negative_guard_path_nodes(tree)
    hits: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if node in allowed:
            continue
        reference = _removed_runbook_literal(node)
        if reference is not None:
            hits.add((node.lineno, reference))
    return hits


def test_searchable_docs_do_not_restate_superseded_final_stage_contracts() -> None:
    forbidden = (
        "成功后发送无按钮通知卡",
        "成功通知卡仅在 App Store 状态明确成功后发送一次",
        "App Store 明确显示 `Waiting for Review` 或 `15 Items Submitted` 后发送一次绿色成功通知卡",
        "当前 30 个技能",
        "登记的 30 个技能",
        "当前 30-skill",
        "current 30-skill",
        "本项目 30 技能",
    )
    hits = []
    for path in SEARCHABLE_CONTRACTS:
        text = _text(path)
        for phrase in forbidden:
            if phrase in text:
                try:
                    label = path.relative_to(ROOT)
                except ValueError:
                    label = path
                hits.append(f"{label}: {phrase}")
    assert not hits, "stale searchable contracts:\n" + "\n".join(hits)


def test_historical_execution_contracts_are_absent() -> None:
    assert not (ROOT / "docs/superpowers").exists()


def test_contract_tests_do_not_reference_removed_skill_runbooks() -> None:
    hits = set()
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(_text(path), filename=str(path))
        ignored_lines: set[int] = set()
        if path.resolve() == Path(__file__).resolve():
            detector = next(
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "_removed_runbook_literal"
            )
            ignored_lines.update(range(detector.lineno, detector.end_lineno + 1))
        for line, reference in _removed_runbook_references(tree):
            if line not in ignored_lines:
                hits.add(f"{path.relative_to(ROOT)}:{line}: {reference}")
    assert not hits, "removed runbook references:\n" + "\n".join(sorted(hits))


def test_removed_runbook_detector_handles_literals_and_exact_negative_guards() -> None:
    positive_sources = (
        '(Path("docs") / "utm-old.md").read_text()',
        'ROOT.joinpath("docs", "utm-old.md").read_text()',
        '(ROOT / "docs" / "feishu-host-routing.md").read_text()',
        'DOCS = ROOT / "docs"\n_text(DOCS / "utm-old.md")',
        'p = ROOT / "docs" / "utm-old.md"\n_text(p)\np = Path("current.md")',
        'consume([ROOT / "docs" / "utm-old.md"])',
        'consume({"path": ROOT / "docs" / "utm-old.md"})',
        '@pytest.mark.parametrize("path", [ROOT / "docs" / "utm-old.md"])\ndef test_contract(path): pass',
        'stage = "old"\nconsume(ROOT / "docs" / f"utm-{stage}.md")',
        'consume(ROOT / "docs" / f"utm-{\'old\'}.md")',
        'stage = "old"\nconsume(ROOT / "docs" / ("utm-" + stage + ".md"))',
        'stage = "old"\nconsume(ROOT / "docs" / "".join(("utm-", stage, ".md")))',
        'consume(ROOT / "docs" / "utm-%s.md")',
        'consume(ROOT / "docs" / "utm-{}.md")',
        'consume(ROOT / "docs" / "utm-*.md")',
    )
    for source in positive_sources:
        assert _removed_runbook_references(ast.parse(source)), source

    negative_source = "\n".join(
        (
            'assert not (ROOT / "docs" / "utm-old.md").exists()',
            'assert (ROOT / "docs" / "utm-old.md").exists() is False',
            'self.assertFalse((ROOT / "docs" / "utm-old.md").is_file())',
            'self.assertFalse((ROOT / "docs" / "utm-old.md").exists(), msg="gone")',
            'assert not os.path.exists(ROOT / "docs" / "utm-old.md")',
        )
    )
    assert not _removed_runbook_references(ast.parse(negative_source))

    bypass_sources = (
        'assert not (ROOT / "docs" / "utm-old.md").exists() or True',
        'assert not accepts((ROOT / "docs" / "utm-old.md").exists())',
        'self.assertFalse((ROOT / "docs" / "utm-old.md").exists() and False)',
        'noop.assertFalse((ROOT / "docs" / "utm-old.md").exists())',
        'assert not ((ROOT / "docs" / "utm-old.md").exists() == expected)',
        'old = ROOT / "docs" / "utm-old.md"\nassert not old.exists()',
    )
    for source in bypass_sources:
        assert _removed_runbook_references(ast.parse(source)), source


def test_every_test_module_is_collected_by_pytest() -> None:
    paths = sorted((ROOT / "tests").rglob("test_*.py"))
    environment = dict(os.environ)
    environment.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            *(str(path.relative_to(ROOT)) for path in paths),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    collected = {
        line.split("::", 1)[0] for line in completed.stdout.splitlines() if "::" in line
    }
    missing = [
        str(path.relative_to(ROOT))
        for path in paths
        if str(path.relative_to(ROOT)) not in collected
    ]
    assert not missing, "test modules skipped by pytest:\n" + "\n".join(missing)


def test_current_authority_and_notion_scope_are_unambiguous() -> None:
    readme = _text(ROOT / "README.md")
    agents = _text(ROOT / "AGENTS.md")
    assert "项目内 `skills/` 是唯一技能源" in readme
    assert "项目内 `skills/` 是 16 个主线技能的唯一正文源" in agents
    assert "项目采用 16 个主线技能" in readme
    assert "utm-p8" in readme
    assert (ROOT / "skills/_shared/AUTOMATION_CONTRACT.md").is_file()
