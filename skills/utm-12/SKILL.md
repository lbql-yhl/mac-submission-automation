---
name: utm-12
description: Use when continuing the same signed-in UTM macOS guest after utm-11 and the workflow must handle Apple Developer membership, App ID registration, or App Store Connect app creation.
---

# UTM-12

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
  --stage 'utm-12:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-12' \
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
| 页面/下拉/字段误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图，`Escape`/`Cancel` 回到当前表单锚点，重新唯一定位；记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立定位后仍失败才发卡 |
| 协议接受结果不明 | 只读检查协议状态；已接受继续，证明未提交才允许一次重试 | 仍 ambiguous 不重复接受 |
| App ID/App 创建中断 | 只读按 Bundle ID/App ID 查询；唯一匹配且字段一致即幂等完成，从第一个缺项续做 | 冲突/多候选为 `unrepairable` |
| Notion 写入失败 | 保存 before，写后独立回读；失败自动还原并复验 | 还原后才允许发卡 |

## 一、硬性前提

- 只使用当前已经打开的 UTM 虚拟机和 Microsoft Edge；禁止启动、重启或切换新的浏览器进程。
- Notion 只通过宿主机项目脚本 `scripts/notion_api.py` 访问；`.env` 的 `NOTION_ROOT_PAGE_ID` 必须指向当前宿主机页面，匹配子页面为 `<应用名>-<vm_name>`。
- 每次点击、切换标签页、粘贴、下拉选择后，至少等待 3 秒，再读取最新截图和状态。
- 每次页面变化后重新定位坐标，禁止复用旧坐标。
- 页面滚动必须慢速、小步进行；每次滚动后等待并重新确认。
- 表单文字使用宿主机原生剪贴板和虚拟机内右键菜单 `Paste`，不要逐字键入。
- 不在技能、日志或回复中记录密码、短信验证码、代理密码、完整短信链接或其他秘密。
- 本技能是自动化流程，不等待用户确认；在 `Register` 和 `Create` 前执行自检，字段正确且页面状态匹配后直接点击，并在点击后验证结果。

## 自动自检原则

- 需要确认的是页面状态和字段，不是人工授权：账户、应用名、Bundle ID、SKU、平台、语言和权限都必须与实时来源一致。
- 自检通过就自动继续，不发送“请确认”式停顿。
- 自检失败、页面不匹配或结果无法验证时暂停后续副作用，先按对应步骤的 `utm-12-*` stage 执行本技能自动恢复矩阵并独立复验；只有恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。

## 二、协议与会员信息

1. 先只读查找同一 guest Edge 内已有且唯一的 `developer.apple.com/account/` 标签；存在时只切换，不重复粘贴。确实不存在时才新建一个 tab，调用 `OP-BROWSER-URL-NO-SCHEME` 并执行 `printf '%s' 'developer.apple.com/account/' | python3 scripts/shared_operations.py browser-url --allow-bare`；只有 `BROWSER_URL_CLIPBOARD=verified` 且原生菜单的 `Paste and Go` 已蓝色高亮才确认一次，粘贴后立即清空剪贴板。
2. 等待至少 3 秒，确认 URL、`Account` 标题和已登录账户正确。
3. 如果出现 `The program license agreement has been updated`、`Agreement Update` 或类似提示：
   - 点击 `Review agreement`。
   - 等待并确认协议页面已经打开。
   - 勾选后先持久化稳定 `AGREEMENT_ATTEMPT_ID`、账号/Team/协议版本和 `status=planned`；重新读页面仍完全一致才更新为 `clicking` 并点击 `Agree` 一次。
   - 等待返回 Account 页面，确认该协议版本提示消失并显示 accepted/completed；结果不明只查询同一 attempt，不二次点击。协议控件或返回结果不匹配时先按 `utm-12-agreement-result` 恢复。
4. 如果没有协议提示，用两次相隔 3 秒的 Account/协议状态读取证明最新协议已接受，记录同一 `AGREEMENT_ATTEMPT_ID=<existing>` 和 `AGREEMENT_ACCEPTED=verified`；入口消失本身不够。
5. 从 Account 页面向下慢速滚动到 `Membership details`，读取页面上可见的：
   - `Team ID`
   - `Renewal date`
6. 不要快速拖到底部，也不要从其他页面推断这两个值。

