# Feishu Project Group Observability Design

## Goal

Make the configured Feishu project group the single operational surface for submission lifecycle visibility:

- send a start card before the first requested submission skill runs;
- send one terminal card with the skills actually run and the frozen elapsed time;
- send the final fault card to the project group after the existing bounded-recovery gate is exhausted;
- let an `@bot` message deterministically list active submissions and currently claimable VMs;
- preserve the existing three fault actions: stop, manually handled and continue, or retry the failed skill while revalidating already successful checkpoints.
- format and send the daily report to the same exact project group, only from fields explicitly supplied and confirmed by the user.

This work does not re-enable Feishu submission intake. It adds lifecycle and query behavior for exact runs that already exist or are handed to a foreground executor.

## Selected Approach

Use explicit lifecycle commands backed by the existing run registry. The foreground executor calls these commands at the boundaries defined by the shared automation contract. Card delivery uses the configured `FEISHU_ALLOWED_CHAT_ID`, which is the exact project-group route; a run must bind that route and the local host before any notification is allowed.

Alternatives considered:

1. Parse Codex CLI output for skill markers. This misses the active Codex App foreground handoff and cannot reliably distinguish retries or scoped runs.
2. Wrap all 16 script entry points. Several late skills are partly or entirely GUI-driven and have no complete wrapper, so this cannot record the true lifecycle.
3. Infer activity from VM bindings or stale run status. Bindings persist after a run and the current foreground handoff has no terminal hook, so the result would not truthfully represent active work.

Explicit lifecycle events cover full, segment, and single-skill scopes without guessing.

## Routing And Authorization

- `FEISHU_ALLOWED_CHAT_ID` is the project-group route for commands and lifecycle cards.
- Start, end, and fault delivery fails closed when the route is missing, does not match the run's bound project group, matches a distinct legacy deny-only route, or the run belongs to another host.
- Routing never resolves a group by display name and never selects the newest or first chat.
- Card callbacks retain the existing nonempty Feishu operator, local-host, waiting-state, and decision-generation checks. Repeated or stale clicks remain inert.
- Cards and replies contain no run/chat IDs, paths, credentials, raw diagnostics, or other sensitive identifiers.

## Run State

Each project-group run stores:

- immutable `project_chat_id` and owning host;
- `lifecycle.started_at`, `finished_at`, `outcome`, and frozen `duration_seconds`;
- stable start/end message UUIDs and confirmed message IDs for delivery idempotency;
- ordered skill attempts with skill name, start/end timestamps, status, and optional non-sensitive failure step;
- the current skill and step for active-query display.

The lifecycle start transition is idempotent and must confirm the start-card message ID before the first skill side effect. The finish transition is terminal and idempotent. A retry records another attempt for the same skill; the end card lists skills in first-execution order and does not claim unrecorded skills.

Run-registry writes used by lifecycle events and callbacks share one advisory lock and atomic replacement so concurrent callback and executor updates cannot overwrite each other.

## Cards

### Start

The green start card contains only application, owning host, and start time. Its title is `<application> 开始提审`.

### End

The terminal card contains application, owning host, outcome, ordered skills actually run, `流程故障次数`, and formatted elapsed time. Success, stopped, and failed outcomes use distinct card headers. It has no buttons.

### Fault

The orange unresolved card contains exactly four visible facts:

- 故障技能
- 技能故障步骤
- 应用
- 宿主

Detailed recovery evidence remains in protected run state and is still required before sending, but is not exposed in the group. The three buttons keep their current callback values and behavior. `stop` becomes terminal only after the active executor has actually stopped and sent the end card. `manual_continue` resumes after fresh state verification. `retry_skill` reruns the failed skill and skips only checkpoints that pass their completion checks again.

## Lifecycle Flow

1. Before the first requested skill, the executor calls `run-start` and waits for confirmed card delivery.
2. Before each skill it records `skill-start`.
3. After verified success it records `skill-success` and hands off normally.
4. On failure it records `skill-failure`, completes the existing three-round recovery or read-only verification gate, then calls `notify-fault` and `wait-decision`.
5. Manual continue and retry are nonterminal. Stop or timeout leads to a stopped terminal transition after execution is no longer continuing.
6. At the requested scope tail, or after a terminal failure/stop, the executor calls `run-finish` exactly once.

