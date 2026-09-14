# Lixsms Rich-Text Account Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the `utm-notion` public entry parse the exact Lixsms account cell used by `LumenDraft` without weakening existing account validation.

**Architecture:** Add one provider-specific parser before the existing flattened-text branches. It recognizes only an HTTPS `lixsms.com` boundary, preserves the phone and credential fragments, and returns the existing account dictionary shape; all non-matching inputs continue through the current parser unchanged.

**Tech Stack:** Python 3 standard library, pytest, Feishu OpenAPI through the existing project client.

---

### Task 1: Lock The Provider Contract With Tests

**Files:**
- Modify: `tests/test_utm_notion.py`

- [ ] **Step 1: Add the valid rich-text regression**

```python
def test_build_registration_fields_accepts_lixsms_rich_text_account() -> None:
    fields = stringbed_fields()
    fields["账号信息"] = [
        {"text": "2025550123"},
        {"text": "查看短信", "link": "https://lixsms.com/sms?id=synthetic"},
        {"text": "stringbed@example.", "link": "https://ignored.example/a"},
        {"text": "comAbc1D2ef", "link": "https://ignored.example/b"},
    ]
    account, _ = build_registration_fields(fields)
    assert account["邮箱："] == "stringbed@example.com"
    assert account["初始密码："] == "Abc1D2ef"
    assert account["电话："] == "+12025550123"
    assert account["电话短信接收平台："] == "https://lixsms.com/sms?id=synthetic"
```

- [ ] **Step 2: Add equivalent four-line string coverage**

Use the same synthetic values separated by CRLF so the test matches the current Feishu OpenAPI response shape.

- [ ] **Step 3: Add strict rejection coverage**

Add one test with a nine-digit prefix and one with two supported email suffix boundaries. Both must raise `RuntimeError` mentioning `Lixsms`.

- [ ] **Step 4: Run tests to verify RED**

Run: `pytest -q tests/test_utm_notion.py -k lixsms`

Expected: the valid fixtures fail in the existing generic parser because their fragment boundaries are flattened, proving the regression is exercised.

### Task 2: Add The Minimal Provider-Specific Parser

**Files:**
- Modify: `scripts/utm_notion.py`
- Test: `tests/test_utm_notion.py`

- [ ] **Step 1: Add `html` parsing support and a private Lixsms helper**

The helper must:

```python
def _parse_lixsms_account_info(cell: object) -> dict[str, str] | None:
    # Recognize the exact rich-list or four-line shape.
    # Require a contiguous 10-digit phone and HTTPS lixsms.com URL.
    # Join only credential fragments after the provider boundary.
    # Split at exactly one supported email suffix.
    # Validate the email and a non-empty mixed letter/digit password.
```

- [ ] **Step 2: Call the helper first from `parse_account_info`**

Return its result when it matches. When the provider boundary is present but malformed, raise instead of falling through. Leave every existing parser branch unchanged.

- [ ] **Step 3: Run focused tests to verify GREEN**

Run: `pytest -q tests/test_utm_notion.py -k lixsms`

Expected: all Lixsms tests pass.

- [ ] **Step 4: Run the full related module**

Run: `pytest -q tests/test_utm_notion.py`

Expected: all tests pass with no regression in existing formats.

### Task 3: Retry And Verify The Exact Binding

**Files:**
- No repository file changes.

- [ ] **Step 1: Bootstrap the project and rerun the public entry**

```bash
eval "$(python3 scripts/preflight.py --project-only --emit-shell)"
python3 "$PROJECT_ROOT/scripts/utm_notion.py" --app-name 'LumenDraft' --vm-name 'zwfo'
```

- [ ] **Step 2: Require canonical fresh evidence**

Expected: `执行成功：utm-notion；status=verified`.

- [ ] **Step 3: Stop at the requested scope boundary**

Do not hand off to `utm-clash-ip`; this request covers only the explicit application-to-VM binding.
