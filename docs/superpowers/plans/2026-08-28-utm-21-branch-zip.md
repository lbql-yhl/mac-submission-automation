# UTM-21 Branch ZIP Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace UTM-21's Codeup clone with a run-bound Feishu branch choice, a verified GitHub ZIP copy at `<shared-dir>/<application>-git` and guest `Downloads/<application>-git`, then replace five optional identifiers in the guest from the exact inherited Notion page.

**Architecture:** `scripts/utm_21_prepare.py` is the only public UTM-21 entry and owns exact context validation, Feishu Base lookup, deterministic branch ZIP retrieval, safe host staging, verified guest delivery, exact Notion identifier reads, and stdin-driven guest replacement. `services/feishu_bot.py` adds a dedicated `code_branch` pending-decision type while preserving its existing callback authorization, idempotent delivery, and timeout machinery. Existing UTM-ENV download primitives and `scripts/notion_api.py` are reused without changing other skills.

**Tech Stack:** Python 3 standard library, Feishu OpenAPI, Git/GitHub REST ZIP, macOS `open`, SSH/SCP, pytest.

**Authorization note:** Do not create commits unless the user separately authorizes the exact commit scope. The repository contract overrides the generic commit checkpoints normally used by this planning skill.

---

## File Map

- Create `scripts/utm_21_prepare.py`: the complete public UTM-21 host workflow.
- Create `tests/test_utm_21_prepare.py`: Feishu row parsing, branch ZIP, manifest, staging, copy, and orchestration tests.
- Create `tests/test_feishu_code_branch.py`: card creation, callback, delivery, duplicate/stale handling, and waiting tests.
- Modify `services/feishu_bot.py`: add the `code_branch` decision model, card, callback route, CLI notification, and waiter result.
- Modify `skills/utm-21/SKILL.md`: publish the new executable contract and remove the old clone/replacement/workspace workflow.
- Modify `skills/utm-21/agents/openai.yaml`: describe branch ZIP preparation instead of Codeup cloning.
- Modify `tests/test_utm_21_skill.py`: assert the new skill surface and removed responsibilities.
- Modify `tests/test_automatic_skill_actions.py`, `tests/test_segmented_skill_command_contract.py`, and `tests/test_late_skill_regressions.py`: point UTM-21's stable entry to `scripts/utm_21_prepare.py`.
- Leave `scripts/utm_21_clone.py`, UTM-ENV, and all other skill bodies unchanged.

### Task 1: Add The Run-Bound Feishu Branch Decision

**Files:**
- Create: `tests/test_feishu_code_branch.py`
- Modify: `services/feishu_bot.py`

- [ ] **Step 1: Write failing card-state and callback tests**

Cover one exact run with `chat_id`, `project_chat_id`, local host, and no pending decision. Assert that:

```python
run = create_or_update_code_branch_selection("run-1")
pending = run["pending_decision"]
assert pending["kind"] == "code_branch"
assert pending["status"] == "waiting"
assert pending["allowed_branches"] == ["main", "dev", "release"]

card = build_code_branch_card(run)
assert [button["text"]["content"] for button in card["body"]["elements"][1:]] == [
    "main", "dev", "release"
]
```

