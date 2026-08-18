#!/usr/bin/env python3
"""Shared configured-password SSH/SCP command construction.

OpenSSH obtains the guest password from a one-use Unix-socket broker through a
mode-700 SSH_ASKPASS helper.  The child receives only a socket path and random
capability, leaving stdin available for remote scripts and sudo input without
placing the password in its environment.  Public-key authentication is
explicitly disabled for every connection.
"""

from __future__ import annotations

import os
import secrets
import socket
import stat
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Mapping

from services.host_config import guest_password


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "ssh-password"
_ASKPASS_SCRIPT = (
    "#!/usr/bin/env python3\n"
    "import os\n"
    "import socket\n"
    "import sys\n"
    "path = os.environ.pop('SUBMISSION_SSH_ASKPASS_SOCKET', '')\n"
    "capability = os.environ.pop('SUBMISSION_SSH_ASKPASS_CAPABILITY', '')\n"
    "if not path or not capability:\n"
    "    raise SystemExit(1)\n"
    "response = bytearray()\n"
    "with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:\n"
    "    client.settimeout(10)\n"
    "    client.connect(path)\n"
    "    client.sendall(capability.encode('ascii') + b'\\n')\n"
    "    while len(response) <= 64:\n"
    "        chunk = client.recv(64 - len(response))\n"
    "        if not chunk:\n"
    "            break\n"
    "        response.extend(chunk)\n"
    "if not response or len(response) > 64:\n"
    "    raise SystemExit(1)\n"
    "os.write(sys.stdout.fileno(), bytes(response) + b'\\n')\n"
)
_BROKER_TIMEOUT_SECONDS = 30.0
_SOCKET_ENV = "SUBMISSION_SSH_ASKPASS_SOCKET"
_CAPABILITY_ENV = "SUBMISSION_SSH_ASKPASS_CAPABILITY"
_UNIX_SOCKET_PATH_LIMIT = 100


class SSHPasswordError(RuntimeError):
    """Raised when the local password-authentication channel is unsafe."""


def _secure_runtime_dir(path: Path) -> Path:
    path = Path(path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    try:
        path_stat = path.lstat()
    except FileNotFoundError:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            path_stat = path.lstat()
        except OSError as error:
            raise SSHPasswordError("SSH password runtime directory is unsafe") from error
    except OSError as error:
        raise SSHPasswordError("SSH password runtime directory is unsafe") from error
    if not stat.S_ISDIR(path_stat.st_mode):
        raise SSHPasswordError("SSH password runtime directory is unsafe")

    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
        try:
            opened_stat = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(opened_stat.st_mode)
                or opened_stat.st_dev != path_stat.st_dev
                or opened_stat.st_ino != path_stat.st_ino
            ):
                raise SSHPasswordError("SSH password runtime directory changed")
            os.fchmod(descriptor, 0o700)
        finally:
            os.close(descriptor)
    except OSError as error:
        raise SSHPasswordError("SSH password runtime directory is unsafe") from error
    return path


def _askpass_helper(runtime_dir: Path) -> Path:
    directory = _secure_runtime_dir(runtime_dir)
    helper = directory / "askpass"
    existing_source: str | None = None
    try:
        helper_stat = helper.lstat()
    except FileNotFoundError:
        helper_stat = None
    except OSError as error:
        raise SSHPasswordError("SSH_ASKPASS helper is unsafe") from error
    if helper_stat is not None:
        if not stat.S_ISREG(helper_stat.st_mode):
            raise SSHPasswordError("SSH_ASKPASS helper is unsafe")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(helper, flags)
            try:
                opened_stat = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(opened_stat.st_mode)
                    or opened_stat.st_dev != helper_stat.st_dev
                    or opened_stat.st_ino != helper_stat.st_ino
                ):
                    raise SSHPasswordError("SSH_ASKPASS helper changed")
                with os.fdopen(descriptor, encoding="utf-8") as handle:
                    descriptor = -1
                    existing_source = handle.read()
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
        except (OSError, UnicodeError) as error:
            raise SSHPasswordError("SSH_ASKPASS helper is unsafe") from error
    if existing_source != _ASKPASS_SCRIPT:
        temporary = directory / f".askpass-{uuid.uuid4().hex}.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(_ASKPASS_SCRIPT)
                handle.flush()
                os.fsync(handle.fileno())
                os.fchmod(handle.fileno(), 0o700)
            os.replace(temporary, helper)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
    else:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(helper, flags)
        try:
            os.fchmod(descriptor, 0o700)
        finally:
            os.close(descriptor)
    return helper


def _socket_directory(runtime_dir: Path) -> Path:
    candidate = runtime_dir / f".b-{secrets.token_hex(8)}"
    if len(os.fsencode(candidate)) < _UNIX_SOCKET_PATH_LIMIT:
        return runtime_dir
    short_root = Path(tempfile.gettempdir()) / f"submission-ssh-{os.getuid()}"
    return _secure_runtime_dir(short_root)


def _unlink_owned_socket(path: Path, identity: tuple[int, int]) -> None:
    try:
        path_stat = path.lstat()
    except FileNotFoundError:
        return
    if (
        stat.S_ISSOCK(path_stat.st_mode)
        and (path_stat.st_dev, path_stat.st_ino) == identity
    ):
        path.unlink()


def _start_password_broker(runtime_dir: Path, configured_password: str) -> tuple[Path, str]:
    directory = _socket_directory(runtime_dir)
    capability = secrets.token_urlsafe(32)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    socket_path = directory / f".b-{secrets.token_hex(8)}"
    try:
        server.bind(str(socket_path))
        socket_stat = socket_path.lstat()
        identity = (socket_stat.st_dev, socket_stat.st_ino)
        server.listen(1)
        server.settimeout(_BROKER_TIMEOUT_SECONDS)
    except Exception:
        server.close()
        try:
            socket_path.unlink()
        except FileNotFoundError:
            pass
        raise

    def serve_once() -> None:
        try:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(_BROKER_TIMEOUT_SECONDS)
                request = bytearray()
                while len(request) <= 256 and b"\n" not in request:
                    chunk = connection.recv(257 - len(request))
                    if not chunk:
                        break
                    request.extend(chunk)
                supplied = bytes(request).partition(b"\n")[0]
                expected = capability.encode("ascii")
                if len(request) <= 256 and secrets.compare_digest(supplied, expected):
                    connection.sendall(configured_password.encode("utf-8"))
        except (OSError, TimeoutError):
            pass
        finally:
            server.close()
            _unlink_owned_socket(socket_path, identity)

    threading.Thread(target=serve_once, name="ssh-password-broker", daemon=True).start()
    return socket_path, capability


def password_environment(
    base: Mapping[str, str] | None = None, *, runtime_dir: Path = DEFAULT_RUNTIME_DIR
) -> dict[str, str]:
    """Return an environment that forces one configured-password prompt."""
    env = dict(os.environ if base is None else base)
    configured_password = guest_password(environ=base) if base is not None else guest_password()
    helper = _askpass_helper(runtime_dir)
    socket_path, capability = _start_password_broker(
        _secure_runtime_dir(runtime_dir), configured_password
    )
    env.pop("SUBMISSION_GUEST_PASSWORD", None)
    env.update(
        {
            "SSH_ASKPASS": str(helper),
            "SSH_ASKPASS_REQUIRE": "force",
            "DISPLAY": env.get("DISPLAY") or "submission-ssh:0",
            _SOCKET_ENV: str(socket_path),
            _CAPABILITY_ENV: capability,
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
