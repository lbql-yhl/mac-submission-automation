---
name: utm-22
description: Use after utm-21 when the same UTM guest is ready for Xcode archive creation and App Store Connect build upload.
---

# UTM-22：Xcode 点击 Archive，命令/API 上传

## 全局自动恢复与最后故障卡规则

本技能强制继承共享重复操作记忆：原生粘贴调用 `OP-NATIVE-PASTE`，浏览器 URL 调用 `OP-BROWSER-URL-NO-SCHEME`，Apple 电话/验证码调用 `OP-APPLE-PHONE-OTP`，固定 VM 密码调用 `OP-FIXED-PASSWORD-1234`，必须由用户决定的业务节点才调用 `OP-USER-CONFIRMATION`。不得在本技能内发明简化版或冲突步骤。可安全修复的故障必须做满三轮“诊断→实际修复→独立复验”；只有不可逆动作、不能安全重复写入或外部不可修复状态，才改做三轮独立只读复核。少于三轮时运行时拒绝发卡。

执行任何命令前，在项目根目录运行 `eval "$(python3 scripts/preflight.py --project-only --emit-shell)"`，取得当前机器的动态路径。必须先完整遵守 [`../_shared/AUTOMATION_CONTRACT.md`](../_shared/AUTOMATION_CONTRACT.md)：固定顺序是自动诊断、自动修复、自动复验，只有智能体确实无法修复时才允许发送飞书故障卡。

- 正常成功路径连续自动执行，不发送故障卡，不等待用户确认或普通聊天回复。
- 可逆误点先回到本技能矩阵列出的最近验证锚点，作废旧坐标，等待至少 3 秒并用最新截图重做当前最小动作；成功后记录 `GUI_RECOVERY=verified` 并继续。
- SSH、API、文件和页面瞬态错误按共享合同有界恢复；不可逆动作只执行一次，结果不明时只读查询同一 attempt，禁止盲目重做。
- 只有恢复预算穷尽或只读证明为外部不可修复状态，才记录 `AUTO_RECOVERY_ATTEMPTS`、`AUTO_RECOVERY_ACTIONS`、`AUTO_RECOVERY_RESULT=exhausted|unrepairable` 和最后验证锚点。
- 自动恢复穷尽后，使用下列最后出口；`--unrepairable` 只允许用于 CAPTCHA、账号锁定、权威数据缺失、权限/所有权冲突或不可逆结果仍不明确，不能绕过可执行的恢复：

```bash
python3 services/feishu_bot.py notify-fault \
  --run-id '<current-run-id>' \
  --chat-id '<original-chat-id>' \
  --stage 'utm-22:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-22' \
  --recovery-attempts '<actual-count-at-least-3>' \
  --recovery-actions '<diagnose,repair,reverify>' \
  --recovery-result '<exhausted|unrepairable>'
python3 services/feishu_bot.py wait-decision \
  --run-id '<current-run-id>' --decision-kind fault --timeout-seconds 3600
```

规则：`--recovery-result unrepairable` 必须同时追加 `--unrepairable`；恢复穷尽的 `exhausted` 分支不得追加该参数。两种分支都必须填写真实的恢复次数和动作，不能把占位符原样执行。

故障卡仍固定保留 `stop`、`manual_continue`、`retry_skill` 三个决定及稳定 UUID/首次送达后一小时超时规则。当前执行器收到继续决定后立即重读同一精确现场；已验证步骤只有在证据仍成立时才跳过。故障卡是最后恢复出口，不是正常确认节点。

## 本技能自动恢复矩阵

