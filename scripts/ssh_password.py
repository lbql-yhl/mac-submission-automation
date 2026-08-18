#!/usr/bin/env python3
"""Shared configured-password SSH/SCP command construction.

OpenSSH obtains the guest password through a mode-700 SSH_ASKPASS
helper, leaving stdin available for remote scripts and sudo input.  Public-key
authentication is explicitly disabled for every connection.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Mapping

from services.host_config import guest_password


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "ssh-password"
_ASKPASS_SCRIPT = (
    "#!/bin/sh\n"
    "exec /usr/bin/printf '%s\\n' \"$SUBMISSION_GUEST_PASSWORD\"\n"
)


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
    helper = directory / "askpass"
    if helper.exists() and (helper.is_symlink() or not helper.is_file()):
        raise SSHPasswordError(f"SSH_ASKPASS helper is unsafe: {helper}")
    if not helper.exists() or helper.read_text(encoding="utf-8") != _ASKPASS_SCRIPT:
        temporary = directory / f".askpass-{uuid.uuid4().hex}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(_ASKPASS_SCRIPT)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.chmod(0o700)
            os.replace(temporary, helper)
        finally:
            if temporary.exists():
                temporary.unlink()
    helper.chmod(0o700)
    return helper


def password_environment(
    base: Mapping[str, str] | None = None, *, runtime_dir: Path = DEFAULT_RUNTIME_DIR
) -> dict[str, str]:
    """Return an environment that forces one configured-password prompt."""
    env = dict(os.environ if base is None else base)
    configured_password = (
        guest_password(environ=base)
        if base is not None and "SUBMISSION_GUEST_PASSWORD" in base
        else guest_password()
    )
    env.update(
        {
            "SSH_ASKPASS": str(_askpass_helper(runtime_dir)),
            "SSH_ASKPASS_REQUIRE": "force",
            "DISPLAY": env.get("DISPLAY") or "submission-ssh:0",
            "SUBMISSION_GUEST_PASSWORD": configured_password,
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