Dispatch `submission_code_branch_decision` with a matching `decision_id` and operator, then assert the persisted answer, disabled resolved card, and `wait_decision(SimpleNamespace(run_id="run-1", decision_kind="code_branch", timeout_seconds=1, poll_seconds=0), config)` output. Also assert that an unsupported branch, empty operator, foreign host/chat, stale generation, and duplicate click are inert or idempotent as appropriate.

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
pytest -q tests/test_feishu_code_branch.py
```

Expected: collection or import failures for the missing `create_or_update_code_branch_selection`, `build_code_branch_card`, and branch callback behavior.

- [ ] **Step 3: Implement the minimal decision model**

Add `CODE_BRANCHES = ("main", "dev", "release")` and these exact interfaces:

- `create_or_update_code_branch_selection(run_id: str) -> dict[str, Any]`
- `build_code_branch_card(run: dict[str, Any]) -> dict[str, Any]`
- `handle_code_branch_card_action(payload: dict[str, Any], value: dict[str, Any], operator_id: str, submission_host_machine: str, daily_report_chat_id: str, allowed_chat_id: str = "") -> dict[str, Any]`
- `notify_code_branch(args: argparse.Namespace, config: Config) -> int`

The creator returns an existing identical waiting decision or atomically stores a new decision with a generated `decision_id`, `message_uuid`, and the three allowed branches. The builder returns a JSON 2.0 card with three buttons while waiting and one disabled result button after resolution. The handler applies the existing host/chat/operator/generation gates before recording one allowed branch. The notifier requires an existing run and exact original chat, creates or resumes the decision, confirms delivery, and returns zero only after a message ID is persisted.

Extend `record_decision_by_run_id` with branch-only validation when `pending.kind == "code_branch"`; add statuses and non-sensitive notes for all three branches. Route `submission_code_branch_decision` before the fault action, render `code_branch` from `decision_card_for_run`, record its delivery through the existing idempotent notification path, allow `--decision-kind code_branch`, return the selected branch from `wait_decision`, and add `notify-code-branch` to the CLI.

- [ ] **Step 4: Run card tests and existing callback regressions**

Run:

```bash
pytest -q tests/test_feishu_code_branch.py tests/test_feishu_card_callback_transport.py tests/test_feishu_fault_card.py tests/test_feishu_confirmation.py
```

Expected: all tests pass; existing fault, confirmation, and review decisions retain their current behavior.

### Task 2: Implement Exact Feishu URL And Branch ZIP Preparation

**Files:**
- Create: `tests/test_utm_21_prepare.py`
- Create: `scripts/utm_21_prepare.py`

- [ ] **Step 1: Write failing source and ZIP tests**

Define fake Feishu and GitHub command adapters. Assert exact row selection, exactly one non-empty `代码 URL`, canonical GitHub root validation, safe application naming, exact branch ref parsing, and commit-pinned download:

```python
assert select_code_url([record("Demo", "https://github.com/acme/repo")], "Demo") == (
    "https://github.com/acme/repo"
)
assert parse_branch_ref("a" * 40 + "\trefs/heads/dev\n", "dev") == "a" * 40
assert final_directory_name("Demo") == "Demo-git"
```

Reject zero/two application matches, missing/empty/multiple links, credential-bearing or non-GitHub URLs, branch output with zero/two refs, unsafe application names, path-traversal ZIPs, symlinks, duplicate case-folded paths, multiple archive roots, and over-limit archives.

- [ ] **Step 2: Run source tests and verify RED**

Run:

```bash
pytest -q tests/test_utm_21_prepare.py -k 'code_url or branch or zip or directory_name'
```

Expected: import failure because `scripts/utm_21_prepare.py` does not exist.

- [ ] **Step 3: Implement source selection and immutable ZIP download**

Create `UTM21Error`, `select_code_url`, `final_directory_name`, `parse_branch_ref`, and `GitHubBranchZipClient`. Reuse `parse_base_url`, `select_exact_record`, `parse_github_repo_url`, `GitHubRepositoryClient._download_repository_zip`, and `_extract_github_repository_zip` from `scripts.utm_env_download_assets` so the new path inherits the existing credential channel and ZIP defenses without changing UTM-ENV.

Resolve only:

```python
["/usr/bin/git", "ls-remote", "--exit-code", "--refs", "--", repo_url,
 f"refs/heads/{branch}"]
