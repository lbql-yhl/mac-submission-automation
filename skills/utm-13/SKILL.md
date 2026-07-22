---
name: utm-13
description: Use after utm-12 when the same signed-in UTM macOS guest must create an Apple Distribution certificate and an App Store Connect provisioning profile in the existing Microsoft Edge session.
---

# UTM-13

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
  --stage 'utm-13:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-13' \
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
| Certificates/Profile 页面误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图，`Escape`/`Back` 回到资源列表并重新定位；记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立定位后仍不唯一才发卡 |
| 证书下载/导入中断 | 查当前 Team 证书和本轮下载文件；已导入即完成，证明未导入才重开文件一次 | 归属/结果不明为 `unrepairable` |
| 文件选择器/Keychain 下拉错选 | `Cancel`/`Escape` 回到上传或 Add Certificates；重新选择精确 CSR/System 并回读 | 三轮可逆修复且每轮独立回读后仍不符才发卡 |
| Profile 生成结果不明 | 按 App ID、证书、名称查询唯一 profile；存在即完成，不重复生成 | 多候选/冲突才发卡 |

## 硬性规则

- 不启动、重启或切换新的浏览器进程；继续使用当前 guest Edge。
- 每次点击、切换标签页、滚动或粘贴后等待至少 3 秒，再读取最新截图和状态。
- 页面变化后重新定位目标，不复用旧坐标。
- 进入下一步前必须验证当前页面、账户/Team ID、目标控件和按钮状态。
- 应用名、CSR 路径等文本使用宿主机原生剪贴板并通过目标输入框右键菜单 `Paste`；不得手动输入来源值。
- Notion 应用名只通过 `${PROJECT_ROOT}/scripts/notion_api.py` 读取；不得用宿主 Chrome、Notion 插件、Playwright、CUA、坐标或浏览器剪贴板读取 Notion。
- Keychain 授权提示只使用当前 guest 固定密码 `1234` 的原生剪贴板/右键 `Paste` 路径；自动核对四个圆点并点击唯一蓝色授权按钮，不询问用户，不把密码写入命令、脚本或日志。
- 页面、账户、CSR、证书或 App ID 不匹配时暂停后续副作用，先按 `utm-13-precheck` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。

## 1. 进入 Certificates

1. 获取 UTM 最新截图，切换到已有的 `Certificates, Identifiers & Profiles` Edge 标签页。
2. 等待并确认页面属于 Apple Developer，URL 位于 `developer.apple.com/account/resources/`，账户和 Team ID 正确。
3. 点击左侧 `Certificates`。
4. 等待并确认 URL 类似 `developer.apple.com/account/resources/certificates/list`，页面标题为 `Certificates`。

## 2. 创建并导入 Apple Distribution 证书

先继承 `utm-9` 的 `CSR_ATTEMPT_ID`、固定 `CSR_PATH` 与两轮稳定 SHA-256，显式私钥 SSH 只读运行 `openssl req -in ... -noout -verify`；全部匹配才记录 `CSR_DISK=verified`。再用两次只读 `security find-identity -v -p codesigning` 盘点 guest 有效签名身份。Certificates 网页有一行但 guest 没有对应私钥/有效 identity 不算可用。

若网页与 guest 恰好有当前 Team 的唯一有效 Apple Distribution 证书，且签名 identity 唯一匹配，记录 `CODESIGN_IDENTITY=verified` 并跳到第 3 节；没有时按以下步骤执行：

1. 点击 `Create a certificate`。
2. 选择 `Apple Distribution`，确认该选项已勾选后点击 `Continue`。
3. 在上传页点击 `Choose File`，打开 guest Desktop，只选择继承的精确 `/Users/<vm_name>/Desktop/CertificateSigningRequest.certSigningRequest`；原生选择器显示的字节数/修改时间必须与 `CSR_DISK=verified` 一致，再点击 `Open`。
4. 确认 CSR 文件名显示在页面上，点击 `Continue`。
5. 点击前先用显式私钥 SSH 保存 guest Downloads 的常规文件清单/哈希。点击 `Download` 一次，等待后重新盘点；要求相对 before 恰好新增一个常规非符号链接、非空且可由 `security verify-cert`/证书解析器读取的 CER，记录 `CERT_DOWNLOAD_NEW_COUNT=1` 和稳定 SHA-256。不能按固定文件名选择旧文件。
6. 打开这一个新 CER 一次；结果不明先检查 Add Certificates 窗口与 Keychain 状态，不重复打开。
7. 在 `Add Certificates` 对话框中把 `Keychain` 从 `login` 切到 `System`：打开下拉框，按一次 `Down`，等待至少 3 秒并重读当前高亮；若为 `iCloud`，再按一次 `Down`，再次等待/重读，只有此时高亮精确为 `System` 才按 `Return`。禁止一次发送多个 Down。
8. 确认字段显示 `Keychain: System` 后点击 `Add`。
9. 处理 Keychain 授权提示时调用 `OP-FIXED-PASSWORD-1234`：先确认弹窗属于当前 `<vm_name>` guest 的本次证书导入，按 `OP-NATIVE-PASTE` 粘贴固定值，验证四个圆点，自动点击唯一蓝色授权按钮并确认弹窗关闭。未知或归属不明的弹窗先暂停输入，重读窗口、进程、证书导入 attempt 和 guest 归属三轮；只有三轮独立复核仍不能归属时才使用当前 run 的最后故障卡出口。
10. 打开 Keychain Access 的 `System`，确认出现当前 Team 的 `Apple Distribution` 证书；随后用两次新 SSH 运行 `security find-identity -v -p codesigning`，要求恰好一个当前 Team 的有效 Apple Distribution identity，私钥关联可用，记录 `CODESIGN_IDENTITY=verified`。红色“不受信任”行或只有证书没有 private key 都不能单独作为成功。

