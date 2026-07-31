# UTM Notion Design

## Goal

Replace `notion-utm` and `notion-utm-1` with one API-only `utm-notion` skill. When a Feishu user mentions the bot with `开始<应用名>应用提审`, the workflow must resolve the unique application row in `运维提审表`, lock one VM to the application, fill the copied Notion template, and hand off to `utm-5`.

This change does not modify, invoke, or hand off to `utm-vm-clone`. VM creation remains an independent user-run inventory-preparation workflow.

## Authoritative Systems

- Feishu Base app token: `LNFdbb2cxaauuvsVGuGcebMhnxm`
- Feishu table: `tblcENvSwMO6lhSH`
- Feishu view: `运维提审表` (`vewfxNVEGj`)
- Application identity: exact, case-sensitive `应用名` match; exactly one record is required.
- VM inventory: `${PROJECT_ROOT}/runtime/vm-inventory.sqlite3`
- Notion parent: `.env` `NOTION_ROOT_PAGE_ID`, verified before every operation against `SUBMISSION_HOST_MACHINE`
- Notion source: the unique direct child page named `模板`

Feishu, SQLite, and Notion operations use project Python scripts and HTTP APIs only. Browser automation, Chrome, Feishu desktop, Notion desktop/web UI, Computer Use, coordinates, and clipboard transfer are prohibited.

## Trigger and Run Creation

The Feishu bot recognizes a mention containing `开始<应用名>应用提审`, allowing surrounding whitespace but requiring one non-empty application name. It silently ignores the daily-report-only group and any disallowed chat.

The bot creates one run containing the application name, original chat, source message ID, and trigger text. It does not invent a VM name and does not start a background runner. It creates the existing Codex App foreground-session handoff whose first and only initial skill is `utm-notion`.

Duplicate delivery of the same Feishu message ID is idempotent. A second active run for the same application is rejected unless it is the same stable run being resumed.

## Single Script Entry

`utm-notion` exposes one production command, resolved to an absolute path at runtime:

```text
python3 <PROJECT_ROOT>/scripts/utm_notion.py --run-id <exact-run-id>
```

The command performs all Feishu reads, VM allocation, Feishu VM-field write, Notion template creation, field filling, readback, run updates, and success-marker output. Sensitive values never appear in argv, stdout, stderr, logs, cards, or the clipboard.

## Feishu Record Contract

The script resolves one live `StringBed`-style row from `运维提审表` and re-reads it immediately before each external write. Required current columns are:

- `应用名`
- `虚拟机`
- `账号信息`
- `代理信息`
- `代码 URL`
- `ABA Routing Number`
- `Account Number`
- `顶级域名`
- `正式包名`
- `正式域名(app/h5/im/log)`
- `应用类型`
- `应用描述`
- `关键词`

`账号信息` supplies the email from one verified `mailto:` URL. `代理信息` accepts either a four-line labeled block (`代理ip`, `代理端口`, `代理用户名`, `代理用户密码`) or the current compact `host:port:username:password` representation. The parser validates canonical IPv4, port range, and non-empty credentials. `代码 URL` maps to the Notion `代码链接` field.

Fields absent from Feishu remain unchanged in the copied Notion template. The script never guesses, derives, or clears an unsupported value.

## VM Resolution and Permanent Binding

### Existing Feishu VM

When the row's `虚拟机` is non-empty, it must be one four-letter lowercase name. The matching SQLite row must exist, be `status='complete'`, have `directory_present=1`, and identify a real registered bundle.

- If `application_name` already equals the target application, continue idempotently and enforce `available=0`.
- If `application_name` is empty, bind the VM to the target application in one SQLite write transaction and set `available=0`.
- If it is bound to another application, missing, incomplete, or ambiguous, stop before changing Feishu or Notion.

### Empty Feishu VM

When `虚拟机` is empty, one `BEGIN IMMEDIATE` SQLite transaction selects one row satisfying:

```text
available=1
application_name IS NULL
status='complete'
directory_present=1
```

Selection is deterministic by `vm_created_at`, then `vm_name`. The same transaction sets `application_name=<应用名>`, `available=0`, and `last_used_at=<UTC timestamp>`. Once committed, that VM is permanently reserved for the application and cannot be assigned to another application.

The script then updates the exact Feishu record with a payload containing only:

```json
{"fields":{"虚拟机":"<vm_name>"}}
```

It independently re-reads the record, requires the same record ID and VM value, and proves all other fields are unchanged.

SQLite binding is never rolled back merely because the Feishu request fails or its result is unknown. The run stores a stable allocation attempt and VM name before the Feishu write. Recovery always reconciles and writes the same VM; it never allocates another machine.

## Notion Page Creation

The script verifies the configured parent title, resolves exactly one direct `模板` child, and creates exactly one child page named:

```text
<应用名>-<虚拟机>
```

