#!/usr/bin/env python3
"""Read-only portability and run-readiness checks."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.project_paths import (  # noqa: E402
    PROJECT_ROOT,
    PROJECT_SKILLS_DIR,
    SHARED_DIR,
    SSH_PRIVATE_KEY,
    SSH_PUBLIC_KEY,
    VM_IMAGES_DIR,
    VM_TEMPLATE,
)


ORDERED = (
    "notion-utm", "notion-utm-1", "utm-clone-macos", "utm-1", "utm-2", "utm-3",
    "vm-down", "utm-4", "utm-5", "files", "utm-clash", "utm-6", "utm-7", "utm-8",
    "utm-9", "utm-10", "utm-11", "utm-12", "utm-13", "utm-14", "utm-15", "utm-16",
    "utm-17", "utm-18", "utm-19", "utm-20", "utm-21", "utm-22", "utm-23", "utm-24", "utm-25",
)


def executable_exists(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts:
        return False
    executable = Path(os.path.expanduser(parts[0]))
    if executable.parent != Path("."):
        if not executable.is_absolute():
            executable = ROOT / executable
        return executable.is_file() and os.access(executable, os.X_OK)
    return shutil.which(parts[0]) is not None


def runner_command_valid(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    if not parts or not executable_exists(parts[0]):
        return False
    for item in parts[1:]:
        if item.startswith("-"):
            continue
        candidate = Path(os.path.expanduser(item))
        if candidate.suffix in {".py", ".sh", ".zsh"}:
            if not candidate.is_absolute():
                candidate = ROOT / candidate
            return candidate.is_file()
    return True


def check(project_only: bool) -> dict[str, object]:
    discovered = {
        path.parent.name for path in PROJECT_SKILLS_DIR.glob("*/SKILL.md")
    }
    codex_command = os.getenv("FEISHU_CODEX_COMMAND", "codex").strip()
    runner_command = os.getenv(
        "SUBMISSION_RUNNER_COMMAND", "python3 services/submission_runner.py"
    ).strip()
    checks: dict[str, object] = {
        "project_root": PROJECT_ROOT == ROOT and (ROOT / "README.md").is_file(),
        "skills_count": sum((PROJECT_SKILLS_DIR / name / "SKILL.md").is_file() for name in ORDERED),
        "skill_set_exact": discovered == set(ORDERED),
        "skill_names_unique": len(ORDERED) == len(set(ORDERED)) == 31,
        "shared_contract": (PROJECT_SKILLS_DIR / "_shared" / "AUTOMATION_CONTRACT.md").is_file(),
        "python3": shutil.which("python3") is not None,
        "codex": executable_exists(codex_command),
        "runner_enabled": runner_command_valid(runner_command),
    }
    if not project_only:
        checks.update(
            {
                "vm_images_dir": VM_IMAGES_DIR.is_dir(),
                "vm_template": VM_TEMPLATE.is_dir(),
                "shared_dir": SHARED_DIR.is_dir(),
                "ssh_private_key_parent": SSH_PRIVATE_KEY.parent.is_dir(),
                "ssh_public_key_parent": SSH_PUBLIC_KEY.parent.is_dir(),
                "submission_host_machine": bool(os.getenv("SUBMISSION_HOST_MACHINE", "").strip()),
                "feishu_app_id": bool(os.getenv("FEISHU_APP_ID", "").strip()),
                "feishu_app_secret": bool(os.getenv("FEISHU_APP_SECRET", "").strip()),
                "notion_token": bool(os.getenv("NOTION_TOKEN", "").strip()),
                "notion_root_page_id": bool(os.getenv("NOTION_ROOT_PAGE_ID", "").strip()),
                "codeup_username": bool(os.getenv("CODEUP_USERNAME", "").strip()),
                "codeup_password": bool(os.getenv("CODEUP_PASSWORD", "").strip()),
                "ssh": shutil.which("ssh") is not None,
                "ssh_keygen": shutil.which("ssh-keygen") is not None,
                "git": shutil.which("git") is not None,
                "node": shutil.which("node") is not None,
                "npm": shutil.which("npm") is not None,
                "pbcopy": shutil.which("pbcopy") is not None,
                "pbpaste": shutil.which("pbpaste") is not None,
            }
        )
    checks["ok"] = all(
        value == 31 if key == "skills_count" else bool(value)
        for key, value in checks.items()
        if key != "ok"
    )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--emit-shell", action="store_true")
    args = parser.parse_args()
    result = check(args.project_only)
    if args.emit_shell:
        if not result["ok"]:
            return 1
        values = {
            "PROJECT_ROOT": PROJECT_ROOT,
            "PROJECT_SKILLS_DIR": PROJECT_SKILLS_DIR,
            "SUBMISSION_VM_IMAGES_DIR": VM_IMAGES_DIR,
            "SUBMISSION_VM_TEMPLATE": VM_TEMPLATE,
            "SUBMISSION_SHARED_DIR": SHARED_DIR,
            "SUBMISSION_SSH_PRIVATE_KEY": SSH_PRIVATE_KEY,
            "SUBMISSION_SSH_PUBLIC_KEY": SSH_PUBLIC_KEY,
        }
        for key, value in values.items():
            print(f"export {key}={shlex.quote(str(value))}")
    elif args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key.upper()}={value}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