## 3. 打开 Profiles 并选择 App Store Connect

1. 返回 guest Edge，点击 `All Certificates`，等待并确认回到 Certificates 列表。
2. 点击左侧 `Profiles`，确认 Profiles 页面可见。
3. 先按 profile 名、Team、App ID、Type 查询现有 Profiles：唯一完全匹配时打开并验证，直接走 Download and Install；零匹配才点击 `Generate a profile`；多条/同名冲突不猜。
4. 慢速滚动到 `Distribution`，选择 `App Store Connect`。
5. 重新读取截图，确认 `App Store Connect` 单选框已填充，再点击右上角 `Continue`。

## 4. 选择 App ID

1. 确认页面标题为 `Generate a Provisioning Profile`，步骤为 `Select an App ID`。
2. 打开 `App ID` 下拉框，只选择与当前应用和 bundle ID 唯一匹配的 App ID；不得照抄旧运行值。
3. 确认字段显示所选 App ID 且 `Continue` 变为蓝色，再点击 `Continue`。

## 5. 选择证书

1. 确认步骤为 `Select Certificates`。
2. 选择当前 Team 唯一匹配的 `Distribution` 证书；不得照抄旧运行的人员或 Team 值。
3. 确认单选框已选中且 `Continue` 变为蓝色，再点击 `Continue`。

## 6. 命名并生成 Provisioning Profile

1. 确认进入 `Review, Name and Generate`，目标输入框是 `Provisioning Profile Name`。
2. 在 `${PROJECT_ROOT}` 先执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`；父页面不匹配时先按 `utm-13-notion-parent` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
3. 紧接粘贴前执行 `python3 scripts/notion_api.py read-field --title '<应用名>-<vm_name>' --heading '应用信息' --label '应用名: ' --copy`。要求页面、heading、紧随其后的 code block 和字段都唯一，安全元数据表明值非空；命令输出不得包含应用名值。
4. 用 `pbpaste` 做本地只读核对，确认剪贴板中的应用名完整且大小写与当前 `<应用名>` 上下文一致。
5. 聚焦输入框，右键打开菜单，确认 `Paste` 可用后点击 `Paste`；不得用 `super+v` 或手动逐字输入代替。
6. 等待并确认输入框显示完整、大小写一致的应用名，且右上角 `Generate` 为蓝色。
7. 零匹配分支在点击前原子持久化 mode-600 `PROFILE_GENERATE_ATTEMPT_ID`、Team/App ID/certificate/name/type hashes 和 `status=planned`；独立回读完全一致后更新 `clicking` 并点击 `Generate` 一次。结果不明只查询同一 profile，不再次 Generate。
8. 新建或 existing exact 分支都必须在 `Download and Install` 页面确认：`Name` 为应用名、`Type` 为 `App Store`、App ID/Team/certificate 与前述一致、到期日可见，并且右上角 `Download` 可用。

## 完成检查

```text
UTM_13=verified
CERTIFICATES_PAGE=opened
APPLE_DISTRIBUTION_CERT=installed
CERT_DOWNLOAD_NEW_COUNT=1
CODESIGN_IDENTITY=verified
CSR_DISK=verified
PROFILE_GENERATE_ATTEMPT_ID=<stable-or-existing>
PROVISIONING_PROFILE=generated
PROVISIONING_PROFILE_DOWNLOAD=ready
```

## 阻断条件

- `certificates_tab_missing`
- `developer_page_mismatch`
- `account_mismatch`
- `csr_file_missing`
- `certificate_import_failed`
- `system_keychain_not_confirmed`
- `profiles_navigation_error`
- `app_store_connect_not_selected`
- `app_id_not_available`
- `distribution_certificate_not_selected`
- `profile_name_mismatch`
- `profile_generation_failed`
- `result_not_verified`

发生阻断时暂停新的副作用，先按对应 `utm-13-*` stage 执行本技能矩阵并独立复验；恢复穷尽或外部不可修复时才发送最后故障卡。不猜测页面、不启动新浏览器、不用手动输入替代粘贴。

## 连续交接

仅当本技能全部完成检查通过时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-14`；不得等待用户确认。阻断、失败或未完成状态不得交接。
