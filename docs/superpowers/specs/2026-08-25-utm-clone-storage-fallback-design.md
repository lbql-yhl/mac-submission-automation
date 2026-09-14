# UTM Clone Ordered External Storage Design

## Goal

Create each requested UTM clone on the first authorized external storage target
that can still retain at least 300 decimal GB of free space after the clone.
For this host, the configured order is AutoA first and macos2 second.

## Configuration

- Keep `SUBMISSION_VM_IMAGES_DIR` as the backward-compatible single target.
- Add `SUBMISSION_VM_IMAGES_DIRS` as a JSON array of authorized target
  directories in priority order. When present, it replaces the single target
  for clone selection.
- Keep `SUBMISSION_VM_TEMPLATE` as the one exact template. Template location
  and clone destination are independent.
- Define the reserve as 300,000,000,000 bytes to match Finder's decimal GB.
- Host-specific paths remain in the host-local configuration and are never
  committed or printed.

## Selection And Binding

Before every clone, calculate the template's allocated bytes once and inspect
the candidates in configured order. A candidate is eligible only when it is an
existing, writable, non-symlink directory on an external volume and:

```text
current free bytes - template allocated bytes >= 300,000,000,000
```

Select the first eligible candidate. Missing, invalid, internal, read-only, or
undersized candidates are skipped. If no candidate is eligible, stop before
reserving a VM name or creating a destination directory and return one
non-sensitive storage-capacity error.

After cloning, resolve the exact bundle path from inventory and bind its parent
directory to `SUBMISSION_VM_IMAGES_DIR` for every post-clone child process. An
interrupted run resumes from the bundle path stored in the active workflow, so
it cannot switch disks or select a different VM.

## Workflow Scope

The public entry remains `scripts/utm_clone_and_initialize.py`. It still creates
and initializes exactly one VM per invocation. A request for three VMs invokes
that entry three times serially; storage selection and capacity calculation are
fresh for every invocation.

The workflow never migrates, deletes, or replaces existing VMs and never scans
or writes to unconfigured volumes.

## Verification

Automated tests cover:

- primary target eligible, so fallback is not selected;
- primary target would fall below 300 GB, so fallback is selected;
- exact 300 GB remaining is accepted;
- all candidates insufficient, with no destination creation;
- malformed or duplicate candidate configuration is rejected;
- selected storage is propagated to post-clone initialization;
- active-workflow resume reuses the recorded bundle parent;
- legacy single-target configuration still works.

Run the focused clone and handoff tests, then the related portable contract
suite. A live clone is attempted only after host-local candidate paths are
configured and read-only checks establish that the exact template and both
authorized external volumes are available.
