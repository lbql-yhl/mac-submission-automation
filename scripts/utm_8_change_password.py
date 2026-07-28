#!/usr/bin/env python3
"""Run the guest password-change helper and write back only after acceptance.

The candidate is generated and retained in this host process. It is sent to
the guest over SSH stdin, never placed in argv or output. Notion writeback is
performed only after the guest reports that Apple accepted the change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

PROJECT_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_SOURCE_ROOT))

from scripts.change_password_writeback import restore_previous_password
from scripts.notion_register_password import register_password
from scripts.notion_api import api_from_env
from services.project_paths import SSH_PRIVATE_KEY


CHANGE_FILES = (
    "apple_account_change_password.py",
    "find_system_settings_general.py",
    "mac_password_prompt.py",
)
PASSWORD_LENGTH = 16
PASSWORD_SUFFIX = "y"
SAFE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"


def generate_password(length: int = PASSWORD_LENGTH) -> str:
    """Generate the final Apple Account candidate (random base + literal ``y``).

    ``length`` is the random base length; the returned value is therefore one
    character longer and always ends with the required wake-up suffix.
    """
    if length < 8:
        raise ValueError("password length must be at least 8")
    while True:
        base = "".join(secrets.choice(SAFE_ALPHABET) for _ in range(length))
        if (
            any(char.isupper() for char in base)
            and any(char.islower() for char in base)
            and any(char.isdigit() for char in base)
        ):
            return base + PASSWORD_SUFFIX


def validate_final_candidate(candidate: str) -> str:
    """Reject anything that is not the complete random-base-plus-``y`` value."""
    if len(candidate) != PASSWORD_LENGTH + len(PASSWORD_SUFFIX):
        raise ValueError("candidate must be 16 random characters plus trailing y")
    if not candidate.endswith(PASSWORD_SUFFIX):
        raise ValueError("candidate must end with trailing y")
    return candidate


def _ssh_args(private_key: Path, user: str, ip: str) -> list[str]:
    return [
        "ssh",
        "-q",
        "-o",
        "BatchMode=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=8",
        "-i",
        str(private_key),
        f"{user}@{ip}",
    ]


def _scp_file(private_key: Path, user: str, ip: str, source: Path, target: str) -> None:
    subprocess.run(
        [
            "scp",
            "-q",
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "ConnectTimeout=8",
            "-i",
            str(private_key),
            str(source),
            f"{user}@{ip}:{target}",
        ],
        check=True,
    )


def _verify_remote_files(
    private_key: Path,
    user: str,
    ip: str,
    guest_dir: str,
    local_files: list[Path],
) -> None:
    remote_paths = [f"{guest_dir}/{path.name}" for path in local_files]
    result = subprocess.run(
        _ssh_args(private_key, user, ip) + ["shasum", "-a", "256", *remote_paths],
        check=True,
        capture_output=True,
        text=True,
    )
    expected = {hashlib.sha256(path.read_bytes()).hexdigest() for path in local_files}
    actual = {
        fields[0]
        for line in result.stdout.splitlines()
        if len(fields := line.split()) == 2
    }
    if actual != expected or len(actual) != len(local_files):
        raise RuntimeError("guest change-password helper hash verification failed")


def _verify_remote_compilation(
    private_key: Path,
    user: str,
    ip: str,
    guest_dir: str,
) -> None:
    remote_paths = [f"{guest_dir}/{name}" for name in CHANGE_FILES]
    subprocess.run(
        _ssh_args(private_key, user, ip) + ["python3", "-m", "py_compile", *remote_paths],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def _resolve_notion_context(args: argparse.Namespace) -> tuple[str, str]:
    """Resolve the host parent and the exact registration page from VM name."""
    vm_name = str(getattr(args, "vm_name", "")).strip()
    if not vm_name or not vm_name.isidentifier():
        raise RuntimeError("vm-name must be a simple VM name")
    parent_title = os.environ.get("SUBMISSION_HOST_MACHINE", "").strip()
    if not parent_title:
        raise RuntimeError("SUBMISSION_HOST_MACHINE is required for Notion matching")
    return parent_title, vm_name


def _read_current_password(api: object, page_title: str) -> str:
    """Read the effective current Apple password from the exact Notion page."""
    modified = api.read_field(page_title, "账号信息", "修改后的密码：").strip()  # type: ignore[attr-defined]
    if modified:
        return modified
    initial = api.read_field(page_title, "账号信息", "初始密码：").strip()  # type: ignore[attr-defined]
    if not initial:
        raise RuntimeError("Notion current Apple Account password is empty")
    return initial


def run(args: argparse.Namespace) -> int:
    private_key = Path(args.ssh_key).expanduser().resolve()
    if not private_key.is_file() or private_key.is_symlink():
        raise RuntimeError("SSH private key must be an existing regular file")
    if not args.vm_user.isidentifier():
        raise RuntimeError("vm-user must be a simple macOS account name")
    if not args.vm_ip or any(char not in "0123456789abcdefABCDEF:." for char in args.vm_ip):
        raise RuntimeError("vm-ip must be a literal IPv4/IPv6 address")

    parent_title, page_title = _resolve_notion_context(args)
    api = api_from_env()
    api.verify_parent(parent_title)
    previous_modified_password = api.read_field(
        page_title, "账号信息", "修改后的密码："
    ).strip()  # type: ignore[attr-defined]
    current_password = (
        previous_modified_password
        or api.read_field(page_title, "账号信息", "初始密码：").strip()  # type: ignore[attr-defined]
    )
    if not current_password:
        raise RuntimeError("Notion current Apple Account password is empty")
    source_dir = Path(args.source_dir).expanduser().resolve()
    local_files = [source_dir / name for name in CHANGE_FILES]
    if not all(path.is_file() and not path.is_symlink() for path in local_files):
        raise RuntimeError("change-password helper files are incomplete")

    guest_dir = args.guest_dir or f"/Users/{args.vm_user}/Downloads"
    subprocess.run(
        _ssh_args(private_key, args.vm_user, args.vm_ip) + ["mkdir", "-p", guest_dir],
        check=True,
    )
    for path in local_files:
        _scp_file(
            private_key,
            args.vm_user,
            args.vm_ip,
            path,
            f"{guest_dir}/{path.name}",
        )
    _verify_remote_files(private_key, args.vm_user, args.vm_ip, guest_dir, local_files)
    _verify_remote_compilation(private_key, args.vm_user, args.vm_ip, guest_dir)

    candidate = validate_final_candidate(generate_password())
    payload = b""
    try:
        # Persist first so the accepted candidate cannot be lost if the guest
        # process exits unexpectedly. Known guest failures restore the exact
        # preflight value before returning.
        metadata = register_password(api, parent_title, page_title, candidate)
        print("PASSWORD_NOTION_PREWRITE=verified")
        remote_script = f"{guest_dir}/apple_account_change_password.py"
        payload = json.dumps(
            {
                "APPLE_ACCOUNT_CURRENT_PASSWORD": current_password,
                "APPLE_ACCOUNT_NEW_PASSWORD": candidate,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        try:
            result = subprocess.run(
                _ssh_args(private_key, args.vm_user, args.vm_ip)
                + ["python3", "-B", remote_script, "--stdin-json"],
                input=payload,
                check=False,
            )
        except Exception:
            rollback = restore_previous_password(
                api, page_title, previous_modified_password
            )
            print(f"PASSWORD_ROLLBACK_BYTES={rollback['bytes']}")
            print(f"PASSWORD_ROLLBACK_SHA256={rollback['sha256']}")
            print("PASSWORD_NOTION_ROLLBACK=verified")
            raise
        if result.returncode != 0:
            rollback = restore_previous_password(
                api, page_title, previous_modified_password
            )
            print(f"PASSWORD_ROLLBACK_BYTES={rollback['bytes']}")
            print(f"PASSWORD_ROLLBACK_SHA256={rollback['sha256']}")
            print("PASSWORD_NOTION_ROLLBACK=verified")
            print("PASSWORD_CHANGE=blocked", file=sys.stderr)
            return result.returncode

        # The value was already written before the guest change; independently
        # verify the same page after Apple accepts it without writing again.
        api.verify_parent(parent_title)
        if api.read_field(page_title, "账号信息", "修改后的密码：").strip() != candidate:  # type: ignore[attr-defined]
            raise RuntimeError("Notion prewritten password readback mismatch")
        print(f"PASSWORD_WRITE_BYTES={metadata['bytes']}")
        print(f"PASSWORD_WRITE_SHA256={metadata['sha256']}")
        print("NOTION_PASSWORD_WRITE_RECOVERY=verified")
        print("PASSWORD_CHANGE=verified")
        print("MODIFIED_PASSWORD_NOTION=verified")
        return 0
    finally:
        current_password = ""
        candidate = ""
        payload = b""


def main() -> int:
    parser = argparse.ArgumentParser(description="Run UTM-8 Apple Account password change")
    parser.add_argument("--vm-name", required=True)
    parser.add_argument("--vm-ip", required=True)
    parser.add_argument("--vm-user", default="demo")
    parser.add_argument("--ssh-key", default=str(SSH_PRIVATE_KEY))
    parser.add_argument("--guest-dir", default="")
    parser.add_argument("--source-dir", default=str(Path.home() / "Downloads"))
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as error:
        print(f"UTM_8=blocked: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
