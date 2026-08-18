# Public Release Hardening Design

## Goal

Publish a portable, documented version of the macOS submission automation project without exposing credentials, Feishu/Notion resource identifiers, personal host paths, runtime records, or old private history.

## Scope

- Preserve the existing uncommitted implementation and test work.
- Make all 16 project skills runnable from a configurable project root.
- Keep `SKILL.md` as the workflow authority and reduce duplicate operational documentation.
- Document project setup and Feishu bot configuration for a new host.
- Move host-specific passwords, tokens, resource identifiers, chat routing, paths, and signing material to the host-local `.env` or already-ignored runtime files.
- Fix the complete test suite and add public-release hygiene checks.
- Publish a clean public snapshot while retaining old sensitive history only in private archives.

## Configuration boundary

The repository contains only empty examples and non-secret defaults. Each host copies `.env.example` to `.env`, sets mode `0600`, and supplies its own values. The following values have no source-code fallback:

- `SUBMISSION_GUEST_PASSWORD`
- `FEISHU_DAILY_REPORT_CHAT_ID`
- `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, callback verification values, and routing IDs
- Notion tokens and page IDs
- Feishu Wiki/Base URL, app token, table ID, and view ID
- Codeup credentials
- OpenAI key
- host paths and host identity

Missing required values fail with a stable, non-sensitive configuration error. Runtime files that can contain message, callback, or run metadata are created with user-only permissions.

## Skills and documentation

All skill commands resolve the current repository through `PROJECT_ROOT`, emitted by `scripts/preflight.py`, instead of embedding one user's home directory or Python environment. Every skill links to the shared automation contract. Short skills state their inputs, single host entrypoint, success marker, failure/retry rule, and handoff. Long workflow details remain in the skills; `docs/` becomes deployment, configuration, architecture, and operator guidance rather than a second copy of each workflow.

The README provides a portable quick start. `docs/utm-feishu-bot.md` documents Feishu Open Platform setup, required permissions/events, long-connection and callback modes, configuration groups, startup, health checks, and safe troubleshooting. Historical planning documents are excluded from the public snapshot.

## Verification

Tests enforce these invariants:

- no tracked personal home path or approved-for-private-history identifiers;
- no fixed guest password or embedded Feishu resource destination;
- examples contain empty sensitive values;
- private config and runtime paths are ignored;
- runtime metadata files use restrictive permissions;
- skill frontmatter, links, entrypoints, and shared-contract references are valid;
- the full Python and Node suites pass;
- Ruff, JavaScript syntax checks, project preflight, and skill validation pass.

A final staged-tree scan reports only file paths and rule names, never matched values.

## Publication model

The repository currently has sensitive constants in historical commits. Rewriting only the branch tip is insufficient. Preserve the old `yhl-devops-mac` repository under a private archive name, make the legacy public `mac-submission-automation` repository private, and create a new public `yhl-devops-mac` repository from a single sanitized orphan snapshot. Publish only `main`, with no old branches or tags. Verify remote visibility, refs, commit identity, and a fresh clone before declaring completion.

Credential rotation remains necessary for any credential that was previously exposed by the legacy public history; history cleanup cannot invalidate a credential.