| 故障点 | 自动诊断、修复和复验 | 最后发卡边界 |
|---|---|---|
| Xcode target/menu/prompt 误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图；提交 Archive 前用 `Escape`/`Cancel` 回到 Runner workspace，重新核对 scheme/target/profile；记录 `GUI_RECOVERY=verified`、`XCODE_GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立核对后仍无法恢复才发卡 |
| Archive 结果不明 | 持久化构建时间窗；只读检查 Organizer/进程/日志，证明未创建才允许再次点一次 | 仍 ambiguous 不创建第二 Archive |
| API 上传 | 创建前持久化 `UPLOAD_ATTEMPT_ID`；网络结果不明时先查询同一版本和构建号及该 attempt，进行 15/30/60/120 秒有界只读轮询 | 仍不明才发卡，禁止新 buildUpload |
| Game Center 恢复 | 只处理精确 Apple 错误，GUI 构建号 +1、Capability/Profile/签名逐项回读后创建唯一替代 Archive | 任一前置不唯一为 `unrepairable` |

## 定位

本技能严格接在 `utm-21` 后。Xcode GUI 只负责打开工作区、确认签名并通过点击生成 `.xcarchive`；Archive 出现后，不点击 Xcode 的 `Distribute App`，而是复用现有脚本完成只读校验、IPA 封装和 App Store Connect API 上传。

固定上传脚本：

```text
${PROJECT_ROOT}/scripts/utm_22_distribute.mjs
```

Xcode GUI 操作复用当前 Computer Use 的 `node_repl`/`sky` 驱动器；它只是 GUI 操作工具，不是本项目流程中的额外技能。

## SSH 全自动约束

- 直接继承 `utm-21` 的同一精确 VM/IP、`<vm_name>`、workspace 和 `SSH_KEY_AUTH=verified`；所有宿主 SSH/SCP 调用统一使用 `-o BatchMode=yes -o ConnectTimeout=5`，不重复配置 SSH。
- SSH 检查失败时自动按同一 VM 的精确 MAC 刷新 IP、检查 Remote Login/端口，并用固定 `1234` 恢复 `${SUBMISSION_SSH_PUBLIC_KEY}`；不得向用户索取密码、SSH Key 或 IP。
- 恢复后重新验证用户/home/workspace；仍失败时记录 `SSH_AUTO_RECOVERY=blocked`，先按 `utm-22-ssh-auto-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；不选择其他 VM、workspace 或 Archive。

## 全程规则

- 每次 GUI 操作后至少等待 3 秒，重新读取最新截图；只有页面、目标控件和菜单高亮都正确才继续。
- 只使用 `utm-21` 继承的同一 VM、应用、代码目录、Bundle ID、App ID 和账号上下文；不得从旧 run 或记忆回填动态值。
- 账号、密码、验证码、`.p8` 内容和 JWT 不得记录或回显。常规 VM、Keychain、codesign 提示使用项目统一虚拟机凭据，不询问、不回显。
- 不运行依赖安装、提交、推送、发布或提审命令；不得修改 Archive，也不得对旧 Archive 重签。

## 操作步骤

### 一、继承 guest 并确认 Xcode

1. 要求前序已明确记录 `UTM_21=verified`，直接继承其 `vm_name`、VM IP、SSH 用户/home 和 `REPO_PATH`。用一次 `BatchMode=yes` 只读 SSH 同时确认身份并验证工作区唯一存在：

   ```text
   /Users/<vm_name>/StudioProjects/<repo_name>/ios/Runner.xcworkspace
   ```

   正常路径不得重新扫描 started VM、MAC 或 ARP。只有继承 IP 已不可达时，才允许按该 `<vm_name>.utm` 的精确配置 MAC 刷新一次 IP，再重复同一 SSH 身份/workspace 检查；禁止选择其他或“最新”VM。
2. 通过正在运行的 Xcode PID 读取实际 `.app` bundle 路径、bundle identifier、`CFBundleShortVersionString` 和 `CFBundleVersion`；不能只检查 `/Applications/Xcode.app` 后就假定它是实际运行版本。若有多个 Xcode 进程，先只读关联窗口标题、前台 PID 和打开的 `Runner.xcworkspace` 路径，只接受唯一持有当前 workspace 的进程；仍不唯一时用第 3 步的精确 bundle/path 重新执行 `open` 并重读，不关闭其他 Xcode、不猜版本。这个可逆恢复完整执行三轮且每轮独立归属核对；三轮仍无法唯一归属才记录恢复证据并进入最后故障卡。
3. 通过 SSH 打开工作区：

   ```zsh
   ssh -o BatchMode=yes -o ConnectTimeout=5 <vm_name>@<vm-ip> \
     "open -a '<已验证的 Xcode.app 绝对路径>' '/Users/<vm_name>/StudioProjects/<repo_name>/ios/Runner.xcworkspace'"
   ```

   `open -a` 使用的路径必须与上一步读取版本的 Xcode bundle 完全相同，禁止退回应用名让系统另选一个 Xcode。

