---
name: utm-image
description: Use when the executed application stage needs its exact submission image assets prepared and verified.
---

# utm-image

Read and obey [`../_shared/AUTOMATION_CONTRACT.md`](../_shared/AUTOMATION_CONTRACT.md). From the repository root run `eval "$(python3 scripts/preflight.py --project-only --emit-shell)"` before the entry command.

## Contract

- Segment: 3, script preparation and execution.
- Input: exact `<run-id>` or `<page-title>`, plus `<vm-name>`, inherited `<vm-ip>`, `<vm-user>`, and optional distinct `<asset-app-name>`.
- Only public host entry:

  ```bash
  python3 "$PROJECT_ROOT/scripts/utm_image.py" \
    --run-id '<run-id>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
  ```

  Standalone selector: replace `--run-id '<run-id>'` with `--page-title '<page-title>'`. Add `--asset-app-name '<asset-app-name>'` only for an explicitly different source.
- For a user-authorized replacement of an already populated 6.9-inch iPhone panel with the exact verified development attachment, append both `--force-development --replace-existing`. These flags are inseparable for replacement: they must pre-verify the complete development package, bind the unique application/version/display, clear only that target panel, upload the new set, and independently verify the stable final count. This variant must emit `SCREENSHOT_PREUPLOAD_CLASSIFICATION=nonempty_authorized` and `SCREENSHOT_REPLACEMENT=verified`; it never clicks `Submit for Review`.
- Require the exact application/source binding and independently verify the expected image set and guest delivery. Do not print source credentials or unrelated asset contents.
- Retry the same source/file checkpoint at most three rounds using 0/5/10 seconds; never substitute another application's images.

## Result and handoff

The canonical success summary is `执行成功：utm-image；UTM_19=verified`. Immediately hand the same run, VM, application, source binding, and verified assets to `utm-p8`.
