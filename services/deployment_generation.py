"""Compute the source generation shared by bot workers and their supervisor."""

from __future__ import annotations

import hashlib
from pathlib import Path


def calculate_deployment_generation(root: Path) -> str:
    """Return a stable fingerprint for Python sources loaded by bot workers."""
    digest = hashlib.sha256()
    for source_path in sorted((root / "services").rglob("*.py")):
        relative_path = source_path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative_path).to_bytes(4, "big"))
        digest.update(relative_path)
        source = source_path.read_bytes()
        digest.update(len(source).to_bytes(8, "big"))
        digest.update(source)
    return digest.hexdigest()
