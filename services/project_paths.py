"""Portable path resolution for the submission workflow."""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from services.host_config import ConfigurationError, optional_setting
except ModuleNotFoundError:  # Support direct ``python services/feishu_bot.py`` use.
    from host_config import ConfigurationError, optional_setting


SOURCE_ROOT = Path(__file__).resolve().parents[1]


def configured_path(name: str, default: Path) -> Path:
    raw = optional_setting(name, env_path=SOURCE_ROOT / ".env")
    if not raw:
        return default.expanduser().resolve()
    return Path(os.path.expandvars(os.path.expanduser(raw))).resolve()


def configured_paths(name: str, default: tuple[Path, ...]) -> tuple[Path, ...]:
    raw = optional_setting(name, env_path=SOURCE_ROOT / ".env")
    if not raw:
        return tuple(path.expanduser().resolve() for path in default)
    try:
        values = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise ConfigurationError(f"invalid host setting: {name}") from error
    if (
        not isinstance(values, list)
        or not values
        or any(not isinstance(value, str) or not value.strip() for value in values)
    ):
        raise ConfigurationError(f"invalid host setting: {name}")
    paths = tuple(
        Path(os.path.expandvars(os.path.expanduser(value))).resolve()
        for value in values
    )
    if len(set(paths)) != len(paths):
        raise ConfigurationError(f"invalid host setting: {name}")
    return paths


PROJECT_ROOT = configured_path("SUBMISSION_PROJECT_ROOT", SOURCE_ROOT)
# Keep the blank-value fallback inside the copied project. A host with its UTM
# assets elsewhere must set the two variables explicitly; no source-host volume
# name is ever inherited by accident.
_LEGACY_VM_IMAGES_DIR = configured_path(
    "SUBMISSION_VM_IMAGES_DIR", PROJECT_ROOT / "host-assets" / "vm-images"
)
VM_IMAGES_DIRS = configured_paths(
    "SUBMISSION_VM_IMAGES_DIRS", (_LEGACY_VM_IMAGES_DIR,)
)
VM_IMAGES_DIR = VM_IMAGES_DIRS[0]
VM_TEMPLATE = configured_path("SUBMISSION_VM_TEMPLATE", VM_IMAGES_DIR / "macOS.utm")
SHARED_DIR = configured_path("SUBMISSION_SHARED_DIR", Path.home() / "Desktop" / "共享文件")
PROJECT_SKILLS_DIR = configured_path("PROJECT_SKILLS_DIR", PROJECT_ROOT / "skills")
