#!/usr/bin/env python3
"""Smoke tests for the optional machine-side MCP integration."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "integrations" / "mcp_worker_server.py"


def load_module():
    spec = importlib.util.spec_from_file_location("mcp_worker_server", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load MCP worker module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    module = load_module()
    catalog = module.list_project_skills()
    # Hardening trunk uses the renamed 16-skill mainline (+ optional skills),
    # not the legacy utm-1..utm-25 layout from lbql main.
    assert catalog["count"] >= 1
    assert isinstance(catalog["skills"], list) and catalog["skills"]
    assert "utm-vm-clone" in catalog["skills"] or "utm-notion" in catalog["skills"]
    assert module.submission_run_status("missing-run")["found"] is False
    print(f"MCP worker smoke tests passed (skills={catalog['count']})")


if __name__ == "__main__":
    main()
