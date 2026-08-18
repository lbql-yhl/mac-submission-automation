"""Read host-local settings without mutating the process environment."""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Mapping
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT / ".env"


class ConfigurationError(RuntimeError):
    """Raised when a required host-only setting is unavailable or invalid."""


def _dotenv_setting(name: str, env_path: Path) -> str:
    path = Path(env_path)
    try:
        path_stat = path.lstat()
    except FileNotFoundError:
        return ""
    except OSError as error:
        raise ConfigurationError("unable to inspect host settings file") from error
    if not stat.S_ISREG(path_stat.st_mode):
        raise ConfigurationError("unsafe host settings file")

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ConfigurationError("unable to open host settings file safely") from error
    try:
        opened_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened_stat.st_mode)
            or opened_stat.st_dev != path_stat.st_dev
            or opened_stat.st_ino != path_stat.st_ino
        ):
            raise ConfigurationError("host settings file changed during secure open")
        with os.fdopen(descriptor, encoding="utf-8") as handle:
            descriptor = -1
            contents = handle.read()
    except (OSError, UnicodeError) as error:
        raise ConfigurationError("unable to read host settings file safely") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    for raw_line in contents.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != name:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return value.strip()
    return ""


def optional_setting(
    name: str,
    *,
    environ: Mapping[str, str] | None = None,
    env_path: Path = DEFAULT_ENV_PATH,
) -> str:
    """Return a stripped host setting without changing ``os.environ``."""
    if environ is not None:
        return str(environ.get(name, "")).strip()
    if name in os.environ:
        return str(os.environ.get(name, "")).strip()
    return _dotenv_setting(name, env_path)


def required_setting(
    name: str,
    *,
    environ: Mapping[str, str] | None = None,
    env_path: Path = DEFAULT_ENV_PATH,
) -> str:
    """Return a required setting or raise without revealing its value."""
    value = optional_setting(name, environ=environ, env_path=env_path)
    if not value:
        raise ConfigurationError(f"missing required host setting: {name}")
    return value


def guest_password(
    *,
    environ: Mapping[str, str] | None = None,
    env_path: Path = DEFAULT_ENV_PATH,
) -> str:
    """Return the host-configured macOS guest password at call time."""
    value = required_setting(
        "SUBMISSION_GUEST_PASSWORD", environ=environ, env_path=env_path
    )
    if re.fullmatch(r"[0-9]{4}", value) is None:
        raise ConfigurationError(
            "invalid host setting: SUBMISSION_GUEST_PASSWORD must be exactly "
            "four ASCII digits"
        )
    return value
