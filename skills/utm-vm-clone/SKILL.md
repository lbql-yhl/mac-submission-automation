---
name: utm-vm-clone
description: Use when a submission run needs a new UTM macOS guest cloned and initialized from the configured template.
---

# utm-vm-clone

Read and obey [`../_shared/AUTOMATION_CONTRACT.md`](../_shared/AUTOMATION_CONTRACT.md). From the repository root run `eval "$(python3 scripts/preflight.py --project-only --emit-shell)"` before the entry command.

## Contract

- Segment: 1, virtual-machine preparation; this is the segment entry and tail.
- Input: the securely loaded host configuration, exact configured template, VM inventory, and active-clone identity. Do not choose a VM by recency.
- `SUBMISSION_VM_IMAGES_DIRS` is the ordered JSON list of authorized external VM directories. When absent, the legacy single `SUBMISSION_VM_IMAGES_DIR` remains the only candidate.
- Before every clone, select the first eligible configured external directory whose free space after the template copy remains at least 300 decimal GB. Skip an ineligible candidate and try the next configured directory; never scan or write to an unconfigured or internal volume.
- Only public host entry:

  ```bash
  python3 "$PROJECT_ROOT/scripts/utm_clone_and_initialize.py"
  ```

- The entry owns clone, account, hardware, desktop, settings, delivery, dependency, Accessibility, App Management, and finalization checks. Do not invoke its step modules or guest helpers directly.
- Bind the selected bundle parent to the same active clone and every initialization child process. A resumed run must reuse that exact directory and VM identity.
- Accept success only after the entry freshly verifies the unique stopped/running VM identity, shared delivery, all configured dependencies, guest identity, and final inventory binding.
- Retry only the failed internal checkpoint on the same active clone, at most three rounds using 0/5/10 seconds. Never delete or replace a conflicting VM automatically.

## Result and handoff

The canonical success summary is `执行成功：utm-vm-clone；UTM_CLONE_AND_INITIALIZE=verified;VM_NAME=<four lowercase letters>`. This ends segment 1. If the active request covers the full mainline, hand the exact VM/run context to `utm-notion`; otherwise stop at the segment boundary.
