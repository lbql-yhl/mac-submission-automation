---
name: utm-clash-ip
description: Use when the target UTM guest needs its assigned proxy and Clash/IP state configured for the current application.
---

# utm-clash-ip

Read and obey [`../_shared/AUTOMATION_CONTRACT.md`](../_shared/AUTOMATION_CONTRACT.md). From the repository root run `eval "$(python3 scripts/preflight.py --project-only --emit-shell)"` before the entry command.

## Contract

- Segment: 2, environment preparation.
- Input: exact `<vm-name>`, `<app-name>`, inherited `<vm-ip>`, Notion `<parent-title>`, and `<page-title>`.
- Only public host entry:

  ```bash
  python3 "$PROJECT_ROOT/scripts/utm_clash_ip.py" \
    --vm-name '<vm-name>' --application-name '<app-name>' --vm-ip '<vm-ip>' \
    --parent-title '<parent-title>' --page-title '<page-title>'
  ```

- Require one inventory-bound VM and one authoritative proxy assignment. Verify guest proxy configuration and outbound identity without printing proxy credentials.
- Tun/service install uses configured `SUBMISSION_GUEST_PASSWORD` through guest `sudo` (no GUI password dialog).
- After VM start and before `console_state`, use the shared guest-desktop helper in the automation contract so a cold-start login window becomes interactive. Require `SUBMISSION_GUEST_PASSWORD`. Success needs the exact console user and a running Finder. Failure codes: `GUEST_DESKTOP_PASSWORD_MISSING`, `GUEST_DESKTOP_LOGIN_FAILED`, `GUEST_DESKTOP_CONSOLE_UNKNOWN`.
- Retry the same VM/proxy checkpoint at most three rounds using 0/5/10 seconds. Never claim, switch, or guess another proxy or VM.

## Result and handoff

The canonical success summary is `执行成功：utm-clash-ip；UTM_CLASH_IP=verified`. Immediately hand the same run, VM, network identity, and Notion page to `utm-login`.
