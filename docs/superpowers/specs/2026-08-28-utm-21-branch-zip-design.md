# UTM-21 Branch ZIP Preparation Design

## Goal

Replace the current UTM-21 Codeup clone workflow with one deterministic host entry that:

- requires the exact inherited run and `UTM_P8=verified` context;
- reads the exact application's `代码 URL` field through Feishu OpenAPI;
- opens the credential-free repository URL in the host browser without visual automation;
- sends a Feishu card with exactly `main`, `dev`, and `release` choices;
- waits for one authorized, run-bound card callback;
- downloads a ZIP pinned to the selected branch's exact commit;
- safely extracts it as `<application>-git` in the configured host shared directory;
- copies the complete extracted directory to the same guest's `Downloads/<application>-git` and independently verifies the raw copy;
- reads the numeric App ID and production Bundle ID twice from the exact inherited Notion page;
- replaces five optional fixed strings across every regular guest file and verifies the final guest tree against a host-computed expected manifest without modifying the host copy.

UTM-21 does not inspect Git state or verify `Runner.xcworkspace`. No other skill is changed.

## Selected Approach

Add one public Python entry, `scripts/utm_21_prepare.py`. It orchestrates the existing Feishu OpenAPI transport and run registry, the safe GitHub ZIP techniques already used by UTM-ENV, the host browser open command, and the existing password-protected SSH/SCP transport.

The Feishu bot gains one dedicated `code_branch` pending-decision kind. The new decision has three explicit values, `main`, `dev`, and `release`; it is not represented as a generic confirmation because the selected value is workflow data rather than a yes/no authorization. After the raw guest copy is verified, the same Python entry uses `scripts/notion_api.py` and one stdin-driven guest Python command for deterministic identifier replacement.

Alternatives rejected:

1. A chain of independent shell commands would split resume state across processes and make it harder to prove that the callback, ZIP, host directory, and guest directory belong to the same run.
2. Browser-driven clicks on the GitHub branch menu and `Download ZIP` depend on page layout and login state. The browser is opened for visibility, but the selected commit and ZIP are resolved and downloaded through deterministic commands/APIs.
3. Moving the existing UTM-ENV code download is out of scope. This change affects UTM-21 only.

## Public Entry And Inputs

The skill exposes only:

```bash
python3 "$PROJECT_ROOT/scripts/utm_21_prepare.py" \
  --run-id '<run-id>' --chat-id '<chat-id>' \
  --app-name '<app-name>' --vm-name '<vm-name>' --vm-ip '<vm-ip>'
```

Before the entry, the skill uses the shared project preflight and lifecycle handshake. The entry revalidates the exact run, original chat, local host, application, four-letter VM name/user, VM IP, and the completed UTM-P8 marker. It never substitutes the newest, first, or closest run, row, VM, or browser session.

Credentials, authenticated URLs, raw Feishu records, run IDs, chat IDs, and local paths are not printed. GitHub and guest credentials remain in the repository's protected in-memory/environment channels and never enter public logs.

## Data Flow

1. Read the configured Feishu Base location and credentials through the existing local configuration snapshot.
2. Query records through Feishu OpenAPI and require exactly one row whose application name exactly matches the inherited application.
3. Read exactly one non-empty `代码 URL` link and validate it as a canonical credential-free HTTPS GitHub repository root.
4. Ask the host OS to open that canonical URL in the default browser. No DOM, screenshot, coordinate, clipboard, or agent interaction is used.
5. Create or resume one `code_branch` pending decision bound to the exact run, original chat, application, and host. Deliver one idempotent Feishu card with three buttons: `main`, `dev`, and `release`.
6. Accept only a nonempty authorized operator callback with the matching run ID, decision ID, host, chat route, waiting state, and one of the three allowed branch values. Duplicate callbacks return the already-resolved card; stale or mismatched callbacks are inert.
7. Resolve `refs/heads/<selected-branch>` to exactly one commit SHA. Open the selected branch URL in the host browser, then download the GitHub ZIP for that immutable commit rather than for a moving branch name.
8. Validate archive size, member count, one repository root, normalized relative paths, duplicate targets, unsupported file types, symlinks, and total expanded size. Extract into a run-scoped temporary directory without trusting the archive's root name.
9. Build the final host directory as `<shared-dir>/<application>-git`. The application name must be a safe single path component and preserve its exact case.
10. Build a content manifest for every regular file, including dotfiles. Copy the directory into a run-scoped temporary path below `/Users/<vm-user>/Downloads`, verify guest identity and destination ownership, compare the fresh guest manifest with the unchanged host manifest, then atomically place it at `Downloads/<application>-git`.
11. Derive the only valid Notion page title as `<application>-<vm-user>`. Through `scripts/notion_api.py`, verify the exact host parent before, between, and after two reads of `账号信息 / APP_ID：`, `应用信息 / 正式包名: `, and `应用信息 / 应用名: `. Require stable values, the exact application, a numeric App ID, and a production-style Bundle ID.
12. On the host, scan every regular source file in memory and compute the expected guest manifest and hit counts for these mappings without changing the shared copy: `5372311233` to App ID; `jltest.test.test`, `uildbet.brovaxtere`, `xycoins.2027.test`, and `org.toolbox.fastcleaner` to the production Bundle ID. Zero hits are valid.
13. Send the two identifiers and raw/expected manifests to one guest Python process through SSH stdin JSON. The process validates every path and file state, skips files already matching their expected hash, applies a one-pass byte replacement only to files still matching their raw hash, writes changed files atomically, and preserves mode bits. Identifiers never enter argv or public output.
14. Rebuild the guest manifest and require exact equality with the host-computed expected manifest. Persist only identifier hashes, hit counts, and manifests for replacement recovery; never persist identifier plaintext.
15. Delete the temporary ZIP and temporary directories after verified success. Emit only `执行成功：utm-21；UTM_21=verified` and pass the same run, VM, selected branch, commit identity, guest code directory, and live session forward.

