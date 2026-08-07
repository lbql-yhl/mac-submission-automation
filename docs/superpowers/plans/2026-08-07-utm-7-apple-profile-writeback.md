# UTM-7 Apple Profile Writeback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the single `utm-7` entry read Apple Account name and birthday through guest Accessibility, write both to Notion, and preserve the exact `生日（格式年/月/日）：` contract without month/day ambiguity.

**Architecture:** Add one focused guest AX reader returning named date components over SSH stdin/stdout JSON. Keep orchestration and rollback-protected Notion mutation in `utm_7_login.py`; update `utm-notion` and `utm-business` to use the one exact long birthday label and strict date-order conversions.

**Tech Stack:** Python 3, PyObjC Accessibility, password SSH, Notion REST wrapper, pytest/unittest.

---

### Task 1: Lock the birthday label and date-order contract

**Files:**
- Modify: `/Users/yehailin/Documents/mac提审自动化/tests/test_utm_notion.py`
- Modify: `/Users/yehailin/Documents/mac提审自动化/tests/test_utm_business_host.py`
- Modify: `/Users/yehailin/Documents/mac提审自动化/tests/test_utm_business_guest.py`
- Modify: `/Users/yehailin/Documents/mac提审自动化/scripts/utm_business.py`
- Modify: `/Users/yehailin/Documents/mac提审自动化/scripts/utm_business_workflow.py`

- [ ] **Step 1: Write failing tests for the exact label and strict direction**

```python
assert ACCOUNT_LABELS.count("生日（格式年/月/日）：") == 1
assert "生日：" not in ACCOUNT_LABELS
assert utm_business._normalize_birthday("1999/3/9") == "1999-03-09"
with pytest.raises(utm_business.UTMBusinessError, match="NOTION_BIRTHDAY_INVALID"):
    utm_business._normalize_birthday("3/9/1999")
assert normalize_birthday("1999-03-09") == "03-09-1999"
```

- [ ] **Step 2: Run the focused tests and verify the new assertions fail for the current short-label/dual-order behavior**

Run: `python3 -m pytest -q tests/test_utm_notion.py tests/test_utm_business_host.py tests/test_utm_business_guest.py`

Expected: FAIL on the current `生日：` read and acceptance of month/day/year Notion input.

- [ ] **Step 3: Implement the minimal strict contract**

Change the Business read to:

```python
_required_field(api, page_title, "账号信息", "生日（格式年/月/日）：")
```

Make host normalization accept only `YYYY/M/D`, `YYYY-M-D`, or `YYYY.M.D`; validate with `date(year, month, day)` and emit ISO. Keep the guest input contract ISO-only and format it to `MM-DD-YYYY` for the agreement UI.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run: `python3 -m pytest -q tests/test_utm_notion.py tests/test_utm_business_host.py tests/test_utm_business_guest.py`

Expected: PASS.

### Task 2: Add the semantic System Settings profile reader

**Files:**
- Create: `/Users/yehailin/Documents/mac提审自动化/scripts/apple_account_profile.py`
- Create: `/Users/yehailin/Documents/mac提审自动化/tests/test_apple_account_profile.py`

- [ ] **Step 1: Write failing parser and semantic-selection tests**

```python
assert parse_apple_birthday("3/9/1999") == (1999, 3, 9)
assert parse_apple_birthday("03/09/1999") == (1999, 3, 9)
with pytest.raises(ProfileReadError, match="APPLE_BIRTHDAY_INVALID"):
    parse_apple_birthday("1999/3/9")
assert normalize_account_name("  Ada  Lovelace  ") == "Ada  Lovelace"
```

Add fake AX-tree tests proving exactly one expected email, name, `Personal Information`, and `Birthday` are required and duplicates block.

- [ ] **Step 2: Run the new test and verify import/function failures**

Run: `python3 -m pytest -q tests/test_apple_account_profile.py`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement the focused guest helper**

