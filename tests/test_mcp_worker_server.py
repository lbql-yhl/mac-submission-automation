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
    assert catalog["count"] == 31
    assert "utm-25" in catalog["skills"]
    assert module.submission_run_status("missing-run")["found"] is False
    print("MCP worker smoke tests passed")


if __name__ == "__main__":
    main()
