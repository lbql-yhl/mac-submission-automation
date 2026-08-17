#!/usr/bin/env python3
"""Shared fixed-password SSH/SCP command construction.

OpenSSH obtains the fixed guest password through a mode-700 SSH_ASKPASS
helper, leaving stdin available for remote scripts and sudo input.  Public-key
authentication is explicitly disabled for every connection.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXED_PASSWORD = "1234"
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "ssh-password"
_ASKPASS_BODY = "#!/bin/sh\nexec /usr/bin/printf '1234\\n'\n"


class SSHPasswordError(RuntimeError):
    """Raised when the local password-authentication channel is unsafe."""


def _secure_runtime_dir(path: Path) -> Path:
    path = Path(path).expanduser().resolve()
    if path.exists() and (path.is_symlink() or not path.is_dir()):
        raise SSHPasswordError(f"SSH password runtime directory is unsafe: {path}")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def _askpass_helper(runtime_dir: Path) -> Path:
    directory = _secure_runtime_dir(runtime_dir)
    helper = directory / "askpass-1234"
    if helper.exists() and (helper.is_symlink() or not helper.is_file()):
        raise SSHPasswordError(f"SSH_ASKPASS helper is unsafe: {helper}")
    if not helper.exists() or helper.read_text(encoding="utf-8") != _ASKPASS_BODY:
        temporary = directory / f".askpass-{uuid.uuid4().hex}.tmp"
        temporary.write_text(_ASKPASS_BODY, encoding="utf-8")
        temporary.chmod(0o700)
        os.replace(temporary, helper)
    helper.chmod(0o700)
    return helper


def password_environment(
    base: Mapping[str, str] | None = None, *, runtime_dir: Path = DEFAULT_RUNTIME_DIR
) -> dict[str, str]:
    """Return an environment that forces one fixed-password prompt."""
    env = dict(os.environ if base is None else base)
    env.update(
        {
            "SSH_ASKPASS": str(_askpass_helper(runtime_dir)),
            "SSH_ASKPASS_REQUIRE": "force",
            "DISPLAY": env.get("DISPLAY") or "submission-ssh:0",
        }
    )
    return env


def connection_options(connect_timeout: int = 5) -> list[str]:
    if connect_timeout <= 0:
        raise ValueError("connect timeout must be positive")
    return [
        "-o", "BatchMode=no",
        "-o", "PreferredAuthentications=password,keyboard-interactive",
        "-o", "PubkeyAuthentication=no",
        "-o", "KbdInteractiveAuthentication=yes",
        "-o", "NumberOfPasswordPrompts=1",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"ConnectTimeout={connect_timeout}",
    ]


def ssh_args(user: str, ip: str, *, connect_timeout: int = 5, tty: bool = False) -> list[str]:
    if not user or not ip:
        raise ValueError("SSH user and IP are required")
    command = ["/usr/bin/ssh"]
    if tty:
        command.append("-tt")
    command.extend(["-q", *connection_options(connect_timeout), f"{user}@{ip}"])
    return command


def scp_args(
    user: str,
    ip: str,
    source: Path | str,
    target: str,
    *,
    connect_timeout: int = 8,
) -> list[str]:
    if not target:
        raise ValueError("SCP target is required")
    return [
        "/usr/bin/scp", "-q", *connection_options(connect_timeout),
        str(source), f"{user}@{ip}:{target}",
    ]
