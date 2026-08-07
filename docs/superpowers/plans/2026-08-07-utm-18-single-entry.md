# UTM-18 Complete Single-Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the split `utm-18` operator procedure with one resumable host command that performs every current stage and hands off automatically.

**Architecture:** Add a focused attempt module for durable one-shot execution/classification and a thin `utm_18.py` orchestrator that composes the existing Edge and fixed-password SSH modules plus the preinstalled Apple web helper. Keep exact run/VM identity and all non-idempotent state in an atomic mode-600 ledger.

**Tech Stack:** Python 3, subprocess/OpenSSH, zsh login shell, JSON ledgers, pytest.

---

### Task 1: Extract durable attempt execution and classification

**Files:**
- Create: `/Users/yehailin/Documents/mac提审自动化/scripts/utm_18_attempt.py`
- Create: `/Users/yehailin/Documents/mac提审自动化/tests/test_utm_18_attempt.py`

- [ ] **Step 1: Write failing tests for ledger safety and result precedence**

Test pure APIs:

```python
attempt = create_attempt(root, run_id="run-12345678", vm_name="abcd", vm_ip="192.168.64.20")
assert (attempt.ledger_path.stat().st_mode & 0o777) == 0o600
assert classify_attempt(success_log, finished_status, process_running=False).mode == "exited_zero"
assert classify_attempt(success_log, completion_status, process_running=True).mode == "resident_after_summary"
assert classify_attempt(error_and_summary_log, finished_status, process_running=False).state == "blocked_business_error"
```

Also assert collision refusal, unique dynamic `N>=1`, exact log/status binding, SSH 255 returns reconciliation rather than a rerun, and completed ledger resume is idempotent.

- [ ] **Step 2: Run the new tests and verify the module is missing**

Run: `python3 -m pytest -q tests/test_utm_18_attempt.py`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement the minimal focused module**

Define immutable `Attempt` and `AttemptResult` dataclasses, strict target validators, atomic ledger creation/update with fsync and mode 600, fixed guest path generation, precommit/run/inspect remote scripts, and a classifier whose explicit business signatures take precedence over completion markers.

- [ ] **Step 4: Run the new tests and verify they pass**

Run: `python3 -m pytest -q tests/test_utm_18_attempt.py`

Expected: PASS.

### Task 2: Add the one complete orchestrator

**Files:**
- Create: `/Users/yehailin/Documents/mac提审自动化/scripts/utm_18.py`
- Create: `/Users/yehailin/Documents/mac提审自动化/tests/test_utm_18.py`

- [ ] **Step 1: Write failing ordered-flow and no-rerun tests**

Use injected callables to assert this exact order:

```python
["validate", "verify_parent", "prepare_edge", "verify_or_login_apple", "prepare_attempt", "run_or_resume", "classify", "handoff"]
```

Assert one Edge preparation call, no VM start/switch strings, credentials sourced only through Notion, guest secrets sent only in SSH stdin JSON, business errors block, SSH 255 reconciles the same attempt, and normal success emits `UTM_18=verified` without a confirmation prompt.

- [ ] **Step 2: Run the new test and verify the entry is missing**

Run: `python3 -m pytest -q tests/test_utm_18.py`

Expected: FAIL because the complete entry does not exist.

- [ ] **Step 3: Implement the thin orchestrator**

Compose `utm_18_edge.prepare_edge`, the fixed password transport, read-only verification of the exact preinstalled Apple helper, Notion account reads, and `utm_18_attempt` APIs. Persist stage completion before advancing and resume only the same run/VM/attempt. Print existing non-sensitive markers followed by `UTM_18=verified` only after independent classification.

- [ ] **Step 4: Run the orchestrator and existing transport tests**

Run: `python3 -m pytest -q tests/test_utm_18.py tests/test_utm_18_attempt.py tests/test_utm_18_edge.py tests/test_utm_18_ssh.py`

Expected: PASS.

### Task 3: Replace the split operator contract with one command

**Files:**
- Modify: `/Users/yehailin/Documents/mac提审自动化/skills/utm-18/SKILL.md`
- Modify: `/Users/yehailin/Documents/mac提审自动化/docs/utm-18.md`
- Modify: `/Users/yehailin/Documents/mac提审自动化/AGENTS.md`
- Modify: `/Users/yehailin/Documents/mac提审自动化/tests/test_utm_18_skill.py`
- Modify: `/Users/yehailin/Documents/mac提审自动化/tests/test_continuous_handoff_rules.py`
- Modify: `/Users/yehailin/Documents/mac提审自动化/tests/test_unattended_portable_skill_contract.py`

- [ ] **Step 1: Write failing contract assertions requiring exactly one absolute `scripts/utm_18.py` entry and forbidding operator split commands**
- [ ] **Step 2: Run the contract tests and verify failure**

Run: `python3 -m pytest -q tests/test_utm_18_skill.py tests/test_continuous_handoff_rules.py tests/test_unattended_portable_skill_contract.py tests/test_detailed_skill_contract.py`

Expected: FAIL against the current split skill text.

- [ ] **Step 3: Rewrite the executable skill/doc contract around the single command while retaining all recovery, one-shot, dynamic-count, explicit-error, password-SSH, and browser/VM red lines**
- [ ] **Step 4: Run focused and full verification**

Run: `python3 -m pytest -q tests/test_utm_18.py tests/test_utm_18_attempt.py tests/test_utm_18_edge.py tests/test_utm_18_ssh.py tests/test_utm_18_skill.py tests/test_continuous_handoff_rules.py tests/test_unattended_portable_skill_contract.py tests/test_detailed_skill_contract.py`

Run: `python3 -m pytest -q`

Expected: all tests pass.
