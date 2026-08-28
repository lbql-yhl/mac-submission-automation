from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

import services.submission_observability as submission_observability
from services.submission_observability import (
    ObservabilityError,
    active_submission_rows,
    build_submission_end_card,
    build_submission_start_card,
    format_duration,
    format_project_resource_reply,
    list_available_vm_names,
)


def sample_run() -> dict[str, object]:
    return {
        "id": "run-id-secret",
        "chat_id": "chat-id-secret",
        "prompt_path": "/private/runtime/secret-prompt.md",
        "app_name": "SampleApp",
        "host_machine": "host-fallback",
        "submission_data": {
            "host_machine": "host-a",
            "code_link": "https://example.invalid/secret-code",
            "proxy_password": "secret-password",
        },
        "lifecycle": {
            "started_at": "2026-08-26T08:00:00+00:00",
            "finished_at": "2026-08-26T08:10:00+00:00",
            "outcome": "success",
            "duration_seconds": 65,
        },
        "skill_attempts": [
            {"skill": "utm-vm-clone", "status": "failed"},
            {"skill": "utm-vm-clone", "status": "succeeded"},
            {"skill": "utm-notion", "status": "succeeded"},
        ],
    }


def card_lines(card: dict[str, object]) -> list[str]:
    body = card["body"]
    assert isinstance(body, dict)
    elements = body["elements"]
    assert isinstance(elements, list)
    assert len(elements) == 1
    element = elements[0]
    assert isinstance(element, dict)
    text = element["text"]
    assert isinstance(text, dict)
    content = text["content"]
    assert isinstance(content, str)
    return content.splitlines()


def card_text(card: dict[str, object]) -> str:
    return json.dumps(card, ensure_ascii=False, sort_keys=True)


def create_inventory_fixture(tmp_path: Path) -> Path:
    database = tmp_path / "inventory.sqlite3"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """CREATE TABLE vm_inventory (
                   vm_name TEXT,
                   application_name TEXT,
                   status TEXT,
                   directory_present INTEGER,
                   reusable INTEGER,
                   available INTEGER
               )"""
        )
        connection.executemany(
            "INSERT INTO vm_inventory VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("wxyz", None, "complete", 1, 0, 1),
                ("abcd", None, "complete", 1, 0, 1),
                ("bound", "AssignedApp", "complete", 1, 0, 1),
                ("empty", "", "complete", 1, 0, 1),
                ("busy", None, "complete", 1, 0, 0),
                ("copy", None, "copying", 1, 0, 1),
                ("gone", None, "complete", 0, 0, 1),
                ("reuse", None, "complete", 1, 1, 1),
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return database


def non_access_metadata(path: Path) -> tuple[int, int, int, int, int]:
    metadata = path.stat()
    return (
        metadata.st_mode,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "0秒"),
        (5, "5秒"),
        (65, "1分 5秒"),
        (3600, "1小时 0秒"),
        (3661, "1小时 1分 1秒"),
        (-5, "0秒"),
    ],
)
def test_format_duration_is_compact_and_nonnegative(seconds: int, expected: str) -> None:
    assert format_duration(seconds) == expected


def test_start_card_has_exact_operational_fields_and_redacts_run_data() -> None:
    card = build_submission_start_card(sample_run())

    assert card["schema"] == "2.0"
    assert card["header"] == {
        "template": "green",
        "title": {"tag": "plain_text", "content": "SampleApp 开始提审"},
    }
    assert card_lines(card) == [
        "**应用**：SampleApp",
        "**宿主**：host-a",
        "**开始时间**：2026-08-26 08:00:00 UTC",
    ]
    rendered = card_text(card)
    for secret in (
        "run-id-secret",
        "chat-id-secret",
        "/private/runtime/secret-prompt.md",
        "secret-code",
        "secret-password",
        "host-fallback",
    ):
        assert secret not in rendered


def test_start_card_falls_back_to_top_level_host() -> None:
    run = sample_run()
    run["submission_data"] = {}
    run["host_machine"] = "host-b"

    assert card_lines(build_submission_start_card(run))[1] == "**宿主**：host-b"


