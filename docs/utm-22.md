# UTM-22：Xcode 点击 Archive，命令/API 上传

对应技能：`utm-22`。严格接在 `utm-21` 后，并继续使用同一 UTM guest。边界固定为：

```text
Xcode GUI：打开 workspace → 签名/Profile → Product > Archive
命令/API：Archive 只读校验 → IPA 封装 → buildUploads → uploaded=true → COMPLETE / VALID
```

Archive 成功后不点击 Xcode 的 `Distribute App`，也不改用 Transporter；上传只走 `scripts/utm_22_distribute.mjs`。

SSH 直接继承 `utm-21` 已验证的同一 VM/IP/用户、工作区和宿主公钥，所有 SSH/SCP 调用固定使用 `BatchMode=yes`。连接失效时只对同一精确 VM 自动刷新 IP、修复 Remote Login 和恢复宿主公钥，不向用户索取密码、SSH Key、IP，也不等待 SSH 人工处理。

## 操作步骤

1. 确认 `UTM_21=verified`，直接继承其 `vm_name`、VM IP、SSH 用户/home 和 `REPO_PATH`；用一次带 `-o BatchMode=yes -o ConnectTimeout=5` 的只读 SSH 同时验证身份与唯一工作区 `/Users/<vm_name>/StudioProjects/<repo_name>/ios/Runner.xcworkspace`。正常路径不扫描 VM/MAC/ARP；连接失效时按上面的 SSH 全自动约束恢复。
2. 从实际运行的 Xcode 进程读取 `.app` bundle 路径和版本/build；不能只看 `/Applications/Xcode.app`。
3. 通过 BatchMode guest SSH 执行 `open -a '<已验证的 Xcode.app 绝对路径>' '<workspace>'`；应用路径必须与上一步读取版本的 bundle 完全相同，禁止只写应用名让系统另选 Xcode。等待 Xcode 稳定显示 `Runner` 和 `Pods`；Downloads 权限弹窗确认归属后点击 `Allow`。
4. 点击 `Runner` → `Signing & Capabilities`，确认目标为 `Any iOS Device (arm64)`。版本/构建号必须四层一致：`pubspec.yaml` 的 `version:`、Flutter 生成配置中的 `FLUTTER_BUILD_NAME/NUMBER`、Runner target 的 `MARKETING_VERSION/CURRENT_PROJECT_VERSION`、Xcode 界面当前值。把非敏感值与各来源文件 SHA-256 写入 ledger，独立回读后记录 `VERSION_BUILD_SOURCE=verified`；不一致时不得猜值或只改 Xcode 显示值。
5. `Provisioning Profile=None` 时点击 `None`，只在 `Download Profile...` 自身蓝色高亮后确认；如需账号，使用当前匹配 `<应用名>-<vm_name>` 的账号登录。
6. 选择当前应用和 bundle ID 唯一匹配的 App Store Profile，确认 `Team`、`Signing Certificate=Apple Distribution` 属于同一当前 Team，且无红黄警告；不得照抄任何旧运行的应用、人员、证书或 Team 值。
7. 重新确认 scheme 和目标后生成稳定 `ARCHIVE_ATTEMPT_ID`，在宿主 `${PROJECT_ROOT}/runtime/utm-22-attempts/<run-id>/archive-<id>.json` 以 mode-600 同目录临时文件、文件/目录 `fsync` 和原子替换创建 ledger，父目录 mode 700。其中固定记录 run/VM/workspace/App/Bundle ID/版本构建/Team/Xcode bundle、Organizer 前置清单 hash 和 `state=prepared`；独立回读内容、权限与 ID 后记录 `ARCHIVE_LEDGER_MODE=600`。依次持久化 `clicking -> clicked_result_unknown -> verified`，只点击 `Product` → `Archive` 一次。结果不明只查同一 attempt，不新建 ID。
8. Organizer 出现新 `Runner` Archive 后，只选择同时匹配当前 App、Bundle ID、版本、构建号、Team、`ARCHIVE_ATTEMPT_ID` 时间窗口且不在前置清单的唯一项；不得只按最新时间选。结果不明时只读检查 Organizer、构建进程和 DerivedData/Archive 元数据。`.xcarchive` 是目录：递归排序生成包含相对路径/类型/mode/大小、文件内容 SHA-256、符号链接原始目标的 manifest，对 manifest 字节计算 `ARCHIVE_MANIFEST_SHA256`，由第二个只读进程重生并要求完全相等；不得对目录路径执行普通文件 `shasum` 并冒充 Archive 内容哈希。
9. 将宿主固定脚本复制到 guest，并验证两端 SHA-256 一致：

    ```text
    ${PROJECT_ROOT}/scripts/utm_22_distribute.mjs
    ```

10. 用从未存在的新 IPA 路径执行 `prepare`：

    ```zsh
    /usr/local/bin/node /Users/<vm_name>/Downloads/utm_22_distribute.mjs prepare \
      --archive '<唯一新 xcarchive>' \
      --output '/Users/<vm_name>/Downloads/<应用名>-prepare-<时间戳>.ipa'
    ```

