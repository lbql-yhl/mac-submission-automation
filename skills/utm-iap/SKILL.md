---
name: utm-iap
description: Use when an already-ready guest application needs optional in-app purchase creation after utm-script completed without IAP.
---

# utm-iap

Read and obey [`../_shared/AUTOMATION_CONTRACT.md`](../_shared/AUTOMATION_CONTRACT.md). From the repository root run `eval "$(python3 scripts/preflight.py --project-only --emit-shell)"` before the host entry.

## Optional / on-demand

This skill is **not** part of the 16-skill mainline. Do not insert it into the required order after `utm-script`. Run it only when the user explicitly asks to create in-app purchases for an app that already finished mainline script preparation without IAP.

## Prerequisites

- `utm-script` completed successfully with default no-IAP behavior (`UTM_18=verified`, guest markers include skip-IAP completion).
- Guest still has the exact inherited Edge/CDP session if a browser identity was already verified; do not restart Edge after login.
- Guest `~/Downloads/Fire_One_en1.3/.env` is present with `COPYRIGHT`.
- Guest `~/Downloads/apple-store-bm/apple_store_tools` is executable and `config/prod.yml` already holds issuer/key paths from the earlier script stage.
- Guest `~/Downloads/<COPYRIGHT>.xlsx` and `~/Downloads/<COPYRIGHT>.png` are still present (not yet moved).

## Contract

- Segment: optional after segment 3 script preparation; never required for mainline handoff.
- Input: exact `<run-id>` or exact `<page-title>`, plus `<vm-name>`, inherited `<vm-ip>`, and `<vm-user>`.
- Only public host entry:

  ```bash
  python3 "$PROJECT_ROOT/scripts/utm_iap.py" \
    --run-id '<run-id>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
  ```

  Standalone selector: replace `--run-id '<run-id>'` with `--page-title '<page-title>'`.
- The entry uses an independent `utm-iap-attempts` ledger. It only moves the IAP workbook/screenshot into `apple-store-bm` and runs `./apple_store_tools iap-enhanced`. It does not re-run fill-description enrollment or rewrite P8/prod.yml.
- Success requires both `增强版内购创建完成！` and `统计信息: 共处理 N 个产品` with `N >= 1`.
- Retry the same failed checkpoint at most three rounds using 0/5/10 seconds. Do not restart Edge or the VM after login is verified.

## Result and handoff

The canonical success summary is `执行成功：utm-iap；UTM_IAP=verified`. There is no automatic mainline handoff; return to the caller with the same run/VM context.
