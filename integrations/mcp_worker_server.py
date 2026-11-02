"""Machine-side MCP server for the mac submission automation project.

This server intentionally exposes a small, read-only tool surface first. It is
safe to run beside the existing Feishu/Skills workflow and can be connected to
an MCP client later without moving the current submission logic into MCP.
"""

from __future__ import annotations

import json
import os
import platform
import socket
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # The optional MCP dependency is installed separately.
    FastMCP = None  # type: ignore[assignment,misc]


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
RUNS_FILE = ROOT / "runtime" / "feishu-runs.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def machine_info() -> dict[str, str]:
    """Return non-sensitive identity and capability information for this worker."""

    return {
        "machine_id": os.getenv("SUBMISSION_HOST_MACHINE") or socket.gethostname(),
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "project_root": str(ROOT),
        "vm_name": os.getenv("SUBMISSION_VM_NAME", ""),
        "status": "ready",
    }


def list_project_skills() -> dict[str, Any]:
    """List the project's Skill names without exposing Skill contents."""

    skills = sorted(
        directory.name
        for directory in SKILLS_DIR.iterdir()
        if directory.is_dir() and (directory / "SKILL.md").is_file()
    )
    return {"count": len(skills), "skills": skills}


def submission_run_status(run_id: str) -> dict[str, Any]:
    """Return a redacted summary for one submission run."""

    if not run_id or len(run_id) > 200:
        return {"found": False, "error": "invalid run_id"}

    data = _read_json(RUNS_FILE)
    if not isinstance(data, dict):
        return {"found": False, "error": "run store is unavailable"}

    for run in data.get("runs", []):
        if not isinstance(run, dict) or run.get("id") != run_id:
            continue
        allowed_fields = (
            "id",
            "status",
            "created_at",
            "updated_at",
            "host_machine",
            "vm_name",
            "current_skill",
            "attempt",
        )
        return {
            "found": True,
            "run": {key: run[key] for key in allowed_fields if key in run},
        }
    return {"found": False}


if FastMCP is not None:
    mcp = FastMCP(
        "mac-submission-worker",
        instructions=(
            "Read-only machine and submission status tools for the mac submission "
            "automation project. Do not expose credentials or arbitrary shell access."
        ),
    )
    mcp.tool()(machine_info)
    mcp.tool()(list_project_skills)
    mcp.tool()(submission_run_status)
else:
    mcp = None


def main() -> int:
    if mcp is None:
        raise SystemExit(
            "MCP dependency is not installed. Run: "
            "python -m pip install -r requirements-mcp.txt"
        )
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport != "stdio" and os.getenv("MCP_ALLOW_NETWORK") != "1":
        raise SystemExit(
            "Network MCP transport is disabled by default. Set MCP_ALLOW_NETWORK=1 "
            "only after adding authentication and network controls."
        )
    mcp.run(transport=transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
