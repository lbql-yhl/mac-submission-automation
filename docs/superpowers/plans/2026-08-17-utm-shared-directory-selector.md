# UTM Shared Directory Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent UTM step 3 from opening the drive-creation popover when it should open the shared-directory picker.

**Architecture:** Keep the existing AX-driven workflow, but replace the window-wide generic `New…` fallback with exact shared-directory labels and a bounded native-picker wait. Preserve fail-closed uniqueness checks and the existing path/read-only verification.

**Tech Stack:** Python 3.12, PyObjC Accessibility API, pytest

---

### Task 1: Add selector regression coverage

**Files:**
- Modify: `tests/test_utm_1_ax.py:1-60`
- Test: `tests/test_utm_1_ax.py`

- [ ] **Step 1: Replace the incomplete fallback test with failing regression cases**

Add `import pytest`. Update the mocked `live_labeled_nodes()` so `CHOOSE_DIRECTORY_LABELS` returns no control, `ADD_SHARED_LABELS` returns the shared control when present, and generic `("新建…", "New…")` returns a global drive control. Assert that the shared control is returned and that a global-only tree raises `AXTargetError`.

```python
def test_directory_picker_prefers_exact_shared_control_over_global_new(monkeypatch) -> None:
    from scripts import utm_1_ax

    shared_button = object()

    def fake_live_labeled_nodes(_ax, _root, labels, *, exact=True, roles=None):
        normalized = tuple(labels)
        if normalized == utm_1_ax.CHOOSE_DIRECTORY_LABELS:
            return []
        if normalized == utm_1_ax.ADD_SHARED_LABELS:
            return [shared_button]
        if normalized == ("新建…", "New…"):
            return [object()]
        raise AssertionError((normalized, roles, exact))

    monkeypatch.setattr(utm_1_ax, "live_labeled_nodes", fake_live_labeled_nodes)
    assert utm_1_ax.unique_directory_picker_control(object(), object()) is shared_button


def test_directory_picker_rejects_global_new_without_shared_control(monkeypatch) -> None:
    from scripts import utm_1_ax

    def fake_live_labeled_nodes(_ax, _root, labels, *, exact=True, roles=None):
        normalized = tuple(labels)
        if normalized in (utm_1_ax.CHOOSE_DIRECTORY_LABELS, utm_1_ax.ADD_SHARED_LABELS):
            return []
        if normalized == ("新建…", "New…"):
            return [object()]
        raise AssertionError((normalized, roles, exact))

    monkeypatch.setattr(utm_1_ax, "live_labeled_nodes", fake_live_labeled_nodes)
    with pytest.raises(utm_1_ax.AXTargetError, match="shared control count=0"):
        utm_1_ax.unique_directory_picker_control(object(), object())
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python3 -m pytest tests/test_utm_1_ax.py -q
```

Expected: the new tests fail because the production function still queries the generic `新建…/New…` labels instead of `ADD_SHARED_LABELS`.

### Task 2: Implement the fail-closed selector and bounded wait

**Files:**
- Modify: `scripts/utm_1_ax.py:312-337`
- Modify: `scripts/utm_1_ax.py:925-945`
- Test: `tests/test_utm_1_ax.py`

- [ ] **Step 1: Replace the generic fallback with exact shared labels**

Use `ADD_SHARED_LABELS`, accept only `AXButton`, and require exactly one result:

```python
    shared_controls = live_labeled_nodes(
        ax,
        root,
        ADD_SHARED_LABELS,
        exact=True,
        roles={"AXButton"},
    )
    if len(shared_controls) != 1:
        raise AXTargetError(
            f"directory picker shared control count={len(shared_controls)}"
        )
    return shared_controls[0]
```

- [ ] **Step 2: Add a three-read native-picker wait after Add**

After pressing the exact `ADD_ROW_LABELS` button, reacquire the exact VM window up to three times and stop as soon as `native_picker_open(ax, pid)` is true. Only invoke `unique_directory_picker_control()` if all reads report no native picker.

```python
        press_unique_live(ax, window, ADD_ROW_LABELS, exact=True, roles={"AXButton"})
        for _ in range(3):
            window, _ = reacquire_target(ax, pid, vm_name)
            if native_picker_open(ax, pid):
                break
        else:
            press_ax(ax, unique_directory_picker_control(ax, window))
            wait_and_reacquire()
```

- [ ] **Step 3: Run focused tests and verify GREEN**

Run:

```bash
python3 -m pytest tests/test_utm_1_ax.py -q
python3 tests/test_utm_1_ax.py
```

Expected: pytest reports all tests passed and the script prints `UTM_1_AX_LOGIC=verified`.

- [ ] **Step 4: Run nearby regression tests**

Run:

```bash
python3 tests/test_utm_registry_share.py
python3 -m pytest tests/test_utm_post_clone.py -q
```

Expected: `UTM_REGISTRY_SHARE=verified` and all `test_utm_post_clone.py` tests pass.

### Task 3: Resume the failed clone workflow

**Files:**
- No source changes
- Runtime target: active VM `gvby`

- [ ] **Step 1: Re-run only failed step 3**

Run:

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_vm_clone_step_03_hardware.py --vm-name 'gvby'
```

Expected: `步骤3已操作` and `STEP_03_HARDWARE=verified`.

- [ ] **Step 2: Resume the total entry**

Run:

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_clone_and_initialize.py
```

Expected: completed steps are reverified/skipped and the command ends with `执行成功：utm-vm-clone；UTM_CLONE_AND_INITIALIZE=verified`.