@pytest.mark.parametrize(
    ("outcome", "template", "title", "label"),
    [
        ("success", "green", "SampleApp 提审成功", "成功"),
        ("stopped", "grey", "SampleApp 提审已停止", "已停止"),
        ("failed", "red", "SampleApp 提审失败", "失败"),
    ],
)
def test_end_card_uses_terminal_outcome_color_and_has_no_actions(
    outcome: str, template: str, title: str, label: str
) -> None:
    run = sample_run()
    lifecycle = run["lifecycle"]
    assert isinstance(lifecycle, dict)
    lifecycle["outcome"] = outcome

    card = build_submission_end_card(run)

    assert card["schema"] == "2.0"
    assert card["header"] == {
        "template": template,
        "title": {"tag": "plain_text", "content": title},
    }
    assert card_lines(card) == [
        "**应用**：SampleApp",
        "**宿主**：host-a",
        f"**结果**：{label}",
        "**执行技能**：utm-vm-clone、utm-notion",
        "**流程故障次数**：1",
        "**耗时**：1分 5秒",
    ]
    assert "button" not in card_text(card)


def test_end_card_uses_frozen_duration_and_first_attempt_order_only() -> None:
    run = sample_run()
    run["skill_attempts"] = [
        {"skill": "utm-image", "status": "started"},
        {"skill": "utm-p8", "status": "started"},
        {"skill": "utm-image", "status": "started"},
        {"skill": "", "status": "started"},
        {"status": "started"},
    ]
    lifecycle = run["lifecycle"]
    assert isinstance(lifecycle, dict)
    lifecycle["duration_seconds"] = 3661

    card = build_submission_end_card(run)

    assert card_lines(card)[3:] == [
        "**执行技能**：utm-image、utm-p8",
        "**流程故障次数**：0",
        "**耗时**：1小时 1分 1秒",
    ]
    rendered = card_text(card)
    for secret in (
        "run-id-secret",
        "chat-id-secret",
        "/private/runtime/secret-prompt.md",
        "secret-code",
        "secret-password",
    ):
        assert secret not in rendered


def test_end_card_counts_each_failed_attempt_including_retries() -> None:
    run = sample_run()
    run["skill_attempts"] = [
        {"skill": "utm-image", "status": "failed"},
        {"skill": "utm-image", "status": "failed"},
        {"skill": "utm-image", "status": "succeeded"},
        {"skill": "utm-p8", "status": "started"},
        {"skill": "utm-21", "status": "FAILED"},
    ]

    assert card_lines(build_submission_end_card(run))[3:] == [
        "**执行技能**：utm-image、utm-p8、utm-21",
        "**流程故障次数**：2",
        "**耗时**：1分 5秒",
    ]


def test_active_rows_filter_host_and_terminal_runs_and_sort_deterministically() -> None:
    runs = [
        {
            "id": "beta-secret",
            "app_name": "Beta",
            "submission_data": {"host_machine": "host-a"},
            "current_skill": "utm-key",
            "lifecycle": {"started_at": "2026-08-26T08:00:00Z"},
        },
        {
            "id": "alpha-secret",
            "app_name": "Alpha",
            "submission_data": {"host_machine": "host-a"},
            "current_skill": "utm-login",
            "lifecycle": {"started_at": "2026-08-26T08:00:00+00:00"},
        },
        {
            "id": "gamma-secret",
            "app_name": "Gamma",
            "host_machine": "host-a",
            "status": "running",
            "lifecycle": {"started_at": "2026-08-26T08:30:00+00:00"},
        },
        {
            "app_name": "OtherHost",
            "host_machine": "host-a",
            "submission_data": {"host_machine": "host-b"},
            "current_skill": "utm-image",
            "lifecycle": {"started_at": "2026-08-26T07:00:00+00:00"},
        },
        {
            "app_name": "Finished",
            "submission_data": {"host_machine": "host-a"},
            "current_skill": "utm-24",
            "lifecycle": {
                "started_at": "2026-08-26T07:00:00+00:00",
                "finished_at": "2026-08-26T07:30:00+00:00",
            },
        },
        {
            "app_name": "NeverStarted",
            "submission_data": {"host_machine": "host-a"},
            "lifecycle": {},
        },
        {
            "app_name": "Malformed",
            "submission_data": {"host_machine": "host-a"},
            "lifecycle": {"started_at": "not-a-timestamp"},
        },
    ]

    rows = active_submission_rows(
        runs,
        "host-a",
        datetime(2026, 8, 26, 9, 1, 1, tzinfo=timezone.utc),
    )

    assert rows == [
        {"app": "Alpha", "state": "utm-login", "elapsed": "1小时 1分 1秒"},
        {"app": "Beta", "state": "utm-key", "elapsed": "1小时 1分 1秒"},
        {"app": "Gamma", "state": "进行中", "elapsed": "31分 1秒"},
    ]
    assert "secret" not in json.dumps(rows, ensure_ascii=False)


def test_active_rows_require_timezone_aware_now() -> None:
    with pytest.raises(ObservabilityError, match="timezone-aware"):
        active_submission_rows([], "host-a", datetime(2026, 8, 26, 9, 0, 0))