4. 等待至少 3 秒并确认 Xcode 显示 `Runner` 和 `Pods`，窗口标题/Recent 路径都指向当前 `Runner.xcworkspace`。出现 Downloads 权限弹窗时，确认弹窗进程、标题和当前 Xcode 一致后点击唯一 `Allow`，再等待至少 3 秒确认弹窗消失；误开菜单或错误弹窗时先按 `Escape`/`Cancel` 回到 workspace，作废旧坐标、重读最新截图并记录 `XCODE_GUI_RECOVERY=verified`。未知 TCC 或安全弹窗先独立只读识别三轮；只有三轮均证明系统明确要求无法自动取得的外部授权时才进入最后故障卡。

### 二、确认签名和 Profile

1. 点击项目导航中唯一的蓝色工程 `Runner`，等待至少 3 秒重读；在 TARGETS 列表只点击 `Runner`，再等待并确认右侧标题同时显示工程和 target。若误入 `Pods` 或 PROJECT 配置，点击左侧同一 `Runner` 锚点返回，重读最新截图后重做，记录 `XCODE_GUI_RECOVERY=verified`。
2. 进入 `Signing & Capabilities`，确认 scheme 为 `Runner`、运行目标为 `Any iOS Device (arm64)`。版本/构建号不得来自记忆或只看 Xcode 一个字段，必须按以下四层形成权威账本：
   1. SSH 读取 Git 工作区唯一 `pubspec.yaml` 的顶层 `version: <marketing>+<build>`，要求只出现一次、marketing 符合点分数字版本、build 为正整数；
   2. 读取本轮生成的 `ios/Flutter/Generated.xcconfig`，要求唯一 `FLUTTER_BUILD_NAME`/`FLUTTER_BUILD_NUMBER` 与 pubspec 完全一致；
   3. 以只读 `xcodebuild -workspace Runner.xcworkspace -scheme Runner -showBuildSettings` 检查唯一 Runner target 的 `MARKETING_VERSION`、`CURRENT_PROJECT_VERSION` 和 `PRODUCT_BUNDLE_IDENTIFIER`；该命令只读设置，不得 Archive/export；
   4. 最新 Xcode GUI 的 General/Signing 可见 Bundle ID、营销版本、构建号与前三项完全一致。

   四层一致后把非敏感值及来源文件 SHA-256 写入本轮 ledger，记录 `VERSION_BUILD_SOURCE=verified`。任一不符不得猜“当前任务值”，先回到 pubspec/生成配置/Runner target 查明唯一声明源；不得只改 Xcode 显示值掩盖 Flutter 配置。最终上传使用的权威值还必须由新 Archive 的 Info.plist 再确认。
3. 若 `Provisioning Profile` 为 `None`，点击 `None` 后等待至少 3 秒读最新菜单；一次只移动一个菜单项并在每次移动后截图，直到 `Download Profile...` 自身蓝色高亮才确认。误高亮立即按 `Escape`，回到签名页重新打开菜单，禁止确认错误项目。
4. 如 Xcode 要求账号，只使用当前匹配 `<应用名>-<vm_name>` 的账号；已知账号、电话和短信验证码按既有 Notion API 路径自动实时读取并完成。错误账号先取消选择并回到 Accounts 列表重新匹配一次；只有 CAPTCHA、账号锁定、零/多验证码或未知安全挑战才是外部不可修复状态，复核后进入最后故障卡，绝不尝试其他账号。
5. 选择当前应用唯一匹配的 App Store Provisioning Profile。等待至少 3 秒重新读取，确认 `Team`、`Signing Certificate` 与该 Profile 属于同一 Team，证书为 `Apple Distribution`，并且两项均无红色或黄色警告；警告出现时刷新 profile、重新选择同一 Team/Profile 并完整做三轮可逆修复，每轮都独立回读 Team/Profile/证书/警告，不能直接发卡。

### 三、用 Xcode GUI 创建 Archive

