---
name: utm-23
description: Use when utm-22 has uploaded a valid build and the exact App Store Connect review draft must be prepared.
---

# utm-23

Read and obey [`../_shared/AUTOMATION_CONTRACT.md`](../_shared/AUTOMATION_CONTRACT.md). From the repository root run `eval "$(python3 scripts/preflight.py --project-only --emit-shell)"` before the entry command.

## Contract

- Segment: 4, code processing.
- Input: `UTM_22=verified`, `BUILD_UPLOAD_FINAL_STATE=COMPLETE`, `BUILD_PROCESSING_STATE=VALID`, exact run/app/version/build/VM/IP/user.
- Only public host entry:

  ```bash
  python3 "$PROJECT_ROOT/scripts/utm_23.py" \
    --run-id '<run-id>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' \
    --vm-user '<vm-user>' --app-version '<version>' --build-number '<build>'
  ```

  Standalone selection may replace `--run-id '<run-id>'` with the exact `--page-title '<app-name>-<vm-name>'`.
- This entry owns the complete App Store Connect browser workflow. Run it directly; `VISUAL_BROWSER_CONTROL=forbidden` and `SUBAGENT_BROWSER_CONTROL=forbidden`.

## Execution

1. `scripts/utm_23.py` copies `scripts/session.mjs`, `scripts/utm_10_login.mjs`, and `scripts/utm_23_prepare_review.mjs` to the exact guest.
2. It probes Edge/CDP. Reuse one valid session. Only when `EDGE_PROCESS=absent` and CDP is absent, run:

  ```bash
  node '<guest>/session.mjs' start
  ```

  `session.mjs start` executes:

  ```bash
  pkill "Microsoft Edge"

  nohup "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
    --remote-debugging-port=9222 \
    --user-data-dir=/tmp/edge-debug-profile \
    --no-first-run \
    --start-maximized \
    >/dev/null 2>&1 &
  ```

3. After starting Edge, execute `scripts/utm_10_login.mjs` and require `UTM_10=verified`. If Edge/CDP identity is ambiguous, stop.
4. Execute `scripts/utm_23_prepare_review.mjs`. It derives dynamic IAP count `N`, prepares `N+1` review items, writes `02-iap-drafts.png` and `03-app-information.png`, and does not click Submit for Review.

## Result and handoff

Success: `执行成功：utm-23；UTM_23=verified`; `DRAFT_SUBMISSIONS=1`; `IAP_READY_FOR_REVIEW=<N>`; `REVIEW_ITEMS_READY=<N+1>`; `REVIEW_SCREENSHOT_02=verified`; `REVIEW_SCREENSHOT_03=verified`; `SUBMIT_FOR_REVIEW=not_clicked`. Keep the session open and hand off to `utm-24`.