11. 只有 `ARCHIVE_DISTRIBUTION=verified` 才继续。要求 Apple Distribution 签名、App Store Profile、Team、Bundle ID、版本/构建、entitlements、`Payload` 和需要时的 `SwiftSupport/iphoneos` 全部通过。
12. 从当前任务取得数字 App ID，从现有 `prod.yml` 只读取得 issuer ID、key ID 和 `.p8` 路径；不得输出密钥、完整配置或 JWT。
13. 用另一个新 IPA 路径执行 `distribute`：

    ```zsh
    /usr/local/bin/node /Users/<vm_name>/Downloads/utm_22_distribute.mjs distribute \
      --archive '<唯一新 xcarchive>' \
      --output '/Users/<vm_name>/Downloads/<应用名>-upload-<时间戳>.ipa' \
      --app-id '<数字 App ID>' \
      --issuer-id '<issuer ID>' \
      --key-id '<key ID>' \
      --private-key '<绝对 AuthKey_*.p8 路径>'
    ```

14. 在任何 Apple 创建请求前，先为当前 run + App ID + Archive manifest + 版本 + 构建号持久化稳定 `UPLOAD_ATTEMPT_ID`。attempt 路径必须显式传入脚本并位于当前用户 Downloads，只能是不存在或非符号链接普通文件；脚本用随机同目录临时文件、创建时 mode 600、文件/目录 `fsync` 和原子替换，每次写后独立回读身份/内容/权限，记录 `UPLOAD_ATTEMPT_MODE=600`。脚本以 `/v1/builds`（而不是不支持集合读取的 `buildUploads`）只读查询同一 App、版本和构建号；任何已有 Build 或多个候选均拒绝新建。只有零匹配时才创建 `buildUploads` / `buildUploadFiles`，并一旦获得就持久化 `BUILD_UPLOAD_ID`。POST 结果未知时按 5/10/20 秒只读重查 `/v1/builds`，记录 `recovered_after_create_result_unknown` 或 `create_result_ambiguous`，禁止重发；随后按 15/30/60/120 秒轮询同一 Build Upload。最终必须为 `COMPLETE`，关联 Build 必须为 `VALID`。

## Game Center 恢复

只有 App Store Connect 精确显示 `You must add the com.apple.developer.game-center key in Xcode.`，且旧签名/Profile 都缺少 `com.apple.developer.game-center` 时才进入：

1. 在 Xcode 界面保持营销版本不变，把构建号设为旧构建号加 `1`。
2. `Runner` → `Signing & Capabilities` → `+ Capability` → `Game Center`，刷新并重新选择当前 App Store Profile。
3. 点击前生成全新 `GAME_CENTER_ARCHIVE_ATTEMPT_ID` 和独立 mode-600 ledger，记录旧/新构建号、capability/profile 证据与 Organizer 前置 manifest，再按主线同一状态机只点击一次 `Product` → `Archive`；不复用原 `ARCHIVE_ATTEMPT_ID`，不用命令行构建/导出，不覆盖旧 Archive。
4. Organizer 新 Archive 的实际 marketing version 必须不变，实际 build 必须等于旧值 +1，并生成新 `ARCHIVE_MANIFEST_SHA256`。新签名和新 Profile 都验证 `com.apple.developer.game-center=true` 后，才以全新 `UPLOAD_ATTEMPT_ID` 走相同 `prepare` / `distribute` 路径。

## 完成检查

```text
UTM_21=verified
SSH_KEY_AUTH=verified
XCODE_WORKSPACE=verified
XCODE_SIGNING=verified
XCODE_GUI_BUILD=yes
VERSION_BUILD_SOURCE=verified
ARCHIVE_ATTEMPT_ID=<stable-id>
ARCHIVE_LEDGER_MODE=600
ARCHIVE_MANIFEST_SHA256=<sha256>
XCODE_ARCHIVE=verified
ARCHIVE_DISTRIBUTION=verified
IPA_PAYLOAD=verified
IPA_SWIFT_SUPPORT=verified
IPA_SHA256=verified
APP_STORE_CONNECT_APP=verified
UPLOAD_ATTEMPT_ID=<stable-id>
UPLOAD_ATTEMPT_MODE=600
BUILD_UPLOAD_ID=<id>
BUILD_UPLOAD_FINAL_STATE=COMPLETE
BUILD_PROCESSING_STATE=VALID
SCRIPT_EXIT=0
XCODE_GUI_UPLOAD=no
API_UPLOAD=yes
ARCHIVE_MODIFIED=no
UTM_22=verified
```

使用 Game Center 恢复分支时，额外要求 `SIGNED_GAME_CENTER=verified` 和 `PROFILE_GAME_CENTER=verified`。

记录 `UTM_22=verified`，结束 `utm-22`，保留同一 VM、当前构建上下文和既有 guest Edge，立即继续 `utm-23`；不得等待用户确认。

## 自动恢复与最后故障卡

- 每次 GUI 操作后必须等待至少 3 秒并读取新截图；目标或高亮不明确时，先回到最近验证锚点、作废旧坐标并按本技能矩阵恢复。
- VM、workspace、Xcode 实际 bundle、账号、Profile、Team、证书或 Archive 不唯一时先只读重新发现并按完整身份交叉验证，不猜测；仍不唯一才是 `unrepairable`。
- Xcode 签名页有红黄警告或 Archive 失败时，先读取准确诊断、修复可确定的 Profile/证书/权限问题并重新复验；未通过前不进入 API 上传。
- `PROCESSING` 不等于失败；不得重复创建上传或改用 Xcode/Transporter上传同一版本/构建号。
- `FAILED` / `INVALID` 保留非敏感错误并诊断。`90426` 检查 `SwiftSupport`；`90433` 检查 Swift dylib 的 Apple 原始签名和 UUID。只有技能矩阵的安全修复已穷尽，或同一不可逆 attempt 最终仍不明确，才携带恢复证据发送最后故障卡。
- 完成只表示构建已上传并处理有效；不得点击 `Add for Review`、提交审核或发布。