1. Archive 前生成稳定 UUID `ARCHIVE_ATTEMPT_ID`，在宿主 `${PROJECT_ROOT}/runtime/utm-22-attempts/<current-run-id>/archive-<id>.json` 用同目录 mode-600 临时文件、`fsync`、原子替换创建 ledger；父目录 mode 700。固定 schema 包含 run/VM/IP/REPO_PATH、App/Bundle ID、四层一致的版本/构建号、Team、Xcode bundle 路径及版本、`prepared_at`、Organizer 前置清单 manifest hash 和 `state=prepared`，不得含账号或签名密钥。独立回读内容、权限和 ID 后记录 `ARCHIVE_LEDGER_MODE=600`。再次确认 scheme 为 `Runner`、目标为 `Any iOS Device (arm64)`、签名页无警告。
2. 点击前把同一 ledger 原子更新为 `state=clicking`。点击 `Product` 后等待至少 3 秒，读取最新菜单；只有 `Archive` 本身蓝色高亮且可用时点击一次，并立即把 ledger 更新为 `state=clicked_result_unknown`。若误点其他菜单项或菜单关闭且 ledger 尚未进入 clicking，先按 `Escape` 回到 Runner workspace、重读全部锚点并重做当前最小动作；一旦进入 clicking，任何结果不明都只读恢复。构建只能由这次 Xcode GUI 点击触发，不使用命令行构建器。
3. 出现 Xcode Cloud 弹窗时，核对进程/标题属于当前 Archive attempt 后点击唯一 `Don't Ask Again`；出现 Keychain/codesign 授权弹窗时使用固定 guest 密码并点击唯一 `Always Allow`。每次点击后等待至少 3 秒并确认对应弹窗消失，错误弹窗用 `Cancel`/`Escape` 回滚后重新定位。
4. 只读观察当前 attempt 的 Xcode 构建活动、Report Navigator、派生日志和 Organizer。成功必须以 Organizer `Archives` 页面出现新 `Runner` Archive 为准，不能只凭进度条消失或日志无红字判断。结果不明时在 15/30/60/120 秒窗口继续只读核对同一 attempt；只有构建活动、日志和 Archive 清单三者共同证明点击未启动且没有新 Archive，才允许返回第 2 步再点击一次。任何已启动、已生成或仍 ambiguous 状态都禁止第二次 Archive。
5. 在 Organizer 中只选择同时匹配当前 App、Bundle ID、版本、构建号、Team、`ARCHIVE_ATTEMPT_ID` 时间窗且不在前置清单中的唯一新 Archive；不得仅按“修改时间最新”选择。实际 Archive Info.plist 的 marketing/build 必须与第二区块账本一致，否则本轮失败，不得修改 Archive。

   `.xcarchive` 是目录，禁止对目录路径调用普通文件 `shasum` 冒充内容哈希。必须递归排序并生成 manifest：每行固定包含相对路径、类型、mode、大小；普通文件再含内容 SHA-256，符号链接含原始 link target，目录不读内容。manifest 本身保存为 mode 600，再对其字节计算 `ARCHIVE_MANIFEST_SHA256`；用第二个只读进程重新生成并要求完全一致。随后把绝对 Archive 路径、Info.plist 元数据、manifest hash 和 `state=verified` 原子写回同一 ledger。误选旧 Archive 时不点任何按钮，重新选择唯一候选并记录 `XCODE_GUI_RECOVERY=verified`。
6. 记录：

   ```text
   XCODE_GUI_BUILD=yes
   ARCHIVE_ATTEMPT_ID=<stable-id>
   ARCHIVE_LEDGER_MODE=600
   ARCHIVE_MANIFEST_SHA256=<sha256>
   XCODE_ARCHIVE=verified
   XCODE_GUI_RECOVERY=verified|not_needed
   ```

   此后不得点击 Xcode 的上传入口：`XCODE_GUI_UPLOAD=no`。

### 四、只读校验并生成测试 IPA

1. 将固定脚本复制到 guest 的 `/Users/<vm_name>/Downloads/utm_22_distribute.mjs`，核对宿主与 guest SHA-256 完全一致。
2. 使用从未存在的新输出路径执行 `prepare`：

   ```zsh
   /usr/local/bin/node /Users/<vm_name>/Downloads/utm_22_distribute.mjs prepare \
     --archive '<唯一新 xcarchive 的绝对路径>' \
     --output '/Users/<vm_name>/Downloads/<应用名>-prepare-<时间戳>.ipa'
   ```

3. 只有 `ARCHIVE_DISTRIBUTION=verified` 才能继续。脚本必须确认：
   - Archive 只有一个顶层 `.app`；
   - `codesign --verify --deep --strict` 成功，证书为 Apple Distribution；
   - `embedded.mobileprovision` 有效且为 App Store 类型；
   - `get-task-allow=false`、`beta-reports-active=true`；
   - Profile、签名、Team、Bundle ID、版本和构建号一致；
   - IPA 含 `Payload/<App>.app`；若 App 含 `libswift*.dylib`，只从 `/Library/Developer/CommandLineTools` 选择同名、`dwarfdump --uuid` 相同且 Authority 为 `Software Signing` 的 iPhoneOS runtime，放入 `SwiftSupport/iphoneos`。