The template already contains the required headings, code blocks, labels, formatting, and defaults. After the Notion template finishes materializing, the script locates the unique `账号信息` and `应用信息` headings and their immediately following code blocks.

An existing page is reusable only when its exact title, application, VM binding, and current values are compatible with the same run. The script does not create a suffix page to bypass a conflict.

## Template Field Filling

The script parses the copied template by exact label and preserves label text, order, blank lines, code-block type, formatting, and unrelated content. It updates only mapped fields.

### 账号信息

- `邮箱` <- `账号信息`
- `代理ip`, `代理端口`, `代理用户名`, `代理用户密码` <- parsed `代理信息`
- `代码链接` <- `代码 URL`
- `ABA Routing Number` <- same-named Feishu column
- `Account Number` <- same-named Feishu column
- `电话` retains the template default `+1`
- All later-stage fields remain unchanged when Feishu provides no authority for them.

### 应用信息

- `应用名` <- `应用名`
- `团队` <- fixed `灵光`
- `顶级域名` <- `顶级域名`
- `正式包名` <- `正式包名`
- `正式域名` <- `正式域名(app/h5/im/log)`
- `应用类型` <- normalized category
- `应用描述` <- `应用描述`
- `关键词` <- `关键词`
- `隐私协议`, `用户协议`, and `支持链接` remain unchanged unless future authoritative columns are explicitly added to the contract.

Application category normalization accepts, in order:

1. an already-valid App Store Connect enum;
2. the fixed Chinese-to-enum map;
3. a valid enum suffix in a value such as `生活方式-LIFESTYLE`.

The allowed enums are exactly the current fixed category set. Unknown values stop before Notion mutation. Multiline application descriptions and keywords are preserved, so verification uses label uniqueness/order plus complete byte count and SHA-256 rather than a fixed total line count.

## Write Safety and Recovery

Before each Notion mutation, the script re-verifies the parent, page identity, VM binding, and live Feishu record. It saves mode-600 before files for both code blocks. After field-level rendering, it writes only the two exact blocks and independently reads each back for byte-for-byte equality.

If the second block fails after the first succeeds, the script restores both blocks from the same-attempt before files and independently verifies `NOTION_ROLLBACK=verified`. Sensitive temporary files are removed after success, rollback, stop, or timeout.

Transient API reads use three bounded retries. External data absence, permission failure, VM ownership conflict, no available VM, multiple rows, and unresolved write results follow the shared three-round recovery contract before the final fault card. Fault cards go only to the original non-daily-report chat.

## Success and Handoff

Success requires all of the following current evidence:

```text
FEISHU_VIEW=运维提审表
FEISHU_RECORD_MATCH_COUNT=1
VM_BINDING=verified
FEISHU_VM_FIELD=verified
NOTION_PARENT=verified
NOTION_PAGE_TITLE=verified
ACCOUNT_INFO_READBACK=exact
APPLICATION_INFO_READBACK=exact
SENSITIVE_TEMP_FILES=removed
UTM_NOTION=verified
```

Only then may the same run, record ID, application, VM name, original chat, Notion page title, and allocation attempt hand off directly to `utm-5`. `utm-vm-clone` is never invoked or offered as recovery.

## Repository Changes

- Add `skills/utm-notion/SKILL.md` with complete executable business steps.
- Add `scripts/utm_notion.py` as the single production entry.
- Extend the project Feishu API/runtime code for exact `运维提审表` reads and VM-only writes.
- Extend `scripts/vm_inventory.py` with atomic claim/bind/reconcile operations.
- Extend `scripts/notion_api.py` with label-preserving field-fill support and exact template-copy recovery.
- Re-enable the application-name start trigger and update the Codex App prompt to start at `utm-notion`.
- Remove the old `skills/notion-utm` and `skills/notion-utm-1` execution contracts after their replacement tests pass.
- Replace their documentation with `docs/utm-notion.md` and update README, AGENTS, installer, workflow order, and all affected tests.
- Do not change `utm-vm-clone` behavior or add it to the submission flow.

## Test Strategy

- Trigger parsing, duplicate-message idempotency, forbidden-chat silence, and foreground handoff tests.
- Feishu exact-row, schema, URL-cell, proxy-format, and VM-only update tests.
- SQLite concurrent claim tests proving one VM cannot be assigned twice.
- Existing-VM idempotency and ownership-conflict tests.
- Feishu write failure/unknown-result recovery tests proving the same VM is retained.
- Notion template-copy, existing-label fill, multiline value, two-block rollback, and exact readback tests.
- Category tests for every Chinese mapping, direct enums, valid suffixes, and unknown rejection.
- Sensitive-output and temporary-file cleanup tests.
- Updated detailed-skill, continuous-handoff, workflow-order, and portability contract tests.
- One explicit `StringBed` integration test may be run on request; it must use a uniquely named recoverable test page and move it to trash after readback.