## 三、Notion 登记 Team ID 和 Renewal date

1. 在宿主机先执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`；不匹配时先按 `utm-12-notion-parent` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
2. 通过 API 唯一解析 `<应用名>-<vm_name>`、`账号信息` 标题及其紧随的代码块；禁止使用 Chrome、Notion 插件、Playwright、CUA、坐标或浏览器剪贴板读写 Notion。
3. 只修改 `账号信息` 中的精确标签：
   - `team ID:`
   - `Renewal date：`
4. 每个值分别放入已验证的宿主原生剪贴板，记录字节数和 SHA-256 但不打印值。每次 `set-field` 前都重新执行：

   ```bash
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   pbpaste | python3 scripts/notion_api.py set-field \
     --title '<应用名>-<vm_name>' --heading '账号信息' \
     --label '<精确标签>' --value-stdin
   ```

5. 不使用 `--replace-existing`。已有相同值视为幂等成功；已有不同值时先按 `utm-12-membership-conflict` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。脚本必须保留空行、所有其他字段和 `应用信息`，写后自动回读完全一致。
6. 每个写入后再次运行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，再分别用 `read-field --copy` 回读；比较字节数/SHA-256 与 Apple 页面来源一致，且另一字段/整个账号区块 before hash 未发生非预期变化。未确认回读成功不得继续。

## 四、从 Account 进入 App Store Connect

1. 回到同一个 Edge 的 Apple Developer Account 标签页。
2. 从当前位置慢速向上滚动，每次小步移动并重新确认，直到页面顶部的 `Apps` 入口可见。
3. 点击 `Apps`，等待并确认进入 `appstoreconnect.apple.com/apps`。
4. 在 Apps 页面点击 `Add Apps`，等待并确认出现 `New App` 表单。
5. 点击 `Register a new bundle ID in Certificates, Identifiers & Profiles`，等待并确认进入 `Register an App ID` 页面。

## 五、注册 App ID

1. 通过 `scripts/notion_api.py read-field --copy` 从同一匹配页的 `应用信息` 分别读取以下精确标签，不打印值：
   - `应用名` → App ID 表单 `Description`
   - `正式包名` → App ID 表单 `Bundle ID`
   当前模板标签参数分别使用 `'应用名: '` 和 `'正式包名: '`（包含冒号后的空格）；零个或多个匹配时先按 `utm-12-app-fields` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
2. 在 `Description` 输入框中使用原生剪贴板：
   - 将应用名写入宿主机剪贴板并用 `pbpaste` 核对。
   - 点击输入框，等待。
   - 右键输入框，等待最新菜单。
   - 点击当前菜单中可见的 `Paste`，等待并核对字段。
3. 对 `Bundle ID` 重复同样流程。若 `Paste` 灰色不可用：
   - 重新写入剪贴板并核对。
   - 重新点击输入框。
   - 重新打开右键菜单。
   - 只使用新截图中可见的 `Paste`。
4. 点击 `Continue` 前必须确认：
   - `Description` 与 Notion 的应用名完全一致。
   - `Bundle ID` 与 Notion 的正式包名完全一致。
   - `Continue` 已变为可点击状态。
5. 点击 `Continue`，等待并确认 `Confirm your App ID` 页面显示相同的 Description 和 Bundle ID。
6. 在 `Register` 前自动自检 Description、Bundle ID 和确认页内容完全匹配。
7. 自检后先查询 Identifiers 列表/当前确认页并按精确 Bundle ID 分类：一个完全相同条目视为 existing exact 并不点击；零条时原子持久化 `APP_ID_REGISTER_ATTEMPT_ID`、Description/Bundle ID hashes、`status=planned`，重新确认页面后更新 `clicking` 并点击 `Register` 一次；多条或非空冲突停止。
8. 点击结果不明时只回到 Identifiers 列表查询同一 Bundle ID，禁止再次 Register。成功必须唯一新行同时显示正确应用名/Bundle ID，并将同一 attempt 更新为 `registered`；记录 `APP_ID_REGISTERED=verified`。

## 六、刷新并创建 App Store Connect 应用

### 6.1 回到 Apps 页面并刷新

1. 切换到同一个 Edge 的 `App Store Connect` 标签页，确认 URL 为 Apps 页面。
2. 当页面需要重新加载、旧的 `New App` 模态框状态异常或用户要求刷新时，使用浏览器地址栏左侧的圆形箭头刷新按钮。
3. 对该圆形箭头只点击一次，等待至少 6 秒并重新读取。页面仍 loading 时继续等到 10 秒；只有两次只读状态都证明第一次点击根本未触发导航，才允许一次新的恢复 attempt，禁止双击。
4. 刷新成功的判据：
   - `New App` 模态框关闭或页面重新渲染。
   - 页面回到 `Apps`，并能看到 `Add Apps` 或 Apps 列表。
5. 如果页面暂时空白，继续等待 4–6 秒，再重新读取状态；不要立即重复点击。

### 6.2 填写 New App

1. 在 Apps 页面先按应用名查找现有条目并打开候选核对 Bundle ID：唯一完全匹配为 existing exact，直接使用该详情页；零匹配才点击 `Add Apps`；多匹配或同名不同 Bundle ID 是冲突。
2. 按以下顺序填写并逐项确认：
   - 勾选 `iOS`。
   - `Name`：粘贴 Notion 的应用名。
   - `Primary Language`：选择 `English (U.S.)`。
   - `Bundle ID`：打开下拉框，选择唯一的、刚刚注册的 `<应用名> – <正式包名>`。
   - `SKU`：粘贴 Notion 的正式包名。
   - `User Access`：选择并确认 `Full Access`。
3. 选择 Bundle ID 前必须先确认 App ID 已完成 `Register`；未完成 Register 时，下拉框可能只有 `Choose`，没有可选项。
4. 如果下拉框没有展开：
   - 点击当前截图中实际可见的下拉箭头。
   - 等待并重新读取。
   - 必要时先点击下拉框，再使用标准 `Down` 键检查选项。
   - 仍无选项时先按 `utm-12-bundle-id-option` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；不要手填 Bundle ID，回调后检查同一 App ID 是否真的已注册。
5. `Create` 前自动核对所有字段，特别是平台、语言、Bundle ID、SKU 和 Full Access。
6. 自检通过后原子持久化 `APP_CREATE_ATTEMPT_ID`、Name/Bundle ID/SKU/platform/language/access hashes 和 `status=planned`；独立回读表单完全匹配后更新 `clicking` 并点击 `Create` 一次。结果不明只查询 Apps/详情页，不再次 Create。
7. 对新建或 existing exact 分支都验证 App Store Connect 应用详情页出现：
   - 正确的应用名。
   - `iOS App Version 1.0`。
   - `Distribution` 等应用导航项。

## 完成检查

只有全部验证通过才报告完成：

```text
UTM_12=verified
DEVELOPER_ACCOUNT=opened
NOTION_MEMBERSHIP_FIELDS=updated
APP_ID_FORM=confirmed
APP_ID_REGISTERED=verified
AGREEMENT_ATTEMPT_ID=<stable-or-existing>
APP_ID_REGISTER_ATTEMPT_ID=<stable-or-existing>
APP_CREATE_ATTEMPT_ID=<stable-or-existing>
APP_STORE_APP=created_or_existing_exact
```

协议分支执行时额外报告：

```text
AGREEMENT_REVIEW=opened
AGREEMENT_ACCEPTED=verified
```

## 常见阻断

- `account_page_missing`：Account 页面或登录账户不匹配。
- `agreement_page_missing`：协议提示存在但 Review 页面未打开。
- `notion_page_missing`：API 父页、匹配 Notion 页面、标题或代码块找不到或不唯一。
- `notion_save_unverified`：Notion API 写后回读不一致。
- `bundle_id_not_available`：App ID 尚未 Register，或 Bundle ID 下拉框没有唯一选项。
- `navigation_error`：标签页切换或页面导航失败。
- `field_mismatch`：表单字段与 Notion 不一致。
- `result_not_verified`：点击后没有看到预期结果页面。

发生阻断时暂停新的副作用，先按对应 `utm-12-*` stage 执行本技能矩阵的自动诊断、修复和独立复验；只有恢复穷尽或外部状态不可修复时，才携带恢复证据发送最后故障卡。不要猜测值、跳过检查或继续点击。

## 连续交接

仅当本技能全部完成检查通过时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-13`；不得等待用户确认。阻断、失败或未完成状态不得交接。
