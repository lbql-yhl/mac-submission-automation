# UTM Clone Ordered External Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Select the first authorized external VM directory that can hold one clone while retaining 300 decimal GB, then keep that exact directory bound through initialization.

**Architecture:** Parse an ordered JSON path list in `services.project_paths`, while retaining the existing single-directory fallback. Keep destination selection in `scripts.utm_clone_macos`; after the clone, derive the selected directory from the independently verified inventory record and inject it only into the post-clone child environment.

**Tech Stack:** Python 3, `pathlib`, `json`, `plistlib`, macOS `diskutil`, `pytest`.

---

### Task 1: Parse Ordered VM Image Directories

**Files:**
- Modify: `tests/test_project_paths.py`
- Modify: `services/project_paths.py`
- Modify: `scripts/preflight.py`

- [ ] **Step 1: Write failing parser tests**

Add tests that call `configured_paths` with a JSON list, preserve its order,
resolve each path, reject malformed/non-list/empty/duplicate values with a
non-sensitive `ConfigurationError`, and return the legacy path when the new
setting is blank.

```python
def test_configured_paths_preserves_order(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    monkeypatch.setenv(
        "SUBMISSION_TEST_PATHS", json.dumps([str(first), str(second)])
    )
    assert project_paths.configured_paths(
        "SUBMISSION_TEST_PATHS", (tmp_path / "legacy",)
    ) == (first, second)
```

- [ ] **Step 2: Run the parser tests and verify RED**

Run: `python3 -m pytest tests/test_project_paths.py -q`

Expected: FAIL because `configured_paths` and `VM_IMAGES_DIRS` do not exist.

- [ ] **Step 3: Implement ordered path parsing**

In `services/project_paths.py`, import `json` and `ConfigurationError`, add:

```python
def configured_paths(name: str, default: tuple[Path, ...]) -> tuple[Path, ...]:
    raw = optional_setting(name, env_path=SOURCE_ROOT / ".env")
    if not raw:
        return tuple(path.expanduser().resolve() for path in default)
    try:
        values = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise ConfigurationError(f"invalid host setting: {name}") from error
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(value, str) or not value.strip() for value in values)
    ):
        raise ConfigurationError(f"invalid host setting: {name}")
    paths = tuple(
        Path(os.path.expandvars(os.path.expanduser(value))).resolve()
        for value in values
    )
    if len(set(paths)) != len(paths):
        raise ConfigurationError(f"invalid host setting: {name}")
    return paths
```

Build `VM_IMAGES_DIRS` from `SUBMISSION_VM_IMAGES_DIRS`, with the existing
`SUBMISSION_VM_IMAGES_DIR` value as its one-item default, and set
`VM_IMAGES_DIR = VM_IMAGES_DIRS[0]` for legacy consumers. Export the JSON list
from `scripts/preflight.py` without printing it in ordinary status output.

- [ ] **Step 4: Run parser tests and verify GREEN**

Run: `python3 -m pytest tests/test_project_paths.py -q`

Expected: PASS.

### Task 2: Select The First Eligible External Destination

**Files:**
- Modify: `tests/test_utm_clone_macos.py`
- Modify: `scripts/utm_clone_macos.py`

- [ ] **Step 1: Write failing destination-selection tests**

Add focused tests for primary selection, primary-capacity fallback, exact
300 GB acceptance, invalid/non-external candidate fallback, and all candidates
blocked before `reserve_vm_name` or destination creation.

```python
def test_select_clone_images_dir_falls_back_to_second_candidate(monkeypatch, tmp_path):
    source = tmp_path / "template.utm"
    primary = tmp_path / "primary"
    fallback = tmp_path / "fallback"
    for path in (source, primary, fallback):
        path.mkdir()
    monkeypatch.setattr(utm_clone_macos, "package_allocated_bytes", lambda _: 50)
    monkeypatch.setattr(utm_clone_macos, "is_external_writable_volume", lambda _: True)
    monkeypatch.setattr(
        utm_clone_macos.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(
            free=utm_clone_macos.MINIMUM_FREE_BYTES + (49 if path == primary else 50)
        ),
    )
    assert utm_clone_macos.select_clone_images_dir(
        source, (primary, fallback)
    ) == fallback
```

- [ ] **Step 2: Run selection tests and verify RED**

Run: `python3 -m pytest tests/test_utm_clone_macos.py -q`

Expected: FAIL because the selector and 300 GB constant do not exist.