```

Download using the returned 40-character SHA. Do not put credentials or authenticated URLs in argv or logs.

- [ ] **Step 4: Run source and existing UTM-ENV download tests**

Run:

```bash
pytest -q tests/test_utm_21_prepare.py -k 'code_url or branch or zip or directory_name' tests/test_utm_env_download_assets.py
```

Expected: all selected tests pass and UTM-ENV behavior is unchanged.

### Task 3: Add Atomic Host And Guest Delivery

**Files:**
- Modify: `tests/test_utm_21_prepare.py`
- Modify: `scripts/utm_21_prepare.py`

- [ ] **Step 1: Write failing manifest and copy tests**

Assert that `directory_manifest` includes dotfiles, relative POSIX paths, sizes, executable flags, and SHA-256 content hashes in sorted order. Exercise a fake guest transport and assert:

```python
result = deliver_guest_code(
    source=shared / "Demo-git",
    app_name="Demo",
    vm_user="abcd",
    vm_ip="192.0.2.10",
    run_id="run-1",
    transport=fake,
)
assert result["guest_path"] == "/Users/abcd/Downloads/Demo-git"
assert result["manifest_match"] == "exact"
```

Cover absent targets, identical same-run resume, a conflicting host target, a conflicting guest target, a changed guest manifest, wrong guest identity, unsafe symlinks/special files, and cleanup limited to the current run's temporary paths.

- [ ] **Step 2: Run copy tests and verify RED**

Run:

```bash
pytest -q tests/test_utm_21_prepare.py -k 'manifest or host_stage or guest or resume or conflict'
```

Expected: failures for missing manifest/staging/delivery functions.

- [ ] **Step 3: Implement host staging and guest transport**

Add these exact interfaces:

- `directory_manifest(root: Path) -> list[dict[str, object]]`
- `install_host_code(archive: bytes, shared_root: Path, app_name: str, run_id: str, commit_sha: str, ledger: RunLedger) -> tuple[Path, list[dict[str, object]]]`
- `SSHGuestTransport(vm_user: str, vm_ip: str)` with `verify_identity()`, `copy_tree(source: Path, temporary_name: str)`, `manifest(remote_path: str)`, `promote(temporary_path: str, final_path: str)`, and `remove_owned_temporary(remote_path: str)` methods
- `deliver_guest_code(source: Path, app_name: str, vm_user: str, vm_ip: str, run_id: str, commit_sha: str, ledger: RunLedger, transport: GuestTransport) -> dict[str, str]`

Define `RunLedger` as a mode-600 JSON record under `runtime/utm-21` keyed by a SHA-256 digest of the run ID. It stores only the run digest, application, VM identity, selected branch, commit SHA, final directory names, and content manifest; it never stores a credential, URL, run ID, chat ID, or raw API response. Define `GuestTransport` as a protocol matching the five methods listed above so tests can use a stateful fake without invoking SSH.

Extract to a run-hash temporary sibling, verify the manifest, and atomically rename to `<shared-dir>/<application>-git`. Copy the whole directory recursively to a run-hash temporary name below the verified guest `Downloads`, compute a fresh guest manifest, compare it to the host manifest, and atomically rename it to `<application>-git`. A final target is resumable only when the protected same-run ledger binds the selected commit and exact manifest; otherwise refuse without mutation.

- [ ] **Step 4: Run copy and SSH regression tests**

Run:

```bash
pytest -q tests/test_utm_21_prepare.py tests/test_password_ssh_migration.py tests/test_guest_password_input_contract.py
```

Expected: all tests pass; the configured password broker remains the only guest credential channel.

### Task 4: Wire The Public Workflow And Missing-URL Fault Gate

**Files:**
- Modify: `tests/test_utm_21_prepare.py`
- Modify: `scripts/utm_21_prepare.py`

- [ ] **Step 1: Write failing orchestration tests**

Test `verify_run_context` against exact run/chat/host/app/VM/IP fields and a succeeded `utm-p8` attempt. Assert no newest/first fallback. Test the workflow with fakes in this order:

```text
verify context -> read URL -> open repository -> notify branch card -> wait branch
-> resolve commit -> open selected branch -> download/extract -> host manifest
-> guest copy -> fresh guest manifest -> success marker
```

For a missing `代码 URL`, return the same missing-field result on three reads at delays `0/5/10`, invoke `skill-failure` and `notify-fault` with non-sensitive evidence, and assert that browser, card, download, and copy are never called.

- [ ] **Step 2: Run orchestration tests and verify RED**

Run:

```bash
pytest -q tests/test_utm_21_prepare.py -k 'run_context or workflow or missing_code_url or browser'
```

Expected: failures for missing orchestration and CLI functions.

- [ ] **Step 3: Implement the public entry**

Parse only `--run-id`, `--chat-id`, `--app-name`, `--vm-name`, `--vm-ip`, optional `--base-url`, and bounded timeout settings. Load Feishu credentials through `load_credentials(PROJECT_ROOT / ".env")`, use `SHARED_DIR`, call `/usr/bin/open` without shell execution, and call the Feishu bot CLI through an injected argv runner for `notify-code-branch`, `wait-decision`, and the missing-field fault gate.

On success print exactly:

```text
开始执行：utm-21
执行成功：utm-21；UTM_21=verified
```

On failure print only a non-sensitive UTM-21 reason category. Never print the URL, branch commit, paths, raw API records, subprocess output, run/chat IDs, or credentials.

- [ ] **Step 4: Run the complete new workflow tests**

Run:

```bash
pytest -q tests/test_utm_21_prepare.py tests/test_feishu_code_branch.py
```

Expected: all tests pass.

### Task 5: Switch The Authoritative Skill Contract

**Files:**
- Modify: `skills/utm-21/SKILL.md`
- Modify: `skills/utm-21/agents/openai.yaml`
- Modify: `tests/test_utm_21_skill.py`
- Modify: `tests/test_automatic_skill_actions.py`
- Modify: `tests/test_segmented_skill_command_contract.py`
- Modify: `tests/test_late_skill_regressions.py`

- [ ] **Step 1: Replace UTM-21 contract expectations first**

Assert the only public entry is `$PROJECT_ROOT/scripts/utm_21_prepare.py`; require `UTM_P8=verified`, Feishu OpenAPI, `代码 URL`, `main`, `dev`, `release`, `<app-name>-git`, `Downloads`, host/guest manifest verification, and `UTM_21=verified`. Assert the skill does not contain the old entry or the removed behaviors:

```python
for removed in (
    "utm_21_clone.py", "Codeup", "CODEUP_", "placeholder", "origin/main",
    "git diff --check", "Runner.xcworkspace",
):
    assert removed not in skill
