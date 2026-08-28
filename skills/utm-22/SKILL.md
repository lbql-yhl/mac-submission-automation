---
name: utm-22
description: Use when utm-21 has verified the workspace and the same UTM guest is ready to archive and upload its build.
---

# utm-22

执行约束：[`../_shared/AUTOMATION_CONTRACT.md`](../_shared/AUTOMATION_CONTRACT.md)

## Contract

- Segment: 4, code processing.
- Input: `UTM_21=verified`.

## 执行

主线执行：

```bash
cd "$PROJECT_ROOT"
eval "$(python3 scripts/preflight.py --project-only --emit-shell)"
python3 "$PROJECT_ROOT/scripts/utm_22_upload.py" --run-id '<run-id>'
```

独立执行：

```bash
python3 "$PROJECT_ROOT/scripts/utm_22_upload.py" --target '<app-name>-<vm-name>'
```

上传已有 Archive：

```bash
python3 "$PROJECT_ROOT/scripts/utm_22_upload.py" --target '<app-name>-<vm-name>' --archive-path '<exact-archive>'
```

## 1. Xcode 配置

```text
scripts/utm_22_upload.py
-> scripts/utm_22_archive.py
-> xcodebuild -list -json
-> xcodebuild -showBuildSettings -json
```

成功标志：`UTM_22_XCODE_CONFIG=verified`

## 2. Archive

```text
scripts/utm_22_upload.py
-> scripts/utm_22_archive.py start
-> xcodebuild archive -scheme Runner -configuration Release -destination generic/platform=iOS
```

成功标志：`UTM_22_ARCHIVE=verified`

## 3. IPA 打包上传

```text
scripts/utm_22_upload.py
-> scripts/utm_22_distribute.mjs upload-config
```

成功标志：`UTM_22_UPLOAD=verified`、`BUILD_UPLOAD_FINAL_STATE=COMPLETE`、`BUILD_PROCESSING_STATE=VALID`

## Result and handoff

成功：`UTM_22=verified`
下一步：`utm-23`
