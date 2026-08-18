"""Read host-local settings without mutating the process environment."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT / ".env"


class ConfigurationError(RuntimeError):
    """Raised when a required host-only setting is unavailable or invalid."""


def _dotenv_setting(name: str, env_path: Path) -> str:
    path = Path(env_path)
    if not path.is_file():
        return ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
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