def test_available_vm_names_use_exact_claim_predicate_without_writes(
    tmp_path: Path,
) -> None:
    database = create_inventory_fixture(tmp_path)
    before = database.stat().st_mtime_ns

    assert list_available_vm_names(database) == ["abcd", "wxyz"]
    assert database.stat().st_mtime_ns == before


def test_available_vm_names_does_not_create_wal_files_or_mutate_source_metadata(
    tmp_path: Path,
) -> None:
    database = create_inventory_fixture(tmp_path)
    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    finally:
        connection.close()

    wal_path = Path(f"{database}-wal")
    shm_path = Path(f"{database}-shm")
    assert not wal_path.exists()
    assert not shm_path.exists()
    before_entries = sorted(path.name for path in tmp_path.iterdir())
    before_metadata = {
        "directory": non_access_metadata(tmp_path),
        "database": non_access_metadata(database),
    }

    assert list_available_vm_names(database) == ["abcd", "wxyz"]

    assert sorted(path.name for path in tmp_path.iterdir()) == before_entries
    assert not wal_path.exists()
    assert not shm_path.exists()
    assert {
        "directory": non_access_metadata(tmp_path),
        "database": non_access_metadata(database),
    } == before_metadata


def test_available_vm_names_rejects_active_wal_instead_of_returning_stale_rows(
    tmp_path: Path,
) -> None:
    database = create_inventory_fixture(tmp_path)
    writer = sqlite3.connect(database)
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("UPDATE vm_inventory SET available=0 WHERE vm_name='abcd'")
        writer.commit()
        current_names = [
            str(row[0])
            for row in writer.execute(
                """SELECT vm_name FROM vm_inventory
                   WHERE available=1 AND application_name IS NULL
                     AND status='complete' AND directory_present=1 AND reusable=0
                   ORDER BY vm_name"""
            ).fetchall()
        ]
        assert current_names == ["wxyz"]
        assert Path(f"{database}-wal").is_file()
        assert Path(f"{database}-shm").is_file()

        try:
            observed_names = list_available_vm_names(database)
        except ObservabilityError:
            pass
        else:
            pytest.fail(
                "stale availability returned while committed WAL content was active: "
                f"observer={observed_names!r}, writer={current_names!r}"
            )
    finally:
        writer.close()


def test_available_vm_names_rejects_hard_link_with_alternate_wal(
    tmp_path: Path,
) -> None:
    database = create_inventory_fixture(tmp_path)
    alternate = tmp_path / "alternate.sqlite3"
    os.link(database, alternate)
    writer = sqlite3.connect(alternate)
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("UPDATE vm_inventory SET available=0 WHERE vm_name='abcd'")
        writer.commit()
        current_names = [
            str(row[0])
            for row in writer.execute(
                """SELECT vm_name FROM vm_inventory
                   WHERE available=1 AND application_name IS NULL
                     AND status='complete' AND directory_present=1 AND reusable=0
                   ORDER BY vm_name"""
            ).fetchall()
        ]
        assert current_names == ["wxyz"]
        assert Path(f"{alternate}-wal").is_file()
        assert not Path(f"{database}-wal").exists()
        assert database.stat().st_nlink == 2

        try:
            observed_names = list_available_vm_names(database)
        except ObservabilityError:
            pass
        else:
            pytest.fail(
                "stale availability returned through a hard-link alias: "
                f"observer={observed_names!r}, writer={current_names!r}"
            )
    finally:
        writer.close()


def test_available_vm_names_rejects_hot_rollback_journal_snapshot(
    tmp_path: Path,
) -> None:
    database = create_inventory_fixture(tmp_path)
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "CREATE TABLE rollback_pressure (id INTEGER PRIMARY KEY, payload BLOB)"
        )
        connection.executemany(
            "INSERT INTO rollback_pressure(payload) VALUES (zeroblob(4096))",
            [() for _ in range(256)],
        )
        connection.commit()
    finally:
        connection.close()

    child = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os, sqlite3, sys; "
                "connection = sqlite3.connect(sys.argv[1]); "
                "connection.execute('PRAGMA journal_mode=DELETE'); "
                "connection.execute('PRAGMA synchronous=FULL'); "
                "connection.execute('PRAGMA cache_size=1'); "
                "connection.execute('PRAGMA cache_spill=ON'); "
                "connection.execute('BEGIN IMMEDIATE'); "
                "connection.execute(\"UPDATE vm_inventory SET available=0 "
                "WHERE vm_name='abcd'\"); "
                "connection.execute(\"UPDATE rollback_pressure "
                "SET payload=randomblob(4096)\"); "
                "os._exit(0)"
            ),
            str(database),
        ],
        check=False,
    )
    assert child.returncode == 0
    journal = Path(f"{database}-journal")
    assert journal.is_file()
    assert journal.stat().st_size > 512

    try:
        observed_names = list_available_vm_names(database)
    except ObservabilityError:
        pass
    else:
        pytest.fail(
            "availability returned from a hot rollback-journal snapshot: "
            f"observer={observed_names!r}, committed=['abcd', 'wxyz']"
        )


