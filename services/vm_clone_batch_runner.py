#!/usr/bin/env python3
"""Run one Feishu-requested UTM VM clone batch sequentially."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.vm_clone_batch import (  # noqa: E402
    VM_CLONE_BATCHES_FILE,
    VmCloneBatchError,
    build_vm_clone_batch_end_card,
    claim_vm_clone_batch,
    freeze_vm_clone_batch,
    record_vm_clone_batch_completion_delivery,
    record_vm_clone_batch_item_started,
    record_vm_clone_batch_item_success,
)


SUCCESS_RESULT_RE = re.compile(
    r"执行成功：utm-vm-clone；"
    r"UTM_CLONE_AND_INITIALIZE=verified;VM_NAME=([a-z]{4})"
)
SAFE_SKILL_FAILURE_RE = re.compile(
    r"(?m)^执行报错：utm-vm-clone；([A-Z][A-Z0-9_:=.,;|/ -]{0,319})$"
)
DEFAULT_CLONE_TIMEOUT_SECONDS = 21600
SKILL_ENTRY_COMMAND = (
    'bootstrap=$("$VM_CLONE_PYTHON" scripts/preflight.py --project-only --emit-shell) '
    '|| { printf "%s\\n" "执行报错：utm-vm-clone；SKILL_BOOTSTRAP_FAILED" >&2; exit 1; }; '
    'eval "$bootstrap" '
    '|| { printf "%s\\n" "执行报错：utm-vm-clone；SKILL_BOOTSTRAP_INVALID" >&2; exit 1; }; '
    'exec "$VM_CLONE_PYTHON" "$PROJECT_ROOT/scripts/utm_clone_and_initialize.py"'
)


class VmCloneBatchExecutionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def run_existing_utm_vm_clone(
    *,
    project_root: Path = ROOT,
    timeout_seconds: int = DEFAULT_CLONE_TIMEOUT_SECONDS,
) -> str:
    root = Path(project_root).resolve()
    command = ["/bin/zsh", "-c", SKILL_ENTRY_COMMAND]
    environment = os.environ.copy()
    environment["VM_CLONE_PYTHON"] = sys.executable
    try:
        result = subprocess.run(
            command,
            cwd=str(root),
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise VmCloneBatchExecutionError("utm_vm_clone_timeout") from error
    except OSError as error:
        raise VmCloneBatchExecutionError("utm_vm_clone_unavailable") from error
    if result.returncode != 0:
        safe_reasons = SAFE_SKILL_FAILURE_RE.findall(
            "\n".join((str(result.stdout or ""), str(result.stderr or "")))
        )
        raise VmCloneBatchExecutionError(
            safe_reasons[-1] if safe_reasons else "SKILL_ENTRY_FAILED"
        )
    terminal_lines = [
        line.strip()
        for line in str(result.stdout or "").splitlines()
        if line.strip().startswith("执行成功：utm-vm-clone；")
    ]
    match = (
        SUCCESS_RESULT_RE.fullmatch(terminal_lines[0])
        if len(terminal_lines) == 1
        else None
    )
    if match is None:
        raise VmCloneBatchExecutionError("utm_vm_clone_verification_missing")
    return match.group(1)


def _default_available_vm_count() -> int:
    from services.submission_observability import list_available_vm_names

    return len(list_available_vm_names(ROOT / "runtime" / "vm-inventory.sqlite3"))


def _default_terminal_sender(config: Any, batch: dict[str, Any]) -> str:
    from services import feishu_bot

    response = feishu_bot.FeishuClient(config).send_card(
        str(batch.get("chat_id") or ""),
        build_vm_clone_batch_end_card(batch),
        message_uuid=str(batch.get("completion_message_uuid") or ""),
    )
    message_id = feishu_bot.message_id_from_response(response)
    if not message_id:
        raise VmCloneBatchExecutionError("completion_delivery_unconfirmed")
    return message_id


def run_batch(
    batch_id: str,
    config: Any,
    *,
    registry_path: Path = VM_CLONE_BATCHES_FILE,
    clone_once: Callable[[], str] = run_existing_utm_vm_clone,
    available_vm_count_reader: Callable[[], int] = _default_available_vm_count,
    terminal_sender: Callable[[dict[str, Any]], str] | None = None,
    monotonic_clock: Callable[[], float] = time.monotonic,
) -> int:
    try:
        batch = claim_vm_clone_batch(batch_id, registry_path=registry_path)
    except VmCloneBatchError:
        return 2
    started = monotonic_clock()
    outcome = "success"
    failure_code = ""
    available_vm_count: int | None = None
    try:
        for index in range(1, int(batch["requested_count"]) + 1):
            record_vm_clone_batch_item_started(
                batch_id, index, registry_path=registry_path
            )
            try:
                vm_name = clone_once()
            except VmCloneBatchExecutionError:
                raise
            except Exception as error:
                raise VmCloneBatchExecutionError("utm_vm_clone_failed") from error
            record_vm_clone_batch_item_success(
                batch_id, index, vm_name, registry_path=registry_path
            )
        try:
            candidate_available_vm_count = available_vm_count_reader()
        except Exception as error:
            raise VmCloneBatchExecutionError(
                "AVAILABLE_VM_COUNT_UNAVAILABLE"
            ) from error
        if (
            type(candidate_available_vm_count) is not int
            or candidate_available_vm_count < 0
        ):
            raise VmCloneBatchExecutionError("AVAILABLE_VM_COUNT_INVALID")
        available_vm_count = candidate_available_vm_count
    except VmCloneBatchExecutionError as error:
        outcome = "failed"
        failure_code = error.code
    except (VmCloneBatchError, OSError):
        outcome = "failed"
        failure_code = "batch_state_failed"

    duration = max(0, int(monotonic_clock() - started))
    try:
        frozen = freeze_vm_clone_batch(
            batch_id,
            outcome,
            duration,
            failure_code=failure_code,
            available_vm_count=available_vm_count,
            registry_path=registry_path,
        )
        sender = terminal_sender or (lambda item: _default_terminal_sender(config, item))
        message_id = str(sender(frozen) or "").strip()
        if not message_id:
            return 2
        record_vm_clone_batch_completion_delivery(
            batch_id, message_id, registry_path=registry_path
        )
    except Exception:  # noqa: BLE001 - the frozen result must not leak transport data.
        return 2
    return 0 if outcome == "success" else 1


def main() -> int:
    batch_id = str(os.getenv("VM_CLONE_BATCH_ID") or "").strip()
    if not batch_id:
        print("VM clone batch id is missing", file=sys.stderr)
        return 2
    try:
        from services.feishu_bot import load_config

        config = load_config()
    except Exception:
        print("VM clone batch configuration is unavailable", file=sys.stderr)
        return 2
    result = run_batch(batch_id, config)
    if result == 0:
        print("VM_CLONE_BATCH=completed")
    elif result == 1:
        print("VM_CLONE_BATCH=failed", file=sys.stderr)
    else:
        print("VM_CLONE_BATCH=delivery_or_state_failed", file=sys.stderr)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
