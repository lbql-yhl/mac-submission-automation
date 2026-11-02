# MCP integration

This directory contains the first MCP integration for the project:

```text
integrations/mcp_worker_server.py
```

It is a **machine-side, read-only MCP Server**. It exposes only:

- `machine_info`: non-sensitive worker identity and status;
- `list_project_skills`: the names and count of local Skills;
- `submission_run_status`: a redacted summary of one submission run.

It does not expose credentials, arbitrary shell execution, VM mutation, or the
full Skill implementation. The existing Feishu API, Notion API, SSH, UTM and
Skill workflow remain unchanged.

## Install

```bash
python3 -m pip install -r requirements-mcp.txt
```

## Run over stdio

```bash
python3 integrations/mcp_worker_server.py
```

The default transport is `stdio`. Network transports are disabled by default. Set
`MCP_TRANSPORT=streamable-http` and `MCP_ALLOW_NETWORK=1` only after adding
authentication and network controls.

## Architecture role

```text
Feishu Bot / future MCP Client
             ↓
mac-submission-worker MCP Server
             ↓
local read-only machine and run state
```

The MCP Server is a tool boundary, not a task scheduler. Multi-machine queueing,
leases and worker assignment remain a later scheduler concern.
