# Public Release Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a portable, fully tested, public-safe project snapshot with complete project and Feishu bot setup documentation and no tracked host-specific credentials, identifiers, paths, runtime data, or private history.

**Architecture:** Treat the root `.env` as the only host-local configuration source, use fail-closed accessors for required values, and enforce the public boundary with an executable tracked-tree audit. Keep workflow details in the 16 `SKILL.md` files, consolidate operator documentation, and publish a new orphan snapshot while preserving old history only in private archives.

**Tech Stack:** Python 3.12, Node.js, zsh, pytest, Ruff, Codex skills, Git, GitHub CLI

---

### Task 1: Add a public-release audit gate

**Files:**
- Create: `scripts/public_release_audit.py`
- Create: `tests/test_public_release_hygiene.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write failing tests for the tracked-tree boundary**

Create tests that run the audit against `git ls-files` and assert a nonzero result while the current tree still contains personal home paths, embedded password constants, embedded Feishu resource destinations, historical plan files, and missing ignore rules. The audit API is:

```python
from pathlib import Path

def audit_repository(root: Path) -> list[tuple[str, str]]:
    """Return sorted `(rule, relative_path)` findings without secret values."""
```

Sensitive example keys must be present with empty values. The tests must verify `.env`, `config/workflow.env`, `runtime/`, signing files, and VM images are ignored while `.env.example` remains tracked.

- [ ] **Step 2: Verify the tests fail for the expected findings**

Run:

```bash
python3 -m pytest tests/test_public_release_hygiene.py -q
```

Expected: failures name rule IDs and paths, never matched values.

- [ ] **Step 3: Implement the minimal audit**

The script must:

- enumerate tracked regular files with `git ls-files -z`;
- skip binary content after a NUL-byte check;
- flag personal absolute home paths, nonempty assignments to password/token/secret/resource-ID constants, fixed report destinations, and `docs/superpowers/`;
- validate the example-file values by key without printing values;
- print `PUBLIC_RELEASE_AUDIT=ok` on success or `RULE path` findings on failure;
- never read the host `.env`.

Extend `.gitignore` with `*.env`, allow `!.env.example` and `!*.env.example`, and explicitly ignore `config/workflow.env`.

- [ ] **Step 4: Verify the gate reports only current known findings**

Run the focused test and `python3 scripts/public_release_audit.py`. Keep the failing output as the RED baseline for later tasks.

### Task 2: Externalize host secrets and secure runtime metadata

**Files:**
- Create: `services/host_config.py`
- Modify: `.env.example`
- Delete: `config/workflow.env.example`
- Modify: `scripts/ssh_password.py`
- Modify: `scripts/mac_password_prompt.py`
- Modify: `scripts/utm_vm_clone_accessibility.py`
- Modify: `scripts/utm_7_login.py`
- Modify: `scripts/utm_9.py`
- Modify: `scripts/utm_18_ssh.py`
- Modify: `scripts/utm_post_clone_guest.py`
- Modify: `services/feishu_bot.py`
- Modify: `services/feishu_supervisor.py`
- Modify: `scripts/vm_inventory_scan.py`
- Modify: `scripts/utm_notion.py`
- Test: `tests/test_host_config.py`
- Test: `tests/test_ssh_password.py`
- Test: `tests/test_mac_password_prompt.py`
- Test: `tests/test_utm_a_accessibility.py`
- Test: `tests/test_utm_notion.py`
- Test: `tests/test_feishu_fault_card.py`

- [ ] **Step 1: Write failing configuration and permission tests**

Test this interface before implementation:

```python
import os
from collections.abc import Mapping
from pathlib import Path

class ConfigurationError(RuntimeError):
    pass