Expose pure functions:

```python
def parse_apple_birthday(value: str) -> tuple[int, int, int]: ...
def normalize_account_name(value: str) -> str: ...
def read_profile(expected_email: str) -> dict[str, object]: ...
```

Use the existing `find_system_settings_general` AX traversal/activation helpers, require unique semantic targets, sleep at least three seconds after activating `Personal Information`, and emit one JSON object with `name`, `birth_year`, `birth_month`, and `birth_day`.

- [ ] **Step 4: Run the new tests and verify they pass**

Run: `python3 -m pytest -q tests/test_apple_account_profile.py`

Expected: PASS.

### Task 3: Wire rollback-protected Notion writeback into `utm-7`

**Files:**
- Modify: `/Users/yehailin/Documents/mac提审自动化/scripts/utm_7_login.py`
- Modify: `/Users/yehailin/Documents/mac提审自动化/tests/test_utm_7_login.py`

- [ ] **Step 1: Write failing tests for transport, conflict rules, rollback, and marker order**

Add tests for:

```python
profile = {"name": "Ada Lovelace", "birth_year": 1999, "birth_month": 3, "birth_day": 9}
assert format_notion_birthday(profile) == "1999/3/9"
```

Assert the helper is synchronized, expected email travels only in SSH stdin JSON, empty fields are filled, identical fields are idempotent, different non-empty fields block, second-write/readback failure restores both original fields, and `UTM_7=verified` is printed only after both Notion markers.

- [ ] **Step 2: Run the focused test and verify it fails for missing profile writeback**

Run: `python3 -m pytest -q tests/test_utm_7_login.py`

Expected: FAIL on the new helper and transaction assertions.

- [ ] **Step 3: Implement the minimal host orchestration**

Add `apple_account_profile.py` to the synchronized helper set, invoke it with the existing password-SSH transport, validate its JSON schema, format `YYYY/M/D`, and implement a two-field before/write/readback/rollback transaction using `NotionAPI.read_field` and `NotionAPI.set_field` without `replace_existing=True` for a different non-empty value.

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `python3 -m pytest -q tests/test_utm_7_login.py`

Expected: PASS.

### Task 4: Update executable skill contracts and run regression checks

**Files:**
- Modify: `/Users/yehailin/Documents/mac提审自动化/skills/utm-7/SKILL.md`
- Modify: `/Users/yehailin/Documents/mac提审自动化/docs/utm-7.md`
- Modify: `/Users/yehailin/Documents/mac提审自动化/skills/utm-business/SKILL.md`
- Modify: `/Users/yehailin/Documents/mac提审自动化/docs/utm-business.md`
- Modify: `/Users/yehailin/Documents/mac提审自动化/AGENTS.md`
- Modify: `/Users/yehailin/Documents/mac提审自动化/tests/test_automatic_skill_actions.py`
- Modify: `/Users/yehailin/Documents/mac提审自动化/tests/test_notion_read_skills.py`

- [ ] **Step 1: Write failing contract assertions for AX-only writeback and the exact long birthday label**
- [ ] **Step 2: Run the focused contract tests and verify failure**

Run: `python3 -m pytest -q tests/test_automatic_skill_actions.py tests/test_notion_read_skills.py tests/test_detailed_skill_contract.py`

Expected: FAIL until documentation is synchronized.

- [ ] **Step 3: Update skill/docs with the exact entry, markers, conversion direction, conflict/rollback boundary, and seamless `utm-8` handoff**
- [ ] **Step 4: Run focused and full verification**

Run: `python3 -m pytest -q tests/test_apple_account_profile.py tests/test_utm_7_login.py tests/test_utm_notion.py tests/test_utm_business_host.py tests/test_utm_business_guest.py tests/test_automatic_skill_actions.py tests/test_notion_read_skills.py tests/test_detailed_skill_contract.py`

Run: `python3 -m pytest -q`

Expected: all tests pass.