The generated Codex prompt and shared automation contract describe these commands so the foreground mainline is wired without modifying all 16 skill bodies.

## Group Queries

The bot strips the Feishu mention before deterministic command parsing and handles the query before the generic assistant.

Supported intents:

- `正在提审的应用` or `/提审 应用列表`
- `可用的虚拟机` or `/提审 可用VM`
- `/提审 资源` for both sections

Queries only run in the exact configured project group.

Active applications are exact local-host runs with a lifecycle start and no lifecycle finish. The reply shows application, normalized state/current skill, and elapsed time. It never exposes run IDs, chat IDs, prompt paths, or raw run data.

Available VMs are read from the inventory SQLite database in read-only mode using the allocator's exact claim predicate:

`available=1 AND application_name IS NULL AND status='complete' AND directory_present=1 AND reusable=0`

The result is a sorted snapshot of four-letter VM names. A missing, unsafe, corrupt, or incompatible data source returns a clear query failure rather than an empty list.

## User-Provided Daily Report

The daily report uses the same exact project-group route, `FEISHU_ALLOWED_CHAT_ID`. `FEISHU_DAILY_REPORT_CHAT_ID` is an optional legacy deny-only compatibility key and is never a send target; when it equals the project-group route, configuration normalizes it to empty. The report's exact plain-text shape is:

```text
日期：<系统按 Asia/Shanghai 生成的当天日期>
今天提审准备：
<用户提供的应用>
查审情况：
<用户提供的应用>  <过审|待审|审核中> <用户提供的天数>天
```

`日期：`, `今天提审准备：`, and `查审情况：` are fixed report structure and require no user input. The formatter generates the current date in `Asia/Shanghai` and accepts only explicit user-provided business rows: zero or more preparation applications and zero or more review rows. Every review row requires an application, one of the three allowed states, and a non-negative integer day count. At least one application row must exist across the two sections, so an empty payload cannot be sent. Empty sections stay empty; the system does not invent `无`, an application, a status, or a day count.

Delivery requires all of the following:

- the structured payload was supplied explicitly for this report;
- the exact rendered preview hash is supplied back as approval;
- the caller asserts that the user confirmed that exact preview;
- the exact project-group destination is configured, regardless of any legacy daily-report value;
- OpenAPI returns a message ID and delivery verification succeeds.

The daily-report entry has no dependency on run state, Git, Notion, Feishu Base, VM inventory, or assistant memory. Its only generated business-independent value is the current `Asia/Shanghai` date. Existing VM inventory scan output becomes local-only and can no longer use the daily-report delivery route.

## Testing

- Pytest unit tests cover start/end card fields, duration formatting, skill-attempt ordering, idempotent delivery, project-group/host routing, and the four-field-only fault card.
- Callback tests cover all three buttons, stale/duplicate decisions, and executor-facing decision results.
- Query tests cover mention stripping, group authorization, active/terminal classification, exact VM eligibility, read-only SQLite access, and redaction.
- Daily-report tests cover the exact text, allowed statuses, required user fields, empty-data refusal, preview-hash confirmation, fixed destination, and delivery verification; inventory scans cannot send reports.
- Runner/contract tests verify the foreground prompt and shared contract include the lifecycle handshake.
- Final acceptance sends labeled start, end, and fault cards through Feishu OpenAPI to the configured project group and verifies returned message IDs/delivery. Callback semantics are tested against an isolated run registry so acceptance does not mutate a real submission.

## Non-Goals

- Re-enable `/提审 开始` or full registration-message intake.
- Route lifecycle messages to a distinct legacy daily-report route or arbitrary originating chats.
- Infer active runs from Notion, Feishu Base, VM bindings, Git history, or assistant memory.
- Add browser/desktop scraping, operator-role administration, or a second runbook outside the authoritative skill/shared-contract sources.
- Generate or send a daily report when the user has not supplied and confirmed the report fields.