### 五、用既有命令/API 上传

1. 从当前任务已验证上下文取得数字 App ID；从 guest 现有 `prod.yml` 只读取得 issuer ID、key ID 和 `.p8` 路径。不得打印完整配置、私钥或 JWT。
2. 在任何 Apple 创建请求前，固定当前 run + App ID + Archive manifest + 版本 + 构建号对应的 attempt 文件。路径必须是当前用户 Downloads 下的非符号链接普通文件或尚不存在；脚本使用随机同目录临时文件、创建时 mode 600、文件与目录 `fsync` 后原子替换，并在每次状态写入后独立回读 JSON 身份/内容/权限。已有旧权限会先收紧到 600 并复验，符号链接或非普通文件直接拒绝。成功记录 `UPLOAD_ATTEMPT_MODE=600`。首次使用从未存在的新 IPA 路径执行 `distribute`；恢复执行必须复用同一 attempt 文件和同一 IPA，脚本会核对 Archive 身份、IPA SHA-256 和 attempt 元数据，绝不接受另一个 IPA：

   ```zsh
   /usr/local/bin/node /Users/<vm_name>/Downloads/utm_22_distribute.mjs distribute \
     --archive '<唯一新 xcarchive 的绝对路径>' \
     --output '/Users/<vm_name>/Downloads/<应用名>-upload-<时间戳>.ipa' \
     --app-id '<数字 App ID>' \
     --issuer-id '<issuer ID>' \
     --key-id '<key ID>' \
     --private-key '<绝对 AuthKey_*.p8 路径>' \
     --attempt-file '/Users/<vm_name>/Downloads/utm-22-<run-id>-<version>-<build>.upload-attempt.json'
   ```

3. 脚本必须先用 `/v1/apps/<id>` 验证 API App 的 Bundle ID，再用支持集合读取的 `/v1/builds` 对同一 App、版本和构建号做只读查询：仅零条才允许创建；任何已有 Build（包括多条）都记录到 attempt 并拒绝新建。不得把仅支持单条 GET 的 `/v1/buildUploads/<id>` 当作集合查询。创建前已写入 `UPLOAD_ATTEMPT_ID`，POST 返回后立即写入 `BUILD_UPLOAD_ID`；POST 结果不明时按 5/10/20 秒只读重查 `/v1/builds`，发现 Build 则记录 `recovered_after_create_result_unknown`，否则记录 `create_result_ambiguous`，两种结果都禁止再次 POST。只有新建分支才以 `com.apple.ipa` 创建 `buildUploadFiles`，严格按 Apple 返回的 offset、length、method 和 headers 上传分片，最后只提交最小 `uploaded=true`。
4. 记录 IPA SHA-256，并对同一 `BUILD_UPLOAD_ID` 做 15/30/60/120 秒有界只读轮询，持续读取关联 Build。只有以下五项同时满足才完成：

   ```text
   BUILD_UPLOAD_FINAL_STATE=COMPLETE
   BUILD_PROCESSING_STATE=VALID
   UPLOAD_ATTEMPT_ID=<stable-id>
   BUILD_UPLOAD_ID=<id>
   SCRIPT_EXIT=0
   ```

5. 成功后记录 `API_UPLOAD=yes`。此状态只表示构建已被 App Store Connect 接收并处理，不代表已提交审核或发布。

## Game Center 精确恢复分支

仅当当前 App Store Connect 版本逐字显示：

```text
You must add the com.apple.developer.game-center key in Xcode.
```

并且旧 Archive 的签名与 Profile 都确认缺少 `com.apple.developer.game-center` 时进入：

