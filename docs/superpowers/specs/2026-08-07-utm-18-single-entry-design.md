# UTM-18 Complete Single-Entry Design

## Scope

Replace the current split `utm-18` operator procedure with one host entry that
inherits the exact verified `utm-env` target and completes Edge preparation,
Apple Developer session verification or recovery, attempt creation,
`npm run fill:description`, result classification, and successful handoff.
This change does not modify `utm-21` through `utm-25` and does not change the
Feishu submission-start switch.

## Entry and component boundaries

The only documented business entry becomes:

```bash
python3 "/Users/yehailin/Documents/mac提审自动化/scripts/utm_18.py" \
  --run-id "<current-run-id>" \
  --parent-title "<current-host-parent-title>" \
  --page-title "<application-vm-name>" \
  --vm-name "<vm_name>" \
  --vm-ip "<vm-ip>" \
  --vm-user "<vm_name>"
```

The orchestrator owns ordering and state. Existing focused modules remain
internal implementation units:

- `scripts/utm_18_edge.py` verifies the already-running exact VM and performs
  the single allowed Edge restart/CDP preparation;
- `scripts/utm_18_ssh.py` remains the fixed-password SSH transport;
- the already-delivered guest Apple web helpers perform semantic Apple
  Developer account verification or login recovery in the same Edge process;
- a focused attempt module owns host ledger creation, guest log/status
  precommit, foreground npm execution, and read-only result classification.

No component may start, open, restart, stop, or switch the VM. The Edge restart
inside the existing preparation module remains the only browser-process
exception and must not affect host Chrome.

## Continuous data flow

The entry validates the inherited run/VM/IP/user/page tuple once, verifies the
Notion parent, and then runs these stages without an operator pause:

1. Prepare the exact guest Edge/CDP state and require all existing
   `UTM_18_EDGE_PREPARE` markers.
2. Read only the required Apple Account values through `scripts/notion_api.py`
   and pass sensitive values to the guest only in SSH stdin JSON.
3. Read-only verify the exact preinstalled guest helper files and use their
   semantic Accessibility/Selenium path to verify or recover the Apple
   Developer account in the just-prepared Edge PID. No guest helper is uploaded,
   repaired, generated, or overwritten.
4. Create one atomic mode-600 host attempt ledger and matching mode-600 guest
   log/status paths before any npm side effect.
5. In one foreground fixed-password SSH call through `/bin/zsh -lic`, verify
   identity, project directory, Node/npm, and the exact non-secret CDP endpoint,
   then execute `npm run fill:description` with complete output streamed through
   remote `tee` to the precommitted unique log.
6. Classify only that attempt from its exact ledger, full log, status, and
   process state. A unique completion summary with dynamic `N>=1`, no explicit
   business-error signature, and either zero exit or the already-defined stable
   resident-after-summary state is success.
7. Emit the full existing success marker set, then `UTM_18=verified`, and hand
   the unchanged target context directly to the next current mainline skill.

## Recovery and one-shot safety

SSH transport recovery may reconnect only to the same SQLite-bound VM and may
refresh only that VM's IP. It never authorizes a second npm attempt. An SSH 255,
timeout, missing exit status, or process still running is first reconciled by
three read-only checks of the exact attempt. Explicit business signatures take
precedence over a completion summary or resident process.

A new attempt is permitted only when the existing contract has independently
proved the previous attempt ended with zero business side effects. Otherwise
the entry preserves the attempt and uses the existing final fault-card state
machine after its recovery budget is exhausted. Normal success never asks for
confirmation and never pauses between internal stages.

## Persistence and resume

The host ledger records stage markers and the exact attempt paths atomically.
Reinvoking the same entry for the same run resumes verified read-only stages,
reconciles an existing prepared/running/completion-observed attempt, and never
selects a newest VM, newest run, or newest log. A completed and independently
verified attempt is an idempotent fast path.

## Tests

Automated tests must prove:

- the skill and docs expose exactly one complete absolute-path entry;
- ordered stage execution and no pause on normal success;
- no VM-start/switch operation and exactly one Edge preparation call;
- Notion-only account sourcing and SSH-stdin-only secret transfer;
- atomic mode-600 ledger/log/status precommit and collision refusal;
- explicit error precedence, dynamic product-count parsing, zero-exit success,
  resident-after-summary success, SSH-255 reconciliation, and no blind rerun;
- completed-attempt resume and exact-context handoff;
- existing password-SSH, detailed-skill, continuous-handoff, and portability
  tests remain green.
