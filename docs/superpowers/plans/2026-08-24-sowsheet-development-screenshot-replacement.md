# SowSheet Development Screenshot Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace SowSheet's existing 6.9-inch iPhone beauty screenshots with the exact Feishu Base “研发截图” set, then stop without submitting for review.

**Architecture:** Extend the existing `utm-image` public host entry with two explicit, opt-in flags: one forces the development attachment source and one authorizes replacement of a non-empty target panel. The host passes a narrowly scoped replacement boolean through protected stdin; the guest verifies the exact app and display, clears only that display, uploads the verified development set, and emits replacement-specific evidence markers.

**Tech Stack:** Python 3, pytest, Node.js ESM, Playwright over the existing Edge CDP session, Feishu OpenAPI, SSH stdin JSON.

---

### Task 1: Lock the replacement contract in host tests

**Files:**
- Modify: `tests/test_utm_image_ssh.py`
- Modify: `scripts/utm_image.py`

- [ ] **Step 1: Add failing tests for explicit replacement authorization**

Add tests asserting that `--force-development --replace-existing` selects `_development_source_result`, places `replaceExisting: true` in the protected guest payload, and requires `SCREENSHOT_REPLACEMENT=verified`; also assert that neither behavior is enabled when the flags are absent.

- [ ] **Step 2: Run the focused host tests and verify failure**

Run: `pytest -q tests/test_utm_image_ssh.py -k 'force_development or replace_existing'`

Expected: FAIL because the parser and payload do not yet expose the two explicit flags.

- [ ] **Step 3: Implement the minimal host flags and evidence validation**

Add two `store_true` parser options, choose `_development_source_result(...)` only when `force_development` is true, set `payload["replaceExisting"]` only from `replace_existing`, and extend marker validation so replacement mode cannot succeed without `SCREENSHOT_REPLACEMENT=verified` and `SCREENSHOT_PREUPLOAD_CLASSIFICATION=nonempty_authorized`.

- [ ] **Step 4: Re-run the focused host tests**

Run: `pytest -q tests/test_utm_image_ssh.py -k 'force_development or replace_existing'`

Expected: PASS.

No commit is created: the repository contract requires separate explicit commit authorization, which this operation does not include.

### Task 2: Implement exact-panel replacement in the guest workflow

**Files:**
- Modify: `skills/utm-image/scripts/utm_19_one.mjs`
- Modify: `tests/test_utm_image_ssh.py`
- Modify: `skills/utm-image/SKILL.md`

- [ ] **Step 1: Add failing contract tests for replacement safety**

Add assertions requiring the guest workflow to:

- reject `replaceExisting` unless the source marker is `development_attachment`;
- classify the stable pre-upload count as empty or non-empty-authorized;
- scope screenshot-removal controls to the unique 6.9-inch panel;
- delete one screenshot at a time and re-read the stable count until zero;
- refuse deletion when the prepared development set is invalid or exceeds capacity;
- emit `SCREENSHOT_REPLACEMENT=verified` only after the new stable count equals the prepared image count;
- avoid any `Submit for Review` locator or action.

- [ ] **Step 2: Run the focused guest contract tests and verify failure**

Run: `pytest -q tests/test_utm_image_ssh.py -k 'replacement or replace_existing'`

Expected: FAIL because the guest currently rejects every non-empty panel.

- [ ] **Step 3: Add the minimal clear-and-upload path**

Before any deletion, fully download, extract, validate, hash, and normalize the development set. After `openMediaManager`, re-read the unique target panel three times. If replacement is authorized and the count is non-zero, locate removal controls only inside that panel, require their count to match the current screenshot count, click one unique control, wait, and re-read the panel count before continuing. Stop on ambiguous controls or non-decreasing count. After zero is stable, reuse the existing upload ledger and upload path, then require the stable final count to equal the new image count.

- [ ] **Step 4: Document the opt-in public entry**

Add `--force-development --replace-existing` to the canonical `utm-image` command only as an explicitly authorized replacement variant, state that it affects only the unique 6.9-inch target panel, and add the required replacement evidence markers. Keep the ordinary entry behavior unchanged.

- [ ] **Step 5: Run guest syntax and focused tests**

Run: `node --check skills/utm-image/scripts/utm_19_one.mjs`

Expected: exit 0.

Run: `pytest -q tests/test_utm_image_source.py tests/test_utm_image_ssh.py`

Expected: PASS.

No commit is created without separate authorization.

### Task 3: Execute and verify the SowSheet replacement

**Files:**
- Read only: host configuration through project helpers
- Runtime evidence only: `runtime/utm-19/<exact-context-id>/`

- [ ] **Step 1: Resolve and bind the exact live context without printing secrets**

Use project Notion helpers to identify the unique SowSheet page under the configured exact parent, then obtain its exact VM name, VM IP, VM user, App Store app ID, and existing Edge/CDP identity. Stop if any binding is missing or non-unique.

- [ ] **Step 2: Run the canonical project bootstrap and replacement entry**

Run the documented `eval "$(python3 scripts/preflight.py --project-only --emit-shell)"`, then invoke `scripts/utm_image.py` for the exact SowSheet page and VM with `--force-development --replace-existing`. Do not print the resolved sensitive values in chat.

Expected non-sensitive evidence includes:

```text
SCREENSHOT_SOURCE_FIELD=development_attachment
SCREENSHOT_PREUPLOAD_CLASSIFICATION=nonempty_authorized
SCREENSHOT_REPLACEMENT=verified
APP_IDENTITY=verified
IPHONE_69_DISPLAY=selected
UTM_19=verified
```

- [ ] **Step 3: Independently verify the final live page**

Reattach to the unchanged Edge/CDP session and re-read the SowSheet Media Manager page. Verify the 6.9-inch stable count equals the development source image count, no dimensions error is visible, and no review-submission action occurred. Leave that page open for the user.

- [ ] **Step 4: Report only the outcome**

Report the final screenshot count, source marker, replacement verification, and `Submit for Review=not_clicked`. Do not expose IDs, paths, credentials, URLs, hashes, or runtime contents.