def optional_setting(name: str, *, environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    return str(source.get(name, "")).strip()

def required_setting(name: str, *, environ: Mapping[str, str] | None = None) -> str:
    value = optional_setting(name, environ=environ)
    if not value:
        raise ConfigurationError(f"missing required host setting: {name}")
    return value

def secure_runtime_tree(path: Path) -> None:
    root = Path(path)
    if root.is_symlink():
        raise ConfigurationError(f"unsafe runtime path: {root}")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    for current, directories, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in directories:
            child = current_path / name
            if child.is_symlink():
                raise ConfigurationError(f"unsafe runtime path: {child}")
            child.chmod(0o700)
        for name in files:
            child = current_path / name
            if child.is_symlink():
                raise ConfigurationError(f"unsafe runtime path: {child}")
            child.chmod(0o600)
```

`required_setting` must return stripped values, reject blank values with `missing required host setting: NAME`, and never include a value in an exception. `secure_runtime_tree` must set directories to `0700`, regular files to `0600`, and refuse symlinks.

Add behavior tests proving the SSH askpass helper reads `SUBMISSION_GUEST_PASSWORD` from its environment without embedding it in source, command arguments, helper names, or helper contents. Add tests for dynamic four-digit Quartz key-code mapping and for missing configuration failure.

- [ ] **Step 2: Run focused tests and observe missing behavior**

Run:

```bash
python3 -m pytest tests/test_host_config.py tests/test_ssh_password.py tests/test_mac_password_prompt.py tests/test_utm_a_accessibility.py -q
```

Expected: fail because the accessors and dynamic password behavior do not exist.

- [ ] **Step 3: Implement fail-closed host configuration**

Load `.env` through the existing `services.project_paths` import, then expose the accessors above. Replace `FIXED_PASSWORD`, `MAC_PASSWORD_VALUE`, `_ASKPASS_BODY` containing a password, and static key codes with a `guest_password()` accessor and a digit-to-key-code mapping. Rename helpers and tests so no credential appears in a filename or symbol implying a repository default.

Add these empty template keys:

```dotenv
SUBMISSION_GUEST_PASSWORD=
FEISHU_DAILY_REPORT_CHAT_ID=
```

Remove unused Feishu example keys that have no consumer and add currently consumed supervisor keys. Keep every password, token, key, resource identifier, chat ID, host identity, and host path empty.

- [ ] **Step 4: Remove embedded Feishu/Notion destinations**

Replace the report chat constant with `FEISHU_DAILY_REPORT_CHAT_ID`. Replace Feishu Base defaults with empty host settings: either `UTM_NOTION_FEISHU_WIKI_URL` or all of `UTM_NOTION_FEISHU_APP_TOKEN`, `UTM_NOTION_FEISHU_TABLE_ID`, and `UTM_NOTION_FEISHU_VIEW_ID` must be supplied. Missing or mixed settings must fail before a network request.

Fix the current `utm_notion` suite-order leak by isolating all four variables in tests and by avoiding persistent import-time mutation outside the intended project `.env` load.

- [ ] **Step 5: Secure runtime writes**

Call `os.umask(0o077)` at bot/supervisor entrypoints and apply `secure_runtime_tree` to existing runtime metadata before service startup. Preserve active runtime data; change permissions rather than deleting it. Add tests that create permissive temporary files and verify the corrected modes.

- [ ] **Step 6: Verify focused behavior**

Run the touched configuration, SSH, Feishu, Notion, and runtime tests. Expected: all pass with no network access and no secret values in output.

### Task 3: Make the 16 skills portable and self-consistent

**Files:**
- Modify: `skills/_shared/AUTOMATION_CONTRACT.md`
- Modify: `skills/*/SKILL.md`
- Create or regenerate: `skills/*/agents/openai.yaml`
- Modify: `scripts/preflight.py`
- Modify: `tests/test_unattended_portable_skill_contract.py`
- Modify: `tests/test_detailed_skill_contract.py`
- Modify: `tests/test_skill_contract_references.py`
- Modify: other skill-contract tests that assert the old personal path

- [ ] **Step 1: Change contract tests to the portable command model**

Require every `SKILL.md` to:

- contain only `name` and `description` frontmatter fields;
- reference `../_shared/AUTOMATION_CONTRACT.md`;
- initialize with `eval "$(python3 scripts/preflight.py --project-only --emit-shell)"` from the repository root;
- invoke its existing host entrypoint below `$PROJECT_ROOT/scripts/` and the active Python interpreter;
- contain no personal home path or dedicated local virtualenv path;
- state inputs, success marker, retry rule, and handoff.

Run the contract tests and confirm they fail against the current skills.

- [ ] **Step 2: Update the shared contract and skills**

Keep one canonical command and one canonical workflow description per skill. Replace personal absolute paths with `$PROJECT_ROOT` commands, resolve the output-safety contradiction in favor of non-sensitive summaries, and add the shared-contract link and missing execution/verification/handoff sections to short skills. Do not duplicate script internals.

- [ ] **Step 3: Improve skill discovery metadata**

Rewrite descriptions as concrete `Use when...` triggers without workflow summaries. Generate `agents/openai.yaml` for all 16 skills with deterministic `display_name`, `short_description`, and a `default_prompt` that names `$skill-name`. Validate metadata against each skill.

- [ ] **Step 4: Run skill validation and forward tests**

Run official `quick_validate.py` for all 16 skills, the skill contract tests, `scripts/install_project_skills.sh --check`, and representative fresh-agent scenarios for each workflow segment. Expected: all validation succeeds and agents select the correct single host entrypoint without using a private path.

### Task 4: Consolidate public project and Feishu documentation

**Files:**
- Create: `AGENTS.md`
- Rewrite: `README.md`
- Create: `docs/configuration.md`
- Rewrite: `docs/project-workflow.md`
- Rewrite: `docs/utm-feishu-bot.md`
- Merge/Delete: `docs/feishu-host-routing.md`
- Merge/Delete: duplicated `docs/utm-*.md` skill runbooks except the Feishu bot document
- Rewrite: `docs/host-vm-dependency-check.md`
- Rewrite: `shared-files/README.md`
- Rewrite: `shared-files/apple-store-bm/README.md`
- Delete before public snapshot: `docs/superpowers/`
- Test: `tests/test_project_docs_are_concise.py`
- Test: `tests/test_public_release_hygiene.py`

- [ ] **Step 1: Write failing documentation contract tests**

Require a README quick start with prerequisites, copy/chmod/check-ignore steps for `.env`, project-only and host preflight, skill installation, bot start, health check, test commands, and public-security policy. Require the Feishu guide to list the source and purpose of every consumed `FEISHU_*` key, required Open Platform permissions/events, WS and HTTP callback modes, and safe troubleshooting without values.

- [ ] **Step 2: Build the public documentation hierarchy**

Use this authority model:

- `README.md`: overview and quick start;
- `docs/configuration.md`: all host settings grouped as required, feature-specific, and path settings;
- `docs/project-workflow.md`: four workflow segments and links to the 16 skills;
- `docs/utm-feishu-bot.md`: complete Feishu Open Platform and bot operations guide;
- `SKILL.md`: executable workflow truth;
- `shared-files/`: artifact-specific verification and provenance only.

Merge useful host-routing content into the Feishu guide and remove duplicate per-skill runbooks. Add the physical `AGENTS.md` supplied for the project, including graph-first discovery and safe fallback.

- [ ] **Step 3: Remove private planning residue**

Delete `docs/superpowers/` from the release tree after its local design/plan commits exist. Remove concrete host names, VM names, IPs, page names, personal paths, and old repository migration instructions from public documentation.

- [ ] **Step 4: Verify documentation**

Run link checks, docs contract tests, skill reference tests, and the public-release audit. Expected: zero broken local links, zero duplicate runbooks, zero personal paths, and all required setup information present.

### Task 5: Resolve every known test and static-analysis failure

**Files:**
- Modify: implementation and tests identified by the failing suite, limited to the root causes
- Test: complete `tests/` suite

- [ ] **Step 1: Re-run the complete suite after Tasks 1-4**

Run:

```bash
python3 -m pytest -q
node --test tests/test_utm_22_distribute.mjs
```

Record each remaining failure by subsystem. Do not weaken a valid public-safety, portability, or workflow invariant.

- [ ] **Step 2: Fix failures with RED-GREEN-REFACTOR**

For each root cause, run its smallest failing test, confirm the expected failure, implement the minimal production correction, and re-run the subsystem. Particular known groups are `utm-18`, `utm-image`, `utm-post-clone`, skill handoff contracts, and the `utm_notion` environment-isolation failure.

- [ ] **Step 3: Make Ruff output clean**

Run Ruff on all tracked Python. Add narrowly placed `# noqa: E402` only where the established project-root import pattern requires it; remove f-string prefixes from strings without substitutions. Re-run until zero findings.

- [ ] **Step 4: Run all validation gates**

Run complete pytest, Node tests, `node --check` on every tracked JavaScript module, Ruff, `git diff --check`, project preflight, skill installation check, skill validation, and public-release audit. Expected: every command exits zero.

### Task 6: Review, create a clean public snapshot, and update GitHub

**Files:**
- Review: entire staged release tree
- External: GitHub repositories under `lbql-yhl`

- [ ] **Step 1: Perform independent spec and quality reviews**

Dispatch a spec-compliance review, then a code-quality/security review. Fix and re-review every important issue. Re-run all validation after the final fix.

- [ ] **Step 2: Commit the completed working tree**

Stage only the audited project files. Verify `git diff --cached --check`, `git status --ignored`, and the staged-tree public audit. Commit with a public-release hardening message.

- [ ] **Step 3: Protect old history**

Verify exact repository identities with `gh repo view`. Rename the existing private `lbql-yhl/yhl-devops-mac` to a private archive name. Change the legacy `lbql-yhl/mac-submission-automation` repository to private because its public history contains the retired fixed credential and personal resource identifiers.

- [ ] **Step 4: Publish only a clean orphan snapshot**

Create a temporary orphan branch from the sanitized index, commit one snapshot with no parent, create a new public `lbql-yhl/yhl-devops-mac`, and push only `refs/heads/main`. Do not push old branches or tags. Keep the development branch and old Git history local/private.

- [ ] **Step 5: Verify the public repository from a fresh clone**

Check visibility, default branch, remote refs, commit parent count, public audit, examples, links, preflight, tests, and secret scan in a fresh temporary clone. Expected: one public branch, no tags, one root commit, all gates green, and no private values or history.

- [ ] **Step 6: Report rotation requirement**

Report that the retired guest/macOS password appeared in the formerly public legacy history and must be rotated on affected VMs. Do not print it. Report repository URLs, commit IDs, test counts, and archive visibility.
