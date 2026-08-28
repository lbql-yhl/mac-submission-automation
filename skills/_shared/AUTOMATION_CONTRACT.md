# Portable Automation Contract

This contract applies to all 16 UTM skills. A skill body supplies the business-specific inputs, entry point, evidence, and handoff; this file supplies only shared execution rules.

## Portable bootstrap

Before any skill command, change to the repository root and run exactly:

```bash
eval "$(python3 scripts/preflight.py --project-only --emit-shell)"
```

After bootstrap, resolve every repository file from `$PROJECT_ROOT`. Do not hard-code a host user name, home directory, virtual-environment path, plugin version, VM name, IP address, or credential. Use `python3` for Python entry points.

`--project-only --emit-shell` is the only bootstrap mode used by skills. It must not read host secrets. Never print the root `.env`, secret values, tokens, passwords, private keys, JWTs, authenticated URLs, clipboard contents, or raw internal helper output.

## Immutable run context

Keep the inherited `run_id`, original `chat_id`, host identity, application, VM name/IP/user, App ID, Bundle ID, browser process/session, repository/workspace, version/build, and stable attempt IDs bound to the same run. Never replace them with the newest, first, or closest candidate.

Read sensitive settings only through repository code that securely snapshots the root `.env`. Keep values in process memory, pass them through protected stdin or environment channels, and clear sensitive clipboard contents immediately after use.

## Project-group lifecycle handshake

The foreground executor preserves the same exact inherited run, original chat, and host identity for the full requested scope. It must use the repository lifecycle entry points in this order:

1. 首次技能副作用之前，调用 `python3 services/feishu_bot.py run-start --run-id "$SUBMISSION_RUN_ID" --chat-id "$SUBMISSION_CHAT_ID"`，并等待开始卡消息 ID 确认。未确认时不得开始技能副作用。
2. 每次实际技能尝试在其第一个副作用之前调用 `skill-start`，并传入同一 `--run-id`、`--chat-id`、精确 `--skill` 与当前 `--stage`。
3. 独立复验完成后调用 `skill-success`；已确认失败时先调用 `skill-failure`，再进入本合同的有界恢复。重试同一技能时创建新的开始/结束尝试，不改换 run、chat、host 或目标。
4. 只有恢复穷尽后，才可按恢复证据门禁调用 `notify-fault`，随后调用 `wait-decision`。普通可恢复故障不得提前发卡或等待。
5. 到请求范围尾端，或确认终止失败或停止且执行器不再继续后，恰好一次调用 `run-finish --outcome success|failed|stopped`。人工继续或重试决定本身不是终态，不得提前结束 run。

Lifecycle events contain only the exact skill and a non-sensitive step label. Detailed diagnostics, paths, credentials, raw payloads, run IDs, and chat IDs are never rendered into group cards or query replies.

`FEISHU_ALLOWED_CHAT_ID` is the one exact project-group route for lifecycle cards, deterministic queries, ordinary replies, and user-confirmed daily reports. It is never resolved by display name. `FEISHU_DAILY_REPORT_CHAT_ID` is an optional legacy deny-only route and is never a send target; when it equals the project-group route, bot configuration normalizes it to empty so the project group is not excluded as report-only. The start card is confirmed before the first side effect. The terminal card contains only 应用、宿主、结果、实际执行技能、流程故障次数和耗时, and has no action buttons.

After the recovery gate, the final fault card exposes exactly four facts: 故障技能、技能故障步骤、应用、宿主. It retains exactly three actions: `stop`; `manual_continue`, which revalidates live state before continuing; and `retry_skill`, which retries the failed skill while revalidating every previously completed checkpoint before skipping it.

Project-group queries are handled before generic assistant fallback and support `正在提审的应用`, `可用的虚拟机`, `/提审 应用列表`, `/提审 可用VM`, and `/提审 资源`. They use only the exact local host, require `lifecycle.started_at` without `lifecycle.finished_at` for an active run, read VM inventory without writes, and return `查询失败` when required registry or inventory state is missing, unsafe, corrupt, or incompatible. Replies disclose no run/chat IDs, paths, credentials, or raw records. Feishu submission intake remains disabled.

Real acceptance uses Feishu OpenAPI against the exact configured project group, requires returned message IDs and delivery verification, and reports only redacted verification markers. It never prints configured identifiers or API payloads. This shared section defines lifecycle boundaries only; it does not reproduce any individual skill runbook.

## One public host entry

Run only the public host entry or entry helper named in the current skill. Internal modules, guest helpers, browser functions, and sub-stage scripts are implementation details unless the skill explicitly says that the public entry covers only one automated sub-stage.

Each invocation emits only a non-sensitive summary:

```text
开始执行：<skill>
执行成功：<skill>；<verified marker>
```

or:

```text
开始执行：<skill>
执行报错：<skill>；<non-sensitive reason>
```

Do not forward commands, tracebacks, helper logs, identifiers not required by the success marker, or secret-bearing diagnostics.

## Observe, act, verify

For every command or GUI side effect:

1. Re-read the current run, target identity, and live state.
2. Require exactly one enabled target matching the expected page, parent region, text, path, or API identity.
3. Perform one minimum action.
4. Poll the resulting state with the skill's bounded schedule.
5. Re-read fresh evidence and record the skill's marker only when all stated invariants hold.

A click, launched process, closed dialog, zero exit code, old screenshot, or absence of visible error is not sufficient evidence.

## Bounded recovery

Retry only the exact failed checkpoint while preserving the same run and target. Unless a skill defines a stricter schedule, use at most three rounds with delays of 0, 5, and 10 seconds. For each round: diagnose, apply one safe reversible repair, then independently reverify. Do not reset the budget by restarting the skill.

After an interrupted public entry, invoke that same public entry again and revalidate from its first checkpoint. A verified idempotent checkpoint may skip its side effect; an irreversible or result-unknown attempt may only be reconciled by read-only checks and must never be repeated speculatively.

For GUI recovery, discard old coordinates and screenshots, return with `Escape`, `Cancel`, or an explicitly verified tab/page, and locate the unique target again. For browser stages, preserve the inherited Edge PID, profile, CDP session, and successful tabs; never restart a browser after login has been verified.

Only after the bounded budget is exhausted, or three read-only checks prove an external state such as CAPTCHA, account lock, missing authority, ownership conflict, or ambiguous irreversible result, may the workflow use the repository fault-notification service. Fault evidence must be non-sensitive and include the attempt count, recovery actions, and last verified checkpoint.

## Continuous handoff

On success, immediately pass the same verified context and live session to the next skill inside the same segment. Do not wait for ordinary user confirmation. A segment-tail skill stops at the segment boundary unless the active request covers the following segment. `utm-24` is the only final workflow endpoint.

Never hand off a partial, blocked, ambiguous, or result-unknown state.
