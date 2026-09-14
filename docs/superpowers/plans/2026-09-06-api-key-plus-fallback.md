# API Key Plus Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Make the guest integrations automation use the unique add control beside `Active (number)` when `Generate API Key` is absent.

**Architecture:** Preserve the existing API-key creation flow and replace only its initial trigger with a semantic two-path selector. The source is delivered in the current bound UTM guest, so verification uses static source assertions followed by the public `utm-script` entry.

**Tech Stack:** TypeScript, Playwright, SSH-backed UTM guest execution, Python host entry.

---

### Task 1: Verify the failing source shape

**Files:**
- Remote source: `/Users/zwfo/Downloads/Fire_One_en1.3/src/fill-description.ts`

- [ ] **Step 1: Run the regression assertion before editing.**

Run a read-only remote assertion that the source still waits directly on `Generate API Key` and has no `Active (number)` fallback. Expected: the fallback assertion fails, documenting the red state.

### Task 2: Add the semantic fallback

**Files:**
- Remote source: `/Users/zwfo/Downloads/Fire_One_en1.3/src/fill-description.ts`

- [ ] **Step 1: Replace only the API-key trigger block.**

Keep `readExistingIntegrationData(page)` unchanged. After it returns no existing key, click the visible `Generate API Key` button when present. Otherwise require one heading matching `/^Active \\(\\d+\\)$/`, require one button in that heading's parent row, click it, and retain the existing modal form flow.

- [ ] **Step 2: Run static source assertions.**

Verify the source contains the `Active (number)` heading locator, the exact-one heading and button checks, and the existing modal flow. Expected: all assertions pass.

### Task 3: Re-run the public stage

**Files:**
- Host entry: `/Users/yehailin/Documents/mac提审自动化/scripts/utm_18.py`

- [ ] **Step 1: Run the exact public `utm-script` entry with the inherited page, VM, IP, and user.**

Expected success marker: `执行成功：utm-script；UTM_18=verified`. If the same marker is not emitted, stop at `utm-script` and report the non-sensitive result; do not run `utm-image`.