```

Update the three shared entry tables to `scripts/utm_21_prepare.py`.

- [ ] **Step 2: Run contract tests and verify RED**

Run:

```bash
pytest -q tests/test_utm_21_skill.py tests/test_automatic_skill_actions.py tests/test_segmented_skill_command_contract.py tests/test_late_skill_regressions.py
```

Expected: failures because the current skill still publishes `utm_21_clone.py`.

- [ ] **Step 3: Rewrite the skill and metadata minimally**

Publish the approved workflow, one public entry, three exact branch choices, run-bound callback, selected-commit ZIP, `<app-name>-git` host/guest targets, bounded fault gate, and final marker. Explicitly forbid visual/browser-agent operation and all removed legacy responsibilities. Update `openai.yaml` to describe Feishu branch ZIP preparation.

- [ ] **Step 4: Validate the skill and contract tests**

Run:

```bash
python3 /Users/yehailin/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/utm-21
pytest -q tests/test_utm_21_skill.py tests/test_automatic_skill_actions.py tests/test_segmented_skill_command_contract.py tests/test_late_skill_regressions.py
```

Expected: validator success and all contract tests pass.

### Task 6: Add Exact Guest Identifier Replacement

**Files:**
- Modify: `scripts/utm_21_prepare.py`
- Modify: `tests/test_utm_21_prepare.py`
- Modify: `skills/utm-21/SKILL.md`
- Modify: `tests/test_utm_21_skill.py`
- Modify: this design and plan

- [x] **Step 1: Add failing identifier and recovery tests**

Cover exact stable reads of `账号信息 / APP_ID：`, `应用信息 / 正式包名: `, and `应用信息 / 应用名: ` from the derived `<application>-<vm-user>` page. Cover all five optional source strings, zero-hit success, one-pass replacement, hidden files, executable modes, stdin-only identifier transport, partial recovery, completed resume, conflicts, and plaintext absence from the ledger.

- [x] **Step 2: Implement the host replacement proof**

Validate the App ID as numeric and the Bundle ID with the existing project Bundle ID pattern. Read both snapshots around three parent-page checks. Compute the transformed manifest and per-placeholder counts entirely in memory without mutating the host shared directory.

- [x] **Step 3: Implement atomic idempotent guest replacement**

Pass identifiers plus raw/expected manifests through SSH stdin JSON. In the guest, reject symlinks, hard links, special files, unexpected paths, and unexpected content hashes. Skip files already at the expected hash, transform only files still at the raw hash, verify transformed bytes before atomic replacement, and preserve file modes.

- [x] **Step 4: Wire recovery and final verification**

Allow a same-run replacement resume only when each guest file matches either its raw or expected manifest entry. Persist identifier hashes, counts, and manifests without identifier plaintext. Require the final guest manifest to equal the host-computed expected manifest before success.

- [x] **Step 5: Update the Chinese skill contract**

Document the five exact mappings, exact Notion fields, stdin-only transport, zero-hit behavior, unchanged host copy, atomic writes, same-run recovery, and final transformed-manifest gate. Keep Git state and `Runner.xcworkspace` verification removed.

### Task 7: Final Verification

**Files:**
- Verify only; do not modify unrelated dirty files.

- [ ] **Step 1: Run focused regression suites**

```bash
pytest -q \
  tests/test_utm_21_prepare.py \
  tests/test_feishu_code_branch.py \
  tests/test_feishu_card_callback_transport.py \
  tests/test_feishu_fault_card.py \
  tests/test_feishu_confirmation.py \
  tests/test_utm_env_download_assets.py \
  tests/test_password_ssh_migration.py \
  tests/test_utm_21_skill.py \
  tests/test_automatic_skill_actions.py \
  tests/test_segmented_skill_command_contract.py \
  tests/test_late_skill_regressions.py
```

Expected: all tests pass.

- [ ] **Step 2: Run hygiene checks**

```bash
git diff --check
python3 scripts/public_release_audit.py
```

Expected: no whitespace errors and the public-release audit succeeds without reading or printing secrets.

- [ ] **Step 3: Review only the task diff**

```bash
git diff -- \
  scripts/utm_21_prepare.py services/feishu_bot.py \
  skills/utm-21/SKILL.md skills/utm-21/agents/openai.yaml \
  tests/test_utm_21_prepare.py tests/test_feishu_code_branch.py \
  tests/test_utm_21_skill.py tests/test_automatic_skill_actions.py \
  tests/test_segmented_skill_command_contract.py tests/test_late_skill_regressions.py \
  docs/superpowers/specs/2026-08-28-utm-21-branch-zip-design.md \
  docs/superpowers/plans/2026-08-28-utm-21-branch-zip.md
```

Expected: only the approved UTM-21 workflow, branch decision support, focused tests, and design/plan documents are present. Do not commit without exact user authorization.
