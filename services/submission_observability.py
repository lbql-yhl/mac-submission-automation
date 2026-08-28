"""Pure card formatting and read-only submission resource queries."""

from __future__ import annotations

import sqlite3
import stat
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ObservabilityError(RuntimeError):
    """Raised when observability data cannot be handled safely."""


def format_duration(total_seconds: int) -> str:
    """Format a duration as compact Chinese hours, minutes, and seconds."""
    seconds = max(0, int(total_seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = [f"{hours}小时"] if hours else []
    if minutes:
        parts.append(f"{minutes}分")
    parts.append(f"{seconds}秒")
    return " ".join(parts)


def _clean_text(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback
    cleaned = str(value).strip()
    return cleaned or fallback


def _application_name(run: Mapping[str, Any]) -> str:
    return _clean_text(run.get("app_name"), "未知")


def _run_host(run: Mapping[str, Any]) -> str:
    submission_data = run.get("submission_data")
    if isinstance(submission_data, Mapping):
        host = _clean_text(submission_data.get("host_machine"))
        if host:
            return host
    return _clean_text(run.get("host_machine"))


def _run_lifecycle(run: Mapping[str, Any]) -> Mapping[str, Any]:
    lifecycle = run.get("lifecycle")
    return lifecycle if isinstance(lifecycle, Mapping) else {}


def _parse_timestamp(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        normalized = value.strip()
        if normalized.endswith(("Z", "z")):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as error:
            raise ObservabilityError("invalid lifecycle timestamp") from error
    else:
        raise ObservabilityError("invalid lifecycle timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ObservabilityError("lifecycle timestamp must be timezone-aware")
    return parsed


def _format_utc_timestamp(value: object) -> str:
    parsed = _parse_timestamp(value).astimezone(timezone.utc)
    return parsed.strftime("%Y-%m-%d %H:%M:%S UTC")


def _card(template: str, title: str, lines: list[str]) -> dict[str, Any]:
    return {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "header": {
            "template": template,
            "title": {"tag": "plain_text", "content": title},
        },
        "body": {
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "\n".join(lines)},
                }
            ]
        },
    }


def build_submission_start_card(run: Mapping[str, Any]) -> dict[str, Any]:
    """Build the redacted project-group card sent before the first skill."""
    app_name = _application_name(run)
    lines = [
        f"**应用**：{app_name}",
        f"**宿主**：{_run_host(run) or '未知'}",
        f"**开始时间**：{_format_utc_timestamp(_run_lifecycle(run).get('started_at'))}",
    ]
    return _card("green", f"{app_name} 开始提审", lines)


_TERMINAL_OUTCOMES = {
    "success": ("green", "提审成功", "成功"),
    "stopped": ("grey", "提审已停止", "已停止"),
    "failed": ("red", "提审失败", "失败"),
}


def _attempted_skills(run: Mapping[str, Any]) -> list[str]:
    attempts = run.get("skill_attempts")
    if not isinstance(attempts, Iterable) or isinstance(attempts, (str, bytes, Mapping)):
        return []
    skills: list[str] = []
    seen: set[str] = set()
    for attempt in attempts:
        if not isinstance(attempt, Mapping):
            continue
        skill = _clean_text(attempt.get("skill"))
        if skill and skill not in seen:
            seen.add(skill)
            skills.append(skill)
    return skills


def _failed_attempt_count(run: Mapping[str, Any]) -> int:
    attempts = run.get("skill_attempts")
    if not isinstance(attempts, Iterable) or isinstance(attempts, (str, bytes, Mapping)):
        return 0
    return sum(
        1
        for attempt in attempts
        if isinstance(attempt, Mapping) and attempt.get("status") == "failed"
    )


def build_submission_end_card(run: Mapping[str, Any]) -> dict[str, Any]:
    """Build a redacted, action-free card for a frozen terminal lifecycle."""
    app_name = _application_name(run)
    lifecycle = _run_lifecycle(run)
    outcome = _clean_text(lifecycle.get("outcome")).lower()
    try:
        template, title_suffix, outcome_label = _TERMINAL_OUTCOMES[outcome]
    except KeyError as error:
        raise ObservabilityError("unsupported terminal outcome") from error
    skills = _attempted_skills(run)
    lines = [
        f"**应用**：{app_name}",
        f"**宿主**：{_run_host(run) or '未知'}",
        f"**结果**：{outcome_label}",
        f"**执行技能**：{'、'.join(skills) if skills else '无'}",
        f"**流程故障次数**：{_failed_attempt_count(run)}",
        f"**耗时**：{format_duration(lifecycle.get('duration_seconds', 0))}",
    ]
    return _card(template, f"{app_name} {title_suffix}", lines)


def _active_state(run: Mapping[str, Any], lifecycle: Mapping[str, Any]) -> str:
    current_skill = _clean_text(run.get("current_skill"))
    if not current_skill:
        current_skill = _clean_text(lifecycle.get("current_skill"))
    return current_skill or "进行中"


def active_submission_rows(
    runs: Iterable[Mapping[str, Any]], host: str, now: datetime
) -> list[dict[str, str]]:
    """Return redacted active rows for one exact host, ordered by start and app."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ObservabilityError("now must be timezone-aware")
    exact_host = _clean_text(host)
    if not exact_host:
        return []

    sortable_rows: list[tuple[datetime, str, dict[str, str]]] = []
    for run in runs:
        if not isinstance(run, Mapping) or _run_host(run) != exact_host:
            continue
        lifecycle = _run_lifecycle(run)
        if lifecycle.get("finished_at"):
            continue
        started_value = lifecycle.get("started_at")
        if not started_value:
            continue
        try:
            started_at = _parse_timestamp(started_value)
        except ObservabilityError:
            continue
        app_name = _application_name(run)
        elapsed_seconds = max(0, int((now - started_at).total_seconds()))
        row = {
            "app": app_name,
            "state": _active_state(run, lifecycle),
            "elapsed": format_duration(elapsed_seconds),
        }
        sortable_rows.append((started_at.astimezone(timezone.utc), app_name, row))

    sortable_rows.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in sortable_rows]


def list_available_vm_names(database: Path) -> list[str]:
    """Read the allocator's exact claimable-VM snapshot without modifying SQLite."""
    path = Path(database).expanduser()

    def source_signature() -> tuple[int, ...]:
        try:
            metadata = path.lstat()
        except OSError as error:
            raise ObservabilityError("VM inventory is unavailable") from error
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ObservabilityError("VM inventory is unavailable")
        return (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_nlink,
            metadata.st_uid,
            metadata.st_gid,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )

    def require_no_sidecars(message: str) -> None:
        for suffix in ("-journal", "-wal", "-shm"):
            try:
                Path(f"{path}{suffix}").lstat()
            except FileNotFoundError:
                continue
            except OSError as error:
                raise ObservabilityError(message) from error
            raise ObservabilityError(message)

    before_signature = source_signature()
    require_no_sidecars("VM inventory is not quiescent")

    connection: sqlite3.Connection | None = None
    try:
        uri = f"{path.resolve(strict=True).as_uri()}?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True)
        rows = connection.execute(
            """SELECT vm_name FROM vm_inventory
               WHERE available=1 AND application_name IS NULL
                 AND status='complete' AND directory_present=1 AND reusable=0
               ORDER BY vm_name"""
        ).fetchall()
    except (OSError, ValueError, sqlite3.Error) as error:
        raise ObservabilityError("VM inventory cannot be read") from error
    finally:
        if connection is not None:
            connection.close()
    require_no_sidecars("VM inventory changed during observation")
    if source_signature() != before_signature:
        raise ObservabilityError("VM inventory changed during observation")
    return [str(row[0]) for row in rows]


def _single_line(value: object, fallback: str) -> str:
    cleaned = _clean_text(value, fallback)
    return " ".join(cleaned.splitlines()) or fallback


def _format_active_section(active_rows: Iterable[Mapping[str, Any]]) -> str:
    display_rows: list[tuple[str, str, str]] = []
    for row in active_rows:
        if not isinstance(row, Mapping):
            continue
        app = _single_line(row.get("app", row.get("app_name")), "未知")
        state = _single_line(
            row.get("state", row.get("current_skill", row.get("current"))),
            "进行中",
        )
        elapsed_value = row.get("elapsed")
        if elapsed_value is None and row.get("elapsed_seconds") is not None:
            elapsed_value = format_duration(row["elapsed_seconds"])
        elapsed = _single_line(elapsed_value, "0秒")
        display_rows.append((app, state, elapsed))
    display_rows.sort()
    if not display_rows:
        return "正在提审的应用（0）：无"
    lines = [f"正在提审的应用（{len(display_rows)}）："]
    lines.extend(f"- {app}｜{state}｜{elapsed}" for app, state, elapsed in display_rows)
    return "\n".join(lines)


def _format_vm_section(vm_names: Iterable[object]) -> str:
    names = sorted({_single_line(name, "") for name in vm_names if _clean_text(name)})
    if not names:
        return "可用虚拟机（0）：无"
    return f"可用虚拟机（{len(names)}）：{'、'.join(names)}"


def format_project_resource_reply(
    active_rows: Iterable[Mapping[str, Any]] | None = None,
    vm_names: Iterable[object] | None = None,
) -> str:
    """Format active-only, VM-only, or combined deterministic Chinese output."""
    sections: list[str] = []
    if active_rows is not None:
        sections.append(_format_active_section(active_rows))
    if vm_names is not None:
        sections.append(_format_vm_section(vm_names))
    return "\n".join(sections) if sections else "暂无资源信息"