1. 保留营销版本，使用 Xcode 界面把构建号设为旧构建号加 `1`；同时把仓库权威声明源中的 build 更新为同一值并重新生成/读取 `Generated.xcconfig`，然后重复“四层来源一致”检查。只改 Xcode 显示值不合格。
2. 在 `Runner` → `Signing & Capabilities` 中点击 `+ Capability`，选择唯一的 `Game Center`；重新下载/选择当前 App Store Profile，并确认签名页无红黄警告。
3. 在任何点击前生成全新的稳定 `GAME_CENTER_ARCHIVE_ATTEMPT_ID` 和独立 mode-600 archive ledger，保存旧/新构建号、Game Center capability/profile 证据和新的 Organizer 前置 manifest；再按主线相同 `prepared -> clicking -> clicked_result_unknown -> verified` 状态机通过 `Product` → `Archive` 创建一个新 Archive。禁止复用原 `ARCHIVE_ATTEMPT_ID`、覆盖或重签旧 Archive，也禁止使用命令行构建或导出。
4. Organizer 中新 Archive 的实际 marketing version 必须不变，实际 build 必须严格等于旧 build + 1；重新生成目录 manifest 并记录新的 `ARCHIVE_MANIFEST_SHA256`。再分别验证签名 entitlements 与解码后的 Profile 都含 `com.apple.developer.game-center=true`，然后记录：

   ```text
   SIGNED_GAME_CENTER=verified
   PROFILE_GAME_CENTER=verified
   ```

5. 只把这个新 Archive 交给上方相同的 `prepare` / `distribute` 路径，并因构建号已加一而生成新的稳定 `UPLOAD_ATTEMPT_ID`。若 Xcode 无法生成包含 Game Center 的 App Store Profile，自动刷新同一 App Store Profile、重新选择同一 Team 并完整做三轮安全修复，每轮都独立回读；三轮后仍缺少 entitlement 才记录为外部权限状态并进入最后故障卡，不改用 Development、Ad Hoc 或 Enterprise Profile。

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
XCODE_GUI_RECOVERY=verified|not_needed
ARCHIVE_DISTRIBUTION=verified
APP_STORE_CONNECT_APP=verified
IPA_PAYLOAD=verified
IPA_SWIFT_SUPPORT=verified
IPA_SHA256=verified
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

使用 Game Center 恢复分支时，额外要求 `GAME_CENTER_ARCHIVE_ATTEMPT_ID=<new-stable-id>`、新 Archive 实际构建号等于旧值 +1、`SIGNED_GAME_CENTER=verified` 和 `PROFILE_GAME_CENTER=verified`。

记录 `UTM_22=verified`，结束 `utm-22`，保留同一 VM、当前构建上下文和既有 guest Edge，立即继续 `utm-23`；不得等待用户确认。阻断、失败或未完成状态不得交接。

## 阻断条件

- VM/IP/SSH 用户、workspace、Xcode 实际 bundle、账号、Profile、Team、证书或 Archive 不能唯一匹配：对可安全恢复的子项完整执行三轮修复且每轮全量复验；若属于外部所有权或不可安全改动的冲突，则只做三轮独立只读全量复验。三轮仍不唯一才以 `utm-22-context-mismatch` 进入最后故障卡，不猜测。
- Xcode 签名页出现红黄警告、Archive 失败或 Organizer 候选不一致：先刷新同一 profile、恢复签名、读取当前 attempt 日志并确定性恢复；只有恢复穷尽才以 `utm-22-archive-state` 进入最后故障卡，未验证前不进入 API 上传。
- API Key 缺失、无权访问目标 App、App ID 与 Bundle ID 不匹配：先重新读取同一 `prod.yml`、同一 App API 和文件权限并复验；仍为权威缺失/权限冲突才以 `utm-22-api-context` 进入最后故障卡，不尝试其他账号或 App。
- Build Upload 为 `PROCESSING` 时按 15/30/60/120 秒窗口继续有界只读轮询；超时仍未进入终态则保留当前 `UPLOAD_ATTEMPT_ID`/`BUILD_UPLOAD_ID`，完成同版本查询后才以 `utm-22-build-upload-processing` 进入最后故障卡。不得新建第二个上传，也不得切换到 Xcode GUI 或 Transporter 重传同一版本/构建号。
- `FAILED` / `INVALID` 时保留 Apple 返回的非敏感错误，先自动分类唯一可修复分支；只有 Game Center 精确错误可进入本技能规定的构建号 +1 恢复，其余确实不可自动修复时才以 `utm-22-build-upload-failed` 进入最后故障卡。`90426` 表示缺少 `SwiftSupport`；`90433` 表示 Swift dylib 不是正确的 Apple 原始签名，不得复制 App 内已重签的 dylib兜底。
- 不点击 `Add for Review`，不提交审核，不发布。
