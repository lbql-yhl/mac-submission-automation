# Feishu Project Group Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add exact project-group start/end/fault cards and deterministic `@bot` queries for active applications and claimable VMs.

**Architecture:** Keep card rendering and read-only query logic in a focused observability module. Keep Feishu transport, exact run/host/project-group authorization, lifecycle state transitions, and CLI dispatch in the existing bot service. Wire the foreground executor through the generated prompt and shared automation contract; preserve the disabled Feishu intake switch.

**Tech Stack:** Python 3 standard library, Feishu OpenAPI, JSON 2.0 interactive cards, SQLite read-only URI mode, pytest.

**Repository constraint:** Do not commit, push, or rewrite unrelated dirty files. Verification replaces commit checkpoints because the project contract requires explicit commit authorization.

---

### Task 1: Pure Card And Query Model

**Files:**
- Create: `services/submission_observability.py`
- Create: `tests/test_submission_observability.py`

- [ ] **Step 1: Write failing tests for duration, cards, active runs, and VM eligibility**

```python
def test_start_and_end_cards_show_only_operational_fields():
    run = sample_run()
    assert card_lines(build_submission_start_card(run)) == [
        "**应用**：SampleApp",
        "**宿主**：host-a",
        "**开始时间**：2026-08-26 08:00:00 UTC",
    ]
    assert "utm-vm-clone" in card_text(build_submission_end_card(run))
    assert "流程故障次数" in card_text(build_submission_end_card(run))
    assert "1分 5秒" in card_text(build_submission_end_card(run))
    assert "run-id" not in card_text(build_submission_end_card(run))


def test_available_vm_names_use_exact_claim_predicate_without_writes(tmp_path):
    database = create_inventory_fixture(tmp_path)
    before = database.stat().st_mtime_ns
    assert list_available_vm_names(database) == ["abcd"]
    assert database.stat().st_mtime_ns == before
```

- [ ] **Step 2: Run the new tests and confirm collection fails on missing symbols**

Run: `python3 -m pytest tests/test_submission_observability.py -q`

Expected: FAIL during import because `services.submission_observability` does not exist.

- [ ] **Step 3: Implement the focused pure/read-only module**

```python
def format_duration(total_seconds: int) -> str:
    seconds = max(0, int(total_seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = ([f"{hours}小时"] if hours else []) + ([f"{minutes}分"] if minutes else [])
    parts.append(f"{seconds}秒")
    return " ".join(parts)


def list_available_vm_names(database: Path) -> list[str]:
    if not database.is_file() or database.is_symlink():
        raise ObservabilityError("VM inventory is unavailable")
    connection = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            """SELECT vm_name FROM vm_inventory
               WHERE available=1 AND application_name IS NULL
                 AND status='complete' AND directory_present=1 AND reusable=0
               ORDER BY vm_name"""
        ).fetchall()
    finally:
        connection.close()
    return [str(row[0]) for row in rows]
```

Also implement `build_submission_start_card(run)`, `build_submission_end_card(run)`, `active_submission_rows(runs, host, now)`, and `format_project_resource_reply(active_rows=rows, vm_names=names)` with the exact fields and redaction assertions established in Step 1. The end card includes `流程故障次数` in addition to application, host, outcome, actual skills, and duration. Card builders return schema-2.0 dictionaries; active rows require matching host, a lifecycle start, and no lifecycle finish.

`list_available_vm_names` must reject missing/symlink/non-regular files and open SQLite with `mode=ro`. Its query must exactly match the allocator predicate and sort by `vm_name`.

- [ ] **Step 4: Run the focused tests**

Run: `python3 -m pytest tests/test_submission_observability.py -q`

Expected: PASS.

### Task 2: Locked Lifecycle State And Idempotent Delivery

