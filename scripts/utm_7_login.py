#!/usr/bin/env python3
"""Run the project-owned Apple Account login helper with live Notion fields.

Secrets are read through the Notion API, sent to the guest only through SSH
stdin as JSON, and never placed in argv, logs, or a temporary plaintext file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

# When invoked as ``python3 scripts/utm_7_login.py`` Python puts only the
# scripts directory on ``sys.path``.  Add the project root before importing
# the shared ``scripts`` and ``services`` packages so the documented entry
# point works from any current working directory.
PROJECT_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_SOURCE_ROOT))

from scripts.notion_api import api_from_env
from services.project_paths import PROJECT_ROOT, SSH_PRIVATE_KEY


LOGIN_FILES = (
    "apple_account_login.py",
    "find_system_settings_general.py",
    "apple_account_post_login.py",
    "mac_password_prompt.py",
)


def _read_field(api, page_title: str, label: str) -> str:
    value = api.read_field(page_title, "账号信息", label).strip()
    if not value:
        raise RuntimeError(f"Notion field {label!r} is empty")
    return value


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
    command = [
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
    ]
    subprocess.run(command, check=True)


def _verify_remote_hashes(
    private_key: Path,
    user: str,
    ip: str,
    guest_dir: str,
    local_files: list[Path],
) -> None:
    remote_paths = [f"{guest_dir}/{name}" for name in LOGIN_FILES]
    result = subprocess.run(
        _ssh_args(private_key, user, ip)
        + ["shasum", "-a", "256", *remote_paths],
        check=True,
        capture_output=True,
        text=True,
    )
    expected = {
        hashlib.sha256(path.read_bytes()).hexdigest() for path in local_files
    }
    actual = set()
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) == 2:
            actual.add(fields[0])
    if actual != expected or len(actual) != len(LOGIN_FILES):
        raise RuntimeError("guest login helper hash verification failed")


def _verify_remote_compilation(
    private_key: Path,
    user: str,
    ip: str,
    guest_dir: str,
) -> None:
    """Compile the uploaded helpers in the guest before any login side effect."""
    remote_paths = [f"{guest_dir}/{name}" for name in LOGIN_FILES]
    subprocess.run(
        _ssh_args(private_key, user, ip)
        + ["python3", "-m", "py_compile", *remote_paths],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def run(args: argparse.Namespace) -> int:
    private_key = Path(args.ssh_key).expanduser().resolve()
    if not private_key.is_file() or private_key.is_symlink():
        raise RuntimeError("SSH private key must be an existing regular file")
    if not args.vm_user.isidentifier():
        raise RuntimeError("vm-user must be a simple macOS account name")
    if not args.vm_ip or any(char not in "0123456789abcdefABCDEF:." for char in args.vm_ip):
        raise RuntimeError("vm-ip must be a literal IPv4/IPv6 address")

    api = api_from_env()
    api.verify_parent(args.parent_title)
    email = _read_field(api, args.page_title, "邮箱：")
    password = api.read_field(args.page_title, "账号信息", "修改后的密码：").strip()
    if not password:
        password = _read_field(api, args.page_title, "初始密码：")
    phone = _read_field(api, args.page_title, "电话：")
    sms_url = _read_field(api, args.page_title, "电话短信接收平台：")
    parsed_sms = urlparse(sms_url)
    if parsed_sms.scheme not in {"http", "https"} or not parsed_sms.netloc:
        raise RuntimeError("Notion SMS URL is not a valid http(s) URL")

    source_dir = PROJECT_ROOT / "scripts"
    local_files = [source_dir / name for name in LOGIN_FILES]
    if not all(path.is_file() for path in local_files):
        raise RuntimeError("project login helper files are incomplete")
    guest_dir = args.guest_dir or f"/Users/{args.vm_user}/Downloads"
    subprocess.run(
        _ssh_args(private_key, args.vm_user, args.vm_ip)
        + ["mkdir", "-p", guest_dir],
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
    _verify_remote_hashes(
        private_key,
        args.vm_user,
        args.vm_ip,
        guest_dir,
        local_files,
    )
    _verify_remote_compilation(
        private_key,
        args.vm_user,
        args.vm_ip,
        guest_dir,
    )

    payload = {
        "APPLE_ACCOUNT_EMAIL": email,
        "APPLE_ACCOUNT_PASSWORD": password,
        "APPLE_ACCOUNT_PHONE": phone,
        "APPLE_ACCOUNT_SMS_URL": sms_url,
    }
    remote_script = f"{guest_dir}/apple_account_login.py"
    result = subprocess.run(
        _ssh_args(private_key, args.vm_user, args.vm_ip)
        + ["python3", "-B", remote_script, "--stdin-json"],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        check=False,
    )
    if result.returncode != 0:
        print("APPLE_ACCOUNT=blocked", file=sys.stderr)
        return result.returncode
    print("APPLE_ACCOUNT=verified")
    print("UTM_7=verified")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run UTM-7 Apple Account login")
    parser.add_argument("--parent-title", required=True)
    parser.add_argument("--page-title", required=True)
    parser.add_argument("--vm-ip", required=True)
    parser.add_argument("--vm-user", required=True)
    parser.add_argument("--ssh-key", default=str(SSH_PRIVATE_KEY))
    parser.add_argument("--guest-dir", default="")
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as error:
        print(f"UTM_7=blocked: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
