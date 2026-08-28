"""Persistent batch state and redacted Feishu cards for UTM VM cloning."""

from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

try:
    from host_config import secure_runtime_root, secure_write_text
    from submission_observability import format_duration
except ModuleNotFoundError:
    from services.host_config import secure_runtime_root, secure_write_text
    from services.submission_observability import format_duration


ROOT = Path(__file__).resolve().parents[1]
VM_CLONE_BATCHES_FILE = ROOT / "runtime" / "feishu-vm-clone-batches.json"
MAX_VM_CLONE_BATCH_COUNT = 10
ACTIVE_BATCH_STATUSES = frozenset({"queued", "running"})
VM_NAME_RE = re.compile(r"^[a-z]{4}$")
SAFE_FAILURE_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_:=.,;|/ -]{0,319}$")
INTERNAL_FAILURE_CODES = frozenset(
    {
        "batch_state_failed",
        "runner_dispatch_failed",
        "start_delivery_failed",
        "start_delivery_state_failed",
        "utm_vm_clone_failed",
        "utm_vm_clone_timeout",
        "utm_vm_clone_unavailable",
        "utm_vm_clone_verification_missing",
    }
)


class VmCloneBatchError(RuntimeError):
    """The VM clone batch cannot proceed without violating its contract."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def _locked_registry(path: Path) -> Iterator[None]:
    target = Path(path)
    secure_runtime_root(target.parent, create=True)
    lock_path = Path(f"{target}.lock")
    flags = (
        os.O_RDWR
        | os.O_CREAT
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        opened = os.fstat(descriptor)
        current = lock_path.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_dev != current.st_dev
            or opened.st_ino != current.st_ino
            or opened.st_nlink != 1
        ):
            raise VmCloneBatchError("虚拟机批次锁不安全")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    except OSError as error:
        raise VmCloneBatchError("虚拟机批次锁不可用") from error
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _read_registry(path: Path) -> dict[str, Any]:
    target = Path(path)
    try:
        metadata = target.lstat()
    except FileNotFoundError:
        return {"schema_version": 1, "batches": []}
    except OSError as error:
        raise VmCloneBatchError("虚拟机批次记录不可读") from error
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise VmCloneBatchError("虚拟机批次记录不安全")
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise VmCloneBatchError("虚拟机批次记录无效") from error
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != 1
        or not isinstance(value.get("batches"), list)
        or any(not isinstance(item, dict) for item in value["batches"])
    ):
        raise VmCloneBatchError("虚拟机批次记录无效")
    return value


def _write_registry(path: Path, value: Mapping[str, Any]) -> None:
    secure_write_text(
        Path(path),
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def create_vm_clone_batch(
    *,
    requested_count: int,
    chat_id: str,
    host_machine: str,
    source: str,
    registry_path: Path = VM_CLONE_BATCHES_FILE,
) -> dict[str, Any]:
    if not 1 <= int(requested_count) <= MAX_VM_CLONE_BATCH_COUNT:
        raise VmCloneBatchError("虚拟机创建数量无效")
    exact_chat = str(chat_id or "").strip()
    exact_host = str(host_machine or "").strip()
    if not exact_chat or not exact_host:
        raise VmCloneBatchError("虚拟机批次缺少项目群或宿主")
    now = utc_now()
    batch = {
        "id": uuid.uuid4().hex,
        "kind": "vm_clone_batch",
        "chat_id": exact_chat,
        "host_machine": exact_host,
        "requested_count": int(requested_count),
        "completed_count": 0,
        "completed_vm_names": [],
        "status": "queued",
        "source": str(source or "feishu"),
        "created_at": now,
        "updated_at": now,
        "start_message_uuid": uuid.uuid4().hex,
        "completion_message_uuid": uuid.uuid4().hex,
        "start_message_id": "",
        "completion_message_id": "",
    }
    with _locked_registry(registry_path):
        registry = _read_registry(registry_path)
        if any(
            str(item.get("status") or "") in ACTIVE_BATCH_STATUSES
            for item in registry["batches"]
        ):
            raise VmCloneBatchError("当前宿主已有虚拟机创建任务")
        registry["batches"].append(batch)
        registry["batches"] = registry["batches"][-100:]
        _write_registry(registry_path, registry)
    return dict(batch)


def mutate_vm_clone_batch(
    batch_id: str,
    mutator: Callable[[dict[str, Any]], None],
    *,
    registry_path: Path = VM_CLONE_BATCHES_FILE,
) -> dict[str, Any]:
    exact_id = str(batch_id or "").strip()
    if not exact_id:
        raise VmCloneBatchError("虚拟机批次标识无效")
    with _locked_registry(registry_path):
        registry = _read_registry(registry_path)
        matches = [item for item in registry["batches"] if item.get("id") == exact_id]
        if len(matches) != 1:
            raise VmCloneBatchError("虚拟机批次不存在或不唯一")
        mutator(matches[0])
        matches[0]["updated_at"] = utc_now()
        _write_registry(registry_path, registry)
        return dict(matches[0])


def find_vm_clone_batch(
    batch_id: str, *, registry_path: Path = VM_CLONE_BATCHES_FILE
) -> dict[str, Any] | None:
    with _locked_registry(registry_path):
        matches = [
            item
            for item in _read_registry(registry_path)["batches"]
            if item.get("id") == batch_id
        ]
        if len(matches) > 1:
            raise VmCloneBatchError("虚拟机批次记录不唯一")
        return dict(matches[0]) if matches else None


def record_vm_clone_batch_start_delivery(
    batch_id: str,
    message_id: str,
    *,
    registry_path: Path = VM_CLONE_BATCHES_FILE,
) -> dict[str, Any]:
    exact_message = str(message_id or "").strip()
    if not exact_message:
        raise VmCloneBatchError("开始卡送达标识缺失")

    def record(batch: dict[str, Any]) -> None:
        current = str(batch.get("start_message_id") or "")
        if current and current != exact_message:
            raise VmCloneBatchError("开始卡送达标识冲突")
        if batch.get("status") != "queued":
            raise VmCloneBatchError("虚拟机批次不再等待启动")
        batch["start_message_id"] = exact_message

    return mutate_vm_clone_batch(batch_id, record, registry_path=registry_path)


def claim_vm_clone_batch(
    batch_id: str, *, registry_path: Path = VM_CLONE_BATCHES_FILE
) -> dict[str, Any]:
    def claim(batch: dict[str, Any]) -> None:
        if batch.get("status") != "queued" or not batch.get("start_message_id"):
            raise VmCloneBatchError("虚拟机批次不可启动")
        batch["status"] = "running"
        batch["started_at"] = utc_now()
        batch["items"] = []

    return mutate_vm_clone_batch(batch_id, claim, registry_path=registry_path)


def record_vm_clone_batch_item_started(
    batch_id: str,
    index: int,
    *,
    registry_path: Path = VM_CLONE_BATCHES_FILE,
) -> dict[str, Any]:
    def start_item(batch: dict[str, Any]) -> None:
        completed = batch.get("completed_vm_names")
        items = batch.get("items")
        completed_count = int(batch.get("completed_count", len(completed or [])))
        if (
            batch.get("status") != "running"
            or not isinstance(completed, list)
            or not isinstance(items, list)
            or len(completed) != completed_count
            or index != completed_count + 1
            or index > int(batch.get("requested_count") or 0)
            or any(item.get("status") == "running" for item in items)
        ):
            raise VmCloneBatchError("虚拟机批次步骤顺序无效")
        items.append({"index": index, "status": "running", "started_at": utc_now()})
        batch["current_index"] = index

    return mutate_vm_clone_batch(batch_id, start_item, registry_path=registry_path)


def record_vm_clone_batch_item_success(
    batch_id: str,
    index: int,
    vm_name: str,
    *,
    registry_path: Path = VM_CLONE_BATCHES_FILE,
) -> dict[str, Any]:
    exact_vm_name = str(vm_name or "").strip()
    if VM_NAME_RE.fullmatch(exact_vm_name) is None:
        raise VmCloneBatchError("虚拟机名称无效")

    def succeed_item(batch: dict[str, Any]) -> None:
        names = batch.get("completed_vm_names")
        items = batch.get("items")
        completed_count = int(batch.get("completed_count", len(names or [])))
        if (
            batch.get("status") != "running"
            or not isinstance(names, list)
            or not isinstance(items, list)
            or len(names) != completed_count
            or completed_count != index - 1
            or int(batch.get("current_index") or 0) != index
            or not items
            or items[-1].get("index") != index
            or items[-1].get("status") != "running"
            or exact_vm_name in names
        ):
            raise VmCloneBatchError("虚拟机批次步骤结果无效")
        items[-1]["status"] = "completed"
        items[-1]["finished_at"] = utc_now()
        items[-1]["vm_name"] = exact_vm_name
        names.append(exact_vm_name)
        batch["completed_count"] = index
        batch["current_index"] = 0

    return mutate_vm_clone_batch(batch_id, succeed_item, registry_path=registry_path)


def freeze_vm_clone_batch(
    batch_id: str,
    outcome: str,
    duration_seconds: int,
    *,
    failure_code: str = "",
    available_vm_count: int | None = None,
    registry_path: Path = VM_CLONE_BATCHES_FILE,
) -> dict[str, Any]:
    exact_outcome = str(outcome or "").strip()
    if exact_outcome not in {"success", "failed"}:
        raise VmCloneBatchError("虚拟机批次结果无效")
    if available_vm_count is not None and (
        type(available_vm_count) is not int or available_vm_count < 0
    ):
        raise VmCloneBatchError("可用虚拟机数量无效")
    if exact_outcome == "success" and available_vm_count is None:
        raise VmCloneBatchError("成功批次缺少可用虚拟机数量")

    def freeze(batch: dict[str, Any]) -> None:
        if batch.get("status") not in ACTIVE_BATCH_STATUSES:
            raise VmCloneBatchError("虚拟机批次已经结束")
        names = batch.get("completed_vm_names")
        requested = int(batch.get("requested_count") or 0)
        completed_count = int(batch.get("completed_count", len(names or [])))
        if (
            not isinstance(names, list)
            or not len(names) == completed_count <= requested
            or (exact_outcome == "success" and completed_count != requested)
        ):
            raise VmCloneBatchError("虚拟机批次完成数量无效")
        items = batch.get("items")
        if isinstance(items, list) and items and items[-1].get("status") == "running":
            items[-1]["status"] = "failed"
            items[-1]["finished_at"] = utc_now()
        batch["status"] = "completed" if exact_outcome == "success" else "failed"
        batch["outcome"] = exact_outcome
        batch["failure_code"] = (
            str(failure_code or "") if exact_outcome != "success" else ""
        )
        batch["duration_seconds"] = max(0, int(duration_seconds))
        if exact_outcome == "success":
            batch["available_vm_count"] = available_vm_count
        batch["finished_at"] = utc_now()
        batch["current_index"] = 0

    return mutate_vm_clone_batch(batch_id, freeze, registry_path=registry_path)


def record_vm_clone_batch_completion_delivery(
    batch_id: str,
    message_id: str,
    *,
    registry_path: Path = VM_CLONE_BATCHES_FILE,
) -> dict[str, Any]:
    exact_message = str(message_id or "").strip()
    if not exact_message:
        raise VmCloneBatchError("完成卡送达标识缺失")

    def record(batch: dict[str, Any]) -> None:
        if batch.get("status") not in {"completed", "failed"}:
            raise VmCloneBatchError("虚拟机批次尚未结束")
        current = str(batch.get("completion_message_id") or "")
        if current and current != exact_message:
            raise VmCloneBatchError("完成卡送达标识冲突")
        batch["completion_message_id"] = exact_message

    return mutate_vm_clone_batch(batch_id, record, registry_path=registry_path)


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


def _single_line(value: object, fallback: str = "未知") -> str:
    cleaned = " ".join(str(value or "").splitlines()).strip()
    return cleaned or fallback


def build_vm_clone_batch_start_card(batch: Mapping[str, Any]) -> dict[str, Any]:
    count = int(batch.get("requested_count") or 0)
    if not 1 <= count <= MAX_VM_CLONE_BATCH_COUNT:
        raise VmCloneBatchError("虚拟机创建数量无效")
    return _card(
        "blue",
        "开始批量创建虚拟机",
        [
            "**执行技能**：utm-vm-clone",
            f"**计划创建**：{count}台",
            f"**宿主**：{_single_line(batch.get('host_machine'))}",
        ],
    )


def build_vm_clone_batch_end_card(batch: Mapping[str, Any]) -> dict[str, Any]:
    count = int(batch.get("requested_count") or 0)
    outcome = str(batch.get("outcome") or "").strip()
    if not 1 <= count <= MAX_VM_CLONE_BATCH_COUNT or outcome not in {
        "success",
        "failed",
    }:
        raise VmCloneBatchError("虚拟机批次终态无效")
    raw_names = batch.get("completed_vm_names")
    if not isinstance(raw_names, list):
        raise VmCloneBatchError("虚拟机名称名单无效")
    names = [str(name or "").strip() for name in raw_names]
    completed_count = int(batch.get("completed_count", len(names)))
    if (
        not len(names) == completed_count <= count
        or len(set(names)) != len(names)
        or any(VM_NAME_RE.fullmatch(name) is None for name in names)
    ):
        raise VmCloneBatchError("虚拟机名称名单无效")
    success = outcome == "success"
    if success and completed_count != count:
        raise VmCloneBatchError("成功批次的虚拟机数量不完整")
    lines = [
        f"**结果**：{'成功' if success else '失败'}",
        f"**完成数量**：{completed_count}/{count}",
    ]
    if names:
        lines.append(f"**新建虚拟机（{len(names)}）**：")
        lines.extend(f"- {name}" for name in names)
        lines.append("")
    elif completed_count == 0:
        lines.append("**新建虚拟机（0）**：无")
    if not success:
        failure_code = str(batch.get("failure_code") or "").strip()
        if failure_code in INTERNAL_FAILURE_CODES:
            failure_code = failure_code.upper()
        if SAFE_FAILURE_CODE_RE.fullmatch(failure_code):
            lines.append(f"**失败原因**：{failure_code}")
    else:
        available_vm_count = batch.get("available_vm_count")
        if type(available_vm_count) is not int or available_vm_count < 0:
            raise VmCloneBatchError("可用虚拟机数量无效")
        lines.append(f"**目前可用虚拟机**：{available_vm_count}台")
    lines.append(
        f"**总耗时**：{format_duration(int(batch.get('duration_seconds') or 0))}"
    )
    return _card(
        "green" if success else "red",
        "虚拟机批量创建完成" if success else "虚拟机批量创建失败",
        lines,
    )