**Files:**
- Modify: `services/feishu_bot.py`
- Modify: `services/submission_runner.py`
- Create: `tests/test_feishu_project_lifecycle.py`

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_run_start_binds_project_group_and_confirms_delivery(monkeypatch, tmp_path):
    run = sample_run(chat_id="project-chat", host="host-a")
    install_temp_run_registry(monkeypatch, tmp_path, run)
    config = sample_config(allowed_chat_id="project-chat", submission_host_machine="host-a")
    monkeypatch.setattr(FeishuClient, "send_card", lambda *_a, **_k: {"data": {"message_id": "message"}})
    assert notify_run_start(arg_namespace(run_id=run["id"]), config) == 0
    stored = find_run(run["id"])
    assert stored["project_chat_id"] == "project-chat"
    assert stored["lifecycle"]["start_message_id"] == "message"


def test_skill_attempts_and_finish_are_idempotent(monkeypatch, tmp_path):
    run = sample_run(chat_id="project-chat", host="host-a")
    install_temp_run_registry(monkeypatch, tmp_path, run)
    config = sample_config(allowed_chat_id="project-chat", submission_host_machine="host-a")
    sent = []
    monkeypatch.setattr(FeishuClient, "send_card", lambda *_a, **_k: sent.append(1) or {"data": {"message_id": f"message-{len(sent)}"}})
    assert notify_run_start(arg_namespace(run_id=run["id"]), config) == 0
    assert record_skill_lifecycle(arg_namespace(run_id=run["id"], skill="utm-vm-clone", stage=""), config, "started") == 0
    assert record_skill_lifecycle(arg_namespace(run_id=run["id"], skill="utm-vm-clone", stage=""), config, "succeeded") == 0
    finish_args = arg_namespace(run_id=run["id"], outcome="success")
    assert notify_run_finish(finish_args, config) == 0
    assert notify_run_finish(finish_args, config) == 0
    stored = find_run(run["id"])
    assert len(sent) == 2
    assert stored["lifecycle"]["outcome"] == "success"
    assert [item["skill"] for item in stored["skill_attempts"]] == ["utm-vm-clone"]
