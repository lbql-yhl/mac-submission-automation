#!/usr/bin/env python3
"""Clone one UTM VM and initialize that exact clone in the same process tree."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.clean_cli import emit_progress, run_clean_cli
from scripts.vm_inventory import InventoryError, get_record
PYTHON = Path(sys.executable).absolute()
CLONE_SCRIPT = (PROJECT_ROOT / "scripts" / "utm_vm_clone_step_01_clone.py").resolve()
POST_CLONE_SCRIPT = (PROJECT_ROOT / "scripts" / "utm_post_clone.py").resolve()
DATABASE = (PROJECT_ROOT / "runtime" / "vm-inventory.sqlite3").resolve()
ACTIVE_WORKFLOW_PATH = (PROJECT_ROOT / "runtime" / "utm-vm-clone-active.json").resolve()
VM_NAME_RE = re.compile(r"^[a-z]{4}$")
SAFE_BLOCKED_REASON_RE = re.compile(
    r"(?m)^[A-Z][A-Z0-9_]*=blocked:\s*([A-Z][A-Z0-9_:=.,;|/ -]{0,319})$"
)
REQUIRED_CLONE_MARKER = "STEP_01_CLONE=verified"
VERIFIED_CLONE_RESULT_RE = re.compile(
    r"执行成功：utm-vm-clone-step-01；"
    r"STEP_01_CLONE=verified;VM_NAME=([a-z]{4})"
)


class CloneInitializeError(RuntimeError):
    """Raised when clone output cannot be safely handed to initialization."""


def _inventory_record(vm_name: str) -> dict[str, object]:
    if not VM_NAME_RE.fullmatch(vm_name):
        raise CloneInitializeError("ACTIVE_VM_NAME_INVALID")
    return get_record(DATABASE, vm_name)


def _active_inventory_record(vm_name: str) -> dict[str, object]:
    record = _inventory_record(vm_name)
    bundle = Path(str(record.get("bundle_path") or "")).expanduser().resolve()
    if (
        record.get("status") != "complete"
        or int(record.get("available") or 0) != 0
        or int(record.get("reusable") or 0) != 0
        or record.get("application_name") is not None
        or not str(record.get("config_uuid") or "")
        or bundle.is_symlink()
        or not bundle.is_dir()
        or not (bundle / "config.plist").is_file()
    ):
        raise CloneInitializeError("ACTIVE_VM_INVENTORY_MISMATCH")
    return record


def load_active_workflow() -> dict[str, str] | None:
    if not ACTIVE_WORKFLOW_PATH.exists():
        return None
    if ACTIVE_WORKFLOW_PATH.is_symlink() or not ACTIVE_WORKFLOW_PATH.is_file():
        raise CloneInitializeError("ACTIVE_WORKFLOW_PATH_INVALID")
    try:
        value = json.loads(ACTIVE_WORKFLOW_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CloneInitializeError("ACTIVE_WORKFLOW_INVALID") from error
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise CloneInitializeError("ACTIVE_WORKFLOW_INVALID")
    vm_name = str(value.get("vm_name") or "")
    record = _inventory_record(vm_name)
    if record.get("application_name") is not None:
        clear_active_workflow()
        return None
    if (
        record.get("status") == "complete"
        and int(record.get("available") or 0) == 1
        and int(record.get("directory_present") or 0) == 1
        and int(record.get("reusable") or 0) == 0
        and record.get("application_name") is None
    ):
        clear_active_workflow()
        return None
    record = _active_inventory_record(vm_name)
    expected = {
        "schema_version": 1,
        "vm_name": vm_name,
        "config_uuid": str(record.get("config_uuid") or "").upper(),
        "bundle_path": str(Path(str(record.get("bundle_path") or "")).expanduser().resolve()),
    }
    if value != expected:
        raise CloneInitializeError("ACTIVE_WORKFLOW_IDENTITY_MISMATCH")
    return {key: str(item) for key, item in expected.items() if key != "schema_version"}


def write_active_workflow(record: dict[str, object]) -> None:
    vm_name = str(record.get("vm_name") or "")
    inventory = _active_inventory_record(vm_name)
    payload = {
        "schema_version": 1,
        "vm_name": vm_name,
        "config_uuid": str(inventory.get("config_uuid") or "").upper(),
        "bundle_path": str(Path(str(inventory.get("bundle_path") or "")).expanduser().resolve()),
    }
    ACTIVE_WORKFLOW_PATH.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{ACTIVE_WORKFLOW_PATH.name}.", dir=ACTIVE_WORKFLOW_PATH.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, ACTIVE_WORKFLOW_PATH)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def clear_active_workflow() -> None:
    if ACTIVE_WORKFLOW_PATH.exists():
        ACTIVE_WORKFLOW_PATH.unlink()


def verify_completed_inventory(vm_name: str) -> None:
    record = get_record(DATABASE, vm_name)
    bundle = Path(str(record.get("bundle_path") or "")).expanduser().resolve()
    if (
        record.get("status") != "complete"
        or int(record.get("available") or 0) != 1
        or int(record.get("directory_present") or 0) != 1
        or int(record.get("reusable") or 0) != 0
        or record.get("application_name") is not None
        or bundle.is_symlink()
        or not bundle.is_dir()
    ):
        raise CloneInitializeError("FINAL_INVENTORY_NOT_AVAILABLE")


def parse_verified_clone_vm_name(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    result_lines = [
        line
        for line in lines
        if line.startswith("执行成功：utm-vm-clone-step-01；")
    ]
    match = (
        VERIFIED_CLONE_RESULT_RE.fullmatch(result_lines[0])
        if len(result_lines) == 1
        else None
    )
    if match is None:
        raise CloneInitializeError(f"CLONE_VERIFICATION_MISSING={REQUIRED_CLONE_MARKER}")
    return match.group(1)


def child_blocked_reason(result: subprocess.CompletedProcess[str]) -> str:
    detail = result.stderr or result.stdout or ""
    reasons = SAFE_BLOCKED_REASON_RE.findall(detail)
    if reasons:
        return reasons[-1]
    return "CHILD_ENTRY_FAILED"


def run_workflow(
    *, on_verified_vm_name: Callable[[str], None] | None = None
) -> int:
    # Never let a value inherited from an earlier shell/workflow select a VM.
    # The only accepted value is the unique name from this clone invocation.
    os.environ.pop("VM_NAME", None)
    try:
        active = load_active_workflow()
    except CloneInitializeError as error:
        print(f"UTM_CLONE_AND_INITIALIZE=blocked: {error}", file=sys.stderr)
        return 1
    except InventoryError:
        print(
            "UTM_CLONE_AND_INITIALIZE=blocked: "
            "ACTIVE_WORKFLOW_INVENTORY_FAILED",
            file=sys.stderr,
        )
        return 1
    except OSError:
        print(
            "UTM_CLONE_AND_INITIALIZE=blocked: ACTIVE_WORKFLOW_IO_FAILED",
            file=sys.stderr,
        )
        return 1
    if active is not None:
        vm_name = active["vm_name"]
    else:
        clone_command = [str(PYTHON), str(CLONE_SCRIPT)]
        clone_result = subprocess.run(
            clone_command,
            text=True,
            capture_output=True,
            check=False,
        )
        if clone_result.returncode != 0:
            reason = child_blocked_reason(clone_result)
            print(
                f"UTM_CLONE_AND_INITIALIZE=blocked: CLONE_FAILED:{reason}",
                file=sys.stderr,
            )
            return 1

        try:
            vm_name = parse_verified_clone_vm_name(clone_result.stdout)
            progress = [
                line.strip()
                for line in clone_result.stdout.splitlines()
                if line.strip() == "步骤1已操作"
            ]
            if len(progress) != 1:
                raise CloneInitializeError("STEP_ACTION_OUTPUT_INVALID=1")
            emit_progress(progress[0])
            write_active_workflow({"vm_name": vm_name})
        except CloneInitializeError as error:
            print(f"UTM_CLONE_AND_INITIALIZE=blocked: {error}", file=sys.stderr)
            return 1
    if active is not None:
        emit_progress("步骤1已完成，跳过")

    try:
        binding_record = _active_inventory_record(vm_name)
    except CloneInitializeError as error:
        print(f"UTM_CLONE_AND_INITIALIZE=blocked: {error}", file=sys.stderr)
        return 1
    bundle_parent = Path(
        str(binding_record.get("bundle_path") or "")
    ).expanduser().resolve().parent
    os.environ["VM_NAME"] = vm_name
    child_environment = os.environ.copy()
    child_environment["SUBMISSION_VM_IMAGES_DIR"] = str(bundle_parent)
    child_environment["SUBMISSION_VM_IMAGES_DIRS"] = json.dumps(
        [str(bundle_parent)], ensure_ascii=False
    )

    initialize_command = [
        str(PYTHON),
        str(POST_CLONE_SCRIPT),
    ]
    initialize_result = subprocess.run(
        initialize_command,
        env=child_environment,
        text=True,
        capture_output=True,
        check=False,
    )
    for line in (initialize_result.stdout or "").splitlines():
        if re.fullmatch(r"步骤(?:[1-9]|10)(?:已操作|已完成，跳过)", line.strip()):
            emit_progress(line.strip())
    if initialize_result.returncode != 0:
        reason = child_blocked_reason(initialize_result)
        print(
            f"UTM_CLONE_AND_INITIALIZE=blocked: INITIALIZE_FAILED:{reason}",
            file=sys.stderr,
        )
        return 1
    try:
        verify_completed_inventory(vm_name)
        if on_verified_vm_name is not None:
            on_verified_vm_name(vm_name)
        try:
            clear_active_workflow()
        except OSError:
            # The verified inventory is authoritative; cleanup cannot erase
            # the VM name from this completed result.
            pass
    except CloneInitializeError as error:
        print(f"UTM_CLONE_AND_INITIALIZE=blocked: {error}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Clone one UTM VM and initialize that exact clone"
    )
    parser.parse_args(argv)
    verified_vm_names: list[str] = []

    def success_marker() -> str:
        if len(verified_vm_names) != 1 or not VM_NAME_RE.fullmatch(
            verified_vm_names[0]
        ):
            raise CloneInitializeError("FINAL_VM_NAME_OUTPUT_INVALID")
        return (
            "UTM_CLONE_AND_INITIALIZE=verified;"
            f"VM_NAME={verified_vm_names[0]}"
        )

    return run_clean_cli(
        skill_name="utm-vm-clone",
        success_marker=success_marker,
        operation=lambda: run_workflow(
            on_verified_vm_name=verified_vm_names.append
        ),
        progress_pattern=(
            r"步骤(?:[1-9]|10)(?:已操作|已完成，跳过)"
        ),
        preserve_error_detail=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