@pytest.mark.parametrize(
    ("suffix", "entry_kind"),
    [("-wal", "symlink"), ("-shm", "directory")],
)
def test_available_vm_names_rejects_unsafe_sidecar_entries(
    tmp_path: Path, suffix: str, entry_kind: str
) -> None:
    database = create_inventory_fixture(tmp_path)
    sidecar = Path(f"{database}{suffix}")
    if entry_kind == "symlink":
        sidecar.symlink_to(database)
    else:
        sidecar.mkdir()

    with pytest.raises(ObservabilityError, match="not quiescent"):
        list_available_vm_names(database)


@pytest.mark.parametrize("race_kind", ["database", "sidecar"])
def test_available_vm_names_rejects_source_races(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, race_kind: str
) -> None:
    database = create_inventory_fixture(tmp_path)
    real_connect = sqlite3.connect

    def racing_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        connection = real_connect(*args, **kwargs)
        if race_kind == "database":
            metadata = database.stat()
            os.utime(
                database,
                ns=(metadata.st_atime_ns, metadata.st_mtime_ns + 1_000_000_000),
            )
        else:
            Path(f"{database}-wal").write_bytes(b"appeared during observation")
        return connection

    monkeypatch.setattr(submission_observability.sqlite3, "connect", racing_connect)

    with pytest.raises(ObservabilityError, match="changed during observation"):
        list_available_vm_names(database)


def test_available_vm_names_reject_missing_symlink_and_nonregular_paths(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(ObservabilityError, match="unavailable"):
        list_available_vm_names(missing)
    assert not missing.exists()

    database = create_inventory_fixture(tmp_path)
    link = tmp_path / "inventory-link.sqlite3"
    link.symlink_to(database)
    with pytest.raises(ObservabilityError, match="unavailable"):
        list_available_vm_names(link)

    with pytest.raises(ObservabilityError, match="unavailable"):
        list_available_vm_names(tmp_path)


@pytest.mark.parametrize("fixture_kind", ["corrupt", "incompatible"])
def test_available_vm_names_normalize_corrupt_or_incompatible_database_errors(
    tmp_path: Path, fixture_kind: str
) -> None:
    database = tmp_path / f"{fixture_kind}.sqlite3"
    if fixture_kind == "corrupt":
        database.write_bytes(b"not a sqlite database")
    else:
        connection = sqlite3.connect(database)
        try:
            connection.execute("CREATE TABLE unrelated (value TEXT)")
            connection.commit()
        finally:
            connection.close()
    before = database.stat().st_mtime_ns

    with pytest.raises(ObservabilityError, match="cannot be read"):
        list_available_vm_names(database)

    assert database.stat().st_mtime_ns == before


def test_project_resource_reply_supports_active_vm_and_combined_modes() -> None:
    active = [
        {
            "app": "Beta",
            "state": "进行中",
            "elapsed": "5秒",
            "run_id": "must-not-leak",
        },
        {
            "app": "Alpha",
            "state": "utm-login",
            "elapsed": "1分 5秒",
            "prompt_path": "/private/runtime/must-not-leak",
        },
    ]

    active_reply = format_project_resource_reply(active_rows=active)
    assert active_reply == (
        "正在提审的应用（2）：\n"
        "- Alpha｜utm-login｜1分 5秒\n"
        "- Beta｜进行中｜5秒"
    )
    assert "must-not-leak" not in active_reply

    assert format_project_resource_reply(vm_names=["wxyz", "abcd"]) == (
        "可用虚拟机（2）：abcd、wxyz"
    )
    assert format_project_resource_reply(active_rows=active, vm_names=["wxyz", "abcd"]) == (
        f"{active_reply}\n可用虚拟机（2）：abcd、wxyz"
    )


def test_project_resource_reply_has_clear_zero_states() -> None:
    assert format_project_resource_reply(active_rows=[]) == "正在提审的应用（0）：无"
    assert format_project_resource_reply(vm_names=[]) == "可用虚拟机（0）：无"
    assert format_project_resource_reply(active_rows=[], vm_names=[]) == (
        "正在提审的应用（0）：无\n可用虚拟机（0）：无"
    )