## Existing Targets And Resume

- If the final host and guest targets are absent, create them through temporary paths and atomic rename.
- If an interrupted same-run attempt left only a recognized run-scoped temporary path, verify its ledger and resume the exact checkpoint.
- If a final target already exists, accept it only when a persisted same-run ledger and a fresh content manifest prove it is identical to the selected commit.
- If replacement was interrupted, accept the directory only when every file exactly matches either its raw manifest entry or its transformed manifest entry for the same run and identifier hashes. Resume only raw files; transformed files are never processed twice.
- A different, unowned, ambiguous, or nonidentical target is never deleted, replaced, merged, reset, or renamed. After three read-only checks, the skill stops at the recovery gate.
- Project files are never flattened directly into `Downloads`; the final guest root is always `Downloads/<application>-git`.

## Cards And Waiting

The unresolved branch card shows only the application, owning host, and the three branch buttons. It does not expose repository URLs, run/chat IDs, paths, credentials, or raw records.

Once answered, the card becomes a disabled resolved card showing the chosen branch. The existing one-hour decision timeout applies. Timeout stops the run and sends the existing timeout result card. A waiting branch decision prevents another decision card from overwriting it.

The branch card is operational input, not a fault card. Fault cards retain the shared contract's existing four visible facts and three actions.

## Failure And Recovery

Each reversible checkpoint uses the shared `0/5/10` second, three-round budget without resetting it by restarting the entry.

- Missing or empty `代码 URL`: repeat the exact Feishu row/field read three times without mutation, record `skill-failure`, issue the final fault card through the existing recovery gate, and do not continue to branch selection or download.
- Invalid or ambiguous application row, URL, branch, archive, host target, guest target, callback, run ownership, or VM identity: fail closed with a non-sensitive step label.
- Invalid, unstable, or mismatched Notion identifiers, unsafe guest entries, or a guest file matching neither its raw nor transformed hash: stop without overwriting the conflicting content.
- Card delivery failure: retry idempotently using the same decision and message UUID.
- Interrupted download or copy: reconcile only the same run-scoped temporary artifact; never treat an unbound artifact as resumable.
- Branch selection timeout: stop through the existing decision-timeout path.

No later UTM-21 step runs while a fault decision is pending. The shared fault workflow controls manual continuation, exact-skill retry, stop, and timeout.

## Skill Contract Changes

`skills/utm-21/SKILL.md` will:

- name `scripts/utm_21_prepare.py` as its only public host entry;
- require `UTM_P8=verified` and immutable run/application/VM/chat context;
- describe Feishu `代码 URL`, branch-card, selected-commit ZIP, `<application>-git`, exact Notion reads, the five optional fixed replacements, and raw/final host/guest manifest evidence;
- remove the Codeup clone helper, Codeup credentials, generic legacy replacement workflow, Git status, origin/main, and workspace verification requirements;
- retain bounded recovery and the `UTM_21=verified` success marker.

The existing `scripts/utm_21_clone.py` remains untouched but is no longer referenced by UTM-21. Other skill bodies, including UTM-ENV and UTM-22, remain untouched as requested.

## Testing

Tests will cover observable behavior rather than exact prose alone:

- skill entry, required markers, removed legacy responsibilities, and unchanged handoff marker;
- exact application-row and `代码 URL` parsing with missing/empty/ambiguous failures;
- branch card rendering, callback authorization, allowed branches, duplicate/stale clicks, delivery idempotency, and timeout;
- commit-pinned branch resolution and rejection of missing or ambiguous branch refs;
- ZIP traversal, symlink, duplicate-path, file-count, compressed-size, and expanded-size defenses;
- exact `<application>-git` naming and case preservation;
- hidden-file-inclusive host/guest manifests, atomic placement, identical same-run resume, and refusal to overwrite conflicts;
- exact stable Notion field reads, identifier validation, all five mappings, zero-hit success, one-pass behavior, atomic permission-preserving guest writes, partial replacement recovery, and identifier absence from argv/ledger;
- command construction that keeps credentials and URLs out of argv and public output;
- absence of browser DOM, screenshots, coordinates, clipboard, or agent-control dependencies.

Targeted pytest suites and the skill validator must pass before the change is reported complete.

## Non-Goals

- Change UTM-ENV or any other skill.
- Clone through Codeup or preserve Git metadata.
- Validate Git status, branches, remotes, diffs, or repository ownership after ZIP extraction.
- Generate, repair, or verify `Runner.xcworkspace`.
- Drive GitHub visually or click browser controls.
- Flatten project contents into the guest `Downloads` root.
