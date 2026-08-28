"""Process-wide singleton lock for the Feishu supervisor."""

from __future__ import annotations

import errno
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class SupervisorLockError(RuntimeError):
    """The supervisor cannot establish a safe singleton lock."""


class SupervisorAlreadyRunning(SupervisorLockError):
    """Another supervisor currently owns the singleton lock."""


def _open_private_regular_file(path: Path) -> int:
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW"):
        raise SupervisorLockError("supervisor singleton lock is not supported")

    flags = os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as error:
        raise SupervisorLockError("unable to open supervisor singleton lock") from error

    try:
        opened = os.fstat(descriptor)
        current = path.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_dev != current.st_dev
            or opened.st_ino != current.st_ino
        ):
            raise SupervisorLockError("unsafe supervisor singleton lock")
        os.fchmod(descriptor, 0o600)
        if stat.S_IMODE(os.fstat(descriptor).st_mode) != 0o600:
            raise SupervisorLockError("unsafe supervisor singleton lock permissions")
    except SupervisorLockError:
        os.close(descriptor)
        raise
    except OSError as error:
        os.close(descriptor)
        raise SupervisorLockError("unable to verify supervisor singleton lock") from error
    return descriptor


def _verify_locked_path(descriptor: int, path: Path) -> None:
    try:
        opened = os.fstat(descriptor)
        current = path.lstat()
    except OSError as error:
        raise SupervisorLockError("unable to verify locked supervisor path") from error
    if (
        not stat.S_ISREG(opened.st_mode)
        or opened.st_nlink != 1
        or opened.st_dev != current.st_dev
        or opened.st_ino != current.st_ino
        or stat.S_IMODE(opened.st_mode) != 0o600
    ):
        raise SupervisorLockError("unsafe locked supervisor path")


@contextmanager
def supervisor_lock(path: Path) -> Iterator[int]:
    """Hold an exclusive nonblocking lock until the caller leaves the context."""
    if os.name != "posix":
        raise SupervisorLockError("supervisor singleton lock is not supported")
    try:
        import fcntl
    except ImportError as error:
        raise SupervisorLockError("supervisor singleton lock is not supported") from error

    target = Path(path)
    descriptor = _open_private_regular_file(target)
    locked = False
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EAGAIN}:
                raise SupervisorAlreadyRunning(
                    "feishu supervisor is already running"
                ) from error
            raise SupervisorLockError(
                "unable to acquire supervisor singleton lock"
            ) from error
        locked = True
        _verify_locked_path(descriptor, target)
        yield descriptor
    finally:
        if locked:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(descriptor)