- [ ] **Step 3: Implement external-volume and capacity selection**

Replace the 5 GiB reserve with `MINIMUM_FREE_BYTES = 300 * 1000**3`. Parse
`diskutil info -plist` and accept only a writable volume whose `Internal` field
is false and whose mount point contains the candidate directory. Add a selector
with this decision:

```python
def select_clone_images_dir(source: Path, candidates: tuple[Path, ...]) -> Path:
    clone_bytes = package_allocated_bytes(source)
    for candidate in candidates:
        if not valid_candidate_directory(candidate):
            continue
        if not is_external_writable_volume(candidate):
            continue
        if shutil.disk_usage(candidate).free - clone_bytes >= MINIMUM_FREE_BYTES:
            return candidate
    raise CloneError("no eligible external clone storage")
```

Call the selector before checking template state, reserving a name, or creating
the destination. Use `VM_IMAGES_DIRS` instead of the single imported directory.
Do not include candidate paths in blocked output.

- [ ] **Step 4: Run clone tests and verify GREEN**

Run: `python3 -m pytest tests/test_utm_clone_macos.py -q`

Expected: PASS.

### Task 3: Bind The Selected Directory Through Initialization

**Files:**
- Modify: `tests/test_utm_clone_and_initialize.py`
- Modify: `scripts/utm_clone_and_initialize.py`

- [ ] **Step 1: Write failing handoff tests**

Extend the fresh-clone and active-resume tests so the verified inventory bundle
is under a non-primary directory and assert:

```python
assert calls[-1][1]["env"]["SUBMISSION_VM_IMAGES_DIR"] == str(bundle.parent)
```

Also assert the active resume uses its recorded bundle parent and never runs the
clone subprocess.

- [ ] **Step 2: Run handoff tests and verify RED**

Run: `python3 -m pytest tests/test_utm_clone_and_initialize.py -q`

Expected: FAIL because the child environment retains the preflight primary.

- [ ] **Step 3: Implement exact-directory propagation**

After either fresh clone or active-workflow resume, use the validated inventory
record to derive the exact bundle parent. Inject only that value into the child
copy of the environment:

```python
record = _active_inventory_record(vm_name)
bundle_parent = Path(str(record["bundle_path"])).parent
child_environment = os.environ.copy()
child_environment["VM_NAME"] = vm_name
child_environment["SUBMISSION_VM_IMAGES_DIR"] = str(bundle_parent)
```

Keep the active workflow's VM name, UUID, and bundle path identity checks
unchanged.

- [ ] **Step 4: Run handoff tests and verify GREEN**

Run: `python3 -m pytest tests/test_utm_clone_and_initialize.py -q`

Expected: PASS.

### Task 4: Public Contract, Documentation, And Regression

**Files:**
- Modify: `.env.example`
- Modify: `docs/configuration.md`
- Modify: `skills/utm-vm-clone/SKILL.md`
- Test: `tests/test_utm_vm_clone_skill.py`
- Test: `tests/test_unattended_portable_skill_contract.py`

- [ ] **Step 1: Write failing contract assertions**

Require the example configuration and canonical skill to name
`SUBMISSION_VM_IMAGES_DIRS`, ordered selection, and the 300 decimal GB reserve.

- [ ] **Step 2: Run contract tests and verify RED**

Run: `python3 -m pytest tests/test_utm_vm_clone_skill.py tests/test_unattended_portable_skill_contract.py -q`

Expected: FAIL on the new assertions.

- [ ] **Step 3: Update public configuration and skill contract**

Add a blank `SUBMISSION_VM_IMAGES_DIRS=` entry, document it as an ordered JSON
array of host-local external VM directories, and state in the skill that each
invocation selects the first eligible configured external directory while
retaining at least 300 decimal GB after the clone.

- [ ] **Step 4: Run focused and related regression tests**

Run:

```bash
python3 -m pytest \
  tests/test_project_paths.py \
  tests/test_utm_clone_macos.py \
  tests/test_utm_clone_and_initialize.py \
  tests/test_utm_vm_clone_skill.py \
  tests/test_unattended_portable_skill_contract.py -q
```

Expected: PASS with no warnings or unexpected output.

- [ ] **Step 5: Review the scoped diff without committing**

Run: `git diff --check` and inspect only the files listed in this plan. Preserve
all unrelated dirty worktree changes. Do not commit unless the user separately
authorizes the exact commit scope.