```

- [ ] **Step 2: Run lifecycle tests and confirm missing lifecycle functions fail**

Run: `python3 -m pytest tests/test_feishu_project_lifecycle.py -q`

Expected: FAIL on missing `notify_run_start`, `record_skill_lifecycle`, and `notify_run_finish`.

- [ ] **Step 3: Add one advisory lock for all run-registry writers**

```python
@contextmanager
def locked_run_registry():
    fd = os.open(RUNS_LOCK_FILE, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
```

Use the lock in `save_run` and `mutate_run`. Change the legacy runner's `append_run_event` to call the bot's locked mutation helper rather than writing the JSON file independently.

- [ ] **Step 4: Implement lifecycle state transitions and CLI modes**

```python
LIFECYCLE_MODES = {
    "run-start",
    "skill-start",
    "skill-success",
    "skill-failure",
    "run-finish",
}

# Required state written by the mode handlers:
EXPECTED_LIFECYCLE_KEYS = {
    "started_at",
    "start_message_uuid",
    "start_message_id",
    "finished_at",
    "outcome",
    "duration_seconds",
    "end_message_uuid",
    "end_message_id",
}
```

Implement `project_chat_for_run(run, config, requested="")`, `notify_run_start(args, config)`, `record_skill_lifecycle(args, config, state)`, and `notify_run_finish(args, config)` as the only handlers for these transitions. Every handler first re-reads the exact run, validates host/project-group ownership, then performs one locked mutation; network handlers persist the UUID before sending and persist the returned message ID afterward.

Add modes `run-start`, `skill-start`, `skill-success`, `skill-failure`, and `run-finish`; add `--skill` and `--outcome`. Persist a stable UUID before network delivery and require a returned message ID. Repeated matching calls return success without resending; conflicting terminal outcomes fail closed.

- [ ] **Step 5: Wire the legacy runner without weakening foreground behavior**

Before spawning Codex, invoke the idempotent start transition. In all terminal branches invoke `run-finish` with `success`, `failed`, or `stopped`. The generated foreground prompt remains the primary mainline wiring.

- [ ] **Step 6: Run lifecycle and existing bot security tests**

Run: `python3 -m pytest tests/test_feishu_project_lifecycle.py tests/test_feishu_bot_config.py tests/test_feishu_runtime_security.py -q`

Expected: PASS.

### Task 3: Four-Field Project-Group Fault Card

**Files:**
- Modify: `services/feishu_bot.py`
- Modify: `tests/test_feishu_fault_card.py`
- Modify: `tests/test_feishu_card_callback_transport.py`
- Add assertions: `tests/test_feishu_project_lifecycle.py`

- [ ] **Step 1: Add a collected failing test for the exact visible fields**

```python
def test_fault_card_contains_only_required_fields_and_three_actions():
    card = build_fault_decision_card(sample_fault_run())
    text = card["body"]["elements"][0]["text"]["content"]
    assert text.splitlines() == [
        "**故障技能**：utm-image",
        "**技能故障步骤**：上传截图",
        "**应用**：SampleApp",
        "**宿主**：host-a",
    ]
    assert button_labels(card) == [
        "停止流程",
        "已人工处理，继续流程",
        "重试技能，跳过已处理成功的步骤",
    ]
```

- [ ] **Step 2: Run the test and confirm the old 11-field body fails**

Run: `python3 -m pytest tests/test_feishu_project_lifecycle.py -k fault -q`

Expected: FAIL because the card still exposes run, evidence, retry, and recovery fields and omits application.

- [ ] **Step 3: Route fault delivery to the bound project group and simplify rendering**

Keep all detailed recovery evidence in `pending_decision`, but render only the four requested facts. Change `notify_fault` to require `project_chat_for_run`. Extend callback ownership validation with the configured project group while preserving host, operator, decision-generation, waiting-state, duplicate, and timeout checks.

- [ ] **Step 4: Preserve the executor-facing decision contract**

```python
args = SimpleNamespace(run_id="run-1", timeout_seconds=10, poll_seconds=1, decision_kind="fault")
with patch("services.feishu_bot.find_run", return_value=answered_run("manual_continue")):
    assert wait_decision(args, config) == 0
with patch("services.feishu_bot.find_run", return_value=answered_run("retry_skill")):
    assert wait_decision(args, config) == 0
with patch("services.feishu_bot.find_run", return_value=answered_run("stop")):
    assert wait_decision(args, config) == 2
with patch("services.feishu_bot.find_run", return_value=expired_run()):
    assert wait_decision(args, config) == 3
```

Ensure `stop`/timeout lead to `run-finish --outcome stopped` only after execution is terminal. Manual continue and retry must not send an end card.

- [ ] **Step 5: Run direct and collected callback tests**

Run: `python3 tests/test_feishu_fault_card.py`

Run: `python3 tests/test_feishu_card_callback_transport.py`

Run: `python3 -m pytest tests/test_feishu_project_lifecycle.py tests/test_feishu_recovery_gate_and_auto_review.py -q`

Expected: all commands PASS.

### Task 4: Deterministic `@bot` Resource Queries

**Files:**
- Modify: `services/feishu_bot.py`
- Create: `tests/test_feishu_project_queries.py`

- [ ] **Step 1: Write failing tests for mentions, authorization, status, and VM failures**

```python
def test_mentioned_active_application_query_is_local_and_redacted(monkeypatch):
    reply = handle_incoming_text(config, "@Bot 正在提审的应用", "project-chat", source="test")
    assert "SampleApp" in reply
    assert "utm-image" in reply
    assert "run-id" not in reply
    assert "/runtime/" not in reply


def test_vm_query_uses_exact_allowed_group(monkeypatch):
    assert handle_incoming_text(config, "@Bot 可用的虚拟机", "other-chat", source="test") == ""
    assert handle_incoming_text(config, "@Bot 可用的虚拟机", "project-chat", source="test") == "可用虚拟机（1）：abcd"
```

- [ ] **Step 2: Run tests and confirm queries fall through or return empty**

Run: `python3 -m pytest tests/test_feishu_project_queries.py -q`

Expected: FAIL because mention-prefixed resource queries are not recognized.

- [ ] **Step 3: Implement mention-stripped deterministic intents before the assistant**

```python
def project_query_intent(text: str) -> str:
    cleaned = strip_feishu_markdown(text).strip()
    if cleaned in {"/提审 应用列表", "提审 应用列表"} or ("正在提审" in cleaned and "应用" in cleaned):
        return "applications"
    if cleaned in {"/提审 可用VM", "提审 可用VM"} or ("可用" in cleaned and "虚拟机" in cleaned):
        return "vms"
    if cleaned in {"/提审 资源", "提审 资源"}:
        return "all"
    return ""

def handle_project_query(config: Config, text: str, chat_id: str) -> str | None:
    if not config.allowed_chat_id or chat_id != config.allowed_chat_id:
        return None
    intent = project_query_intent(text)
    if not intent:
        return None
    active = active_submission_rows(read_runs_strict(), config.submission_host_machine, utc_datetime()) if intent in {"applications", "all"} else None
    vms = list_available_vm_names(VM_INVENTORY_DATABASE) if intent in {"vms", "all"} else None
    return format_project_resource_reply(active_rows=active, vm_names=vms)
```

Support `正在提审的应用`, `可用的虚拟机`, `/提审 应用列表`, `/提审 可用VM`, and `/提审 资源`. Read runs strictly, filter by exact local host plus started/not-finished lifecycle state, and open inventory SQLite read-only. Missing or corrupt state returns `查询失败` rather than `0`.

- [ ] **Step 4: Update help text and run query tests**

Run: `python3 -m pytest tests/test_feishu_project_queries.py tests/test_feishu_assistant_recovery.py tests/test_feishu_bot_config.py -q`

Expected: PASS.

### Task 5: Authoritative Foreground Wiring And Documentation

**Files:**
- Modify: `services/feishu_bot.py` (`build_codex_prompt`)
- Modify: `skills/_shared/AUTOMATION_CONTRACT.md`
- Modify: `docs/utm-feishu-bot.md`
- Modify: `README.md`
- Create: `tests/test_feishu_project_contract.py`

- [ ] **Step 1: Write failing contract tests**

```python
def test_generated_prompt_and_shared_contract_wire_lifecycle_commands():
    prompt = build_codex_prompt(sample_run())
    contract = CONTRACT.read_text(encoding="utf-8")
    for command in ("run-start", "skill-start", "skill-success", "skill-failure", "run-finish"):
        assert command in prompt
        assert command in contract


def test_intake_stays_disabled():
    assert SUBMISSION_START_ENABLED is False
```

- [ ] **Step 2: Run and confirm missing contract wiring fails**

Run: `python3 -m pytest tests/test_feishu_project_contract.py -q`

Expected: FAIL because the lifecycle commands are absent.

- [ ] **Step 3: Add exact foreground lifecycle instructions**

The shared contract must require `run-start` before the first skill side effect, skill events around each exact skill, `notify-fault` plus `wait-decision` only after the recovery gate, and one `run-finish` at the requested scope tail or terminal stop/failure. The generated prompt must use the same command names and exact inherited run/chat/host context.

- [ ] **Step 4: Document project-group cards and query phrases without duplicating skill runbooks**

Update the Feishu guide with the route, card fields, query phrases, real-card verification boundary, and the fact that intake remains disabled. Keep README to a short status/link summary.

- [ ] **Step 5: Run contract and documentation tests**

Run: `python3 -m pytest tests/test_feishu_project_contract.py tests/test_unattended_portable_skill_contract.py tests/test_skill_contract_references.py -q`

Expected: PASS.

### Task 6: User-Provided Daily Report

**Files:**
- Create: `scripts/feishu_daily_report.py`
- Create: `tests/test_feishu_daily_report.py`
- Modify: `scripts/vm_inventory_scan.py`
- Modify: `docs/utm-feishu-bot.md`
- Modify carefully without replacing existing user changes: `.env.example`

- [ ] **Step 1: Write failing formatter and delivery-gate tests**

```python
def test_report_uses_only_explicit_user_fields():
    payload = {
        "prepared_apps": ["AppA"],
        "review_items": [
            {"app": "AppB", "status": "审核中", "days": 3},
            {"app": "AppC", "status": "过审", "days": 1},
        ],
    }
    assert build_daily_report(payload, report_date=date(2026, 8, 26)) == (
        "日期：2026-08-26\n"
        "今天提审准备：\n"
        "AppA\n"
        "查审情况：\n"
        "AppB  审核中 3天\n"
        "AppC  过审 1天\n"
    )


def test_empty_or_unconfirmed_report_cannot_send(monkeypatch):
    with pytest.raises(DailyReportError):
        build_daily_report({"prepared_apps": [], "review_items": []}, report_date=date(2026, 8, 26))
    with pytest.raises(DailyReportError):
        send_daily_report(payload(), approval_sha256="wrong", user_confirmed=True)
    with pytest.raises(DailyReportError):
        send_daily_report(payload(), approval_sha256=expected_digest(), user_confirmed=False)
```

- [ ] **Step 2: Run and confirm the new module is missing**

Run: `python3 -m pytest tests/test_feishu_daily_report.py -q`

Expected: FAIL during import because `scripts.feishu_daily_report` does not exist.

- [ ] **Step 3: Implement explicit-input preview and send modes**

Accept one JSON payload from stdin containing only explicit user-provided application/status/day rows. Generate the date from `Asia/Shanghai` and the three fixed headings; never fetch or infer `无`, applications, statuses, or day counts. Reject an empty payload before any configuration or network access. `--send-feishu` requires both `--approval-sha256` and `--user-confirmed`. Resolve credentials and the authoritative `FEISHU_ALLOWED_CHAT_ID` destination only through one secure host-settings snapshot; treat `FEISHU_DAILY_REPORT_CHAT_ID` as optional legacy deny-only compatibility and never as a send target. Require a returned message ID and `verify_post_message_delivery` success. Print only the preview, digest, and redacted verification markers. VM inventory scanning remains local-only and cannot deliver through the daily-report entry.

- [ ] **Step 4: Disable VM inventory report delivery while preserving local scan/preview behavior**

Remove `--send-feishu` and `--approval-sha256` from `vm_inventory_scan`, or reject them before any network/config access with a message directing operators to the explicit user-provided daily-report entry. Keep inventory scan and reconciliation behavior unchanged.

- [ ] **Step 5: Run daily-report and inventory-scan tests**

Run: `python3 -m pytest tests/test_feishu_daily_report.py tests/test_vm_inventory_scan.py -q`

Expected: PASS with no network call for invalid, empty, unconfirmed, or inventory-derived reports.

### Task 7: Regression, Review, And Real Feishu Acceptance

**Files:**
- Verify all files above; do not edit `.env` or `runtime/` directly.

- [ ] **Step 1: Run focused Python tests and direct script checks**

Run: `python3 -m pytest tests/test_submission_observability.py tests/test_feishu_project_lifecycle.py tests/test_feishu_project_queries.py tests/test_feishu_project_contract.py tests/test_feishu_bot_config.py tests/test_feishu_runtime_security.py -q`

Run: `python3 tests/test_feishu_fault_card.py`

Run: `python3 tests/test_feishu_card_callback_transport.py`

Expected: PASS.

- [ ] **Step 2: Run repository verification**

Run: `python3 -m pytest -q`

Run: `node --test tests/test_utm_22_distribute.mjs`

Run: `python3 scripts/public_release_audit.py`

Run: `git diff --check`

Expected: all commands PASS. If unrelated pre-existing dirty tests fail, record the exact failing tests and separately prove the feature-focused suite.

- [ ] **Step 3: Review the diff for scope and sensitive output**

Check that no credential, real resource ID, root `.env`, runtime record, absolute host path, or unrelated user change appears in the diff. Confirm card/reply code never renders identifiers or raw exceptions.

- [ ] **Step 4: Send real labeled acceptance cards to the exact configured project group**

Use the secure host settings snapshot and `FeishuClient.send_card` to send one start, one end, and one unresolved fault card labeled `功能验收`. Resolve the destination only from `FEISHU_ALLOWED_CHAT_ID`; do not search by group name. Do not persist or mutate a real submission run.

- [ ] **Step 5: Verify real delivery without exposing IDs**

Require a nonempty OpenAPI message ID for all three responses and use the existing delivery verifier. Report only `start=verified`, `end=verified`, and `fault=verified`; do not print message/chat IDs. The fault card's three real callback payload shapes must also have passed the isolated callback tests from Step 1.
