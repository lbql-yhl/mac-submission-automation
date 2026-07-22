---
name: utm-15
description: Use when the same UTM guest's App Store Connect Business session must open an existing app, obtain its numeric App ID, and register that ID on the matching Notion page.
---

# UTM-15：获取 App ID 并登记 Notion

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
  --stage 'utm-15:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-15' \
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
| Apps/应用误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图；`Back` 回 Apps，按应用名和 `/apps/<App ID>/` 双重定位，记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立定位后仍不唯一才发卡 |
| URL 读取不唯一 | 同一详情页重新读取地址栏/AX URL 三次并交叉验证纯数字段 | 三轮仍无唯一段为 `unrepairable` |
| Notion 现有值冲突 | 重新读取 App Store URL 与 Notion 当前字段；相同幂等完成，空值写入 | 非空不同为外部数据冲突，发卡 |
| API 写入失败 | 保存字段 before，写后独立回读；失败自动还原并复验 | 还原后才发卡 |

## 边界

`utm-15` 接在 `utm-14` 后，完成这一条闭环：

`Business → Apps → 应用名 → 读取 URL 中的数字 App ID → Notion APP_ID： → 保存回读`

只处理已经创建好的应用，不创建应用、不点击 `Add Apps`、不修改 `应用信息`。

## 前置条件

- `utm-14` 已完成，确认 `DAC7_INFO=No_saved`，并确认同一 guest Edge 仍在 App Store Connect `Business` 页面。
- 继续使用同一个 guest、同一个 Microsoft Edge 进程和已有标签页；不启动新浏览器。
- `.env` 中 Notion API 连接可用，`NOTION_ROOT_PAGE_ID` 指向当前宿主机页面，匹配子页面为 `<应用名>-<vm_name>`。
- 通过 Notion API 从该页 `应用信息` 精确读取的应用名用于核对 App Store Connect 应用。

## 硬性规则

- 每次点击、菜单操作或页面变化后等待至少 3 秒，再读取最新截图和状态。
- 页面变化后必须重新定位；不复用旧坐标、旧菜单索引或旧 URL。
- App Store Connect 只点击顶部 `Apps` 和匹配的应用名；禁止点击 `Add Apps` 或其他创建入口。
- App ID 必须从当前应用详情页 URL 读取：要求存在唯一的 `/apps/<纯数字>/` 段；不能猜测、截取页面其他数字或使用旧记录。
- Notion 只更新 `账号信息` 代码块中的 `APP_ID：`；页面没有 `app_id:` 时不要新增该字段。
- 所有 Notion 读写只通过 `scripts/notion_api.py`；不得启动或操作 Chrome Notion、插件、Playwright、CUA、浏览器剪贴板或坐标写入。
- App ID 通过标准输入交给字段级 API 更新；不得放在命令参数或日志中，不得整块替换代码块。

## 操作步骤

### 1. 核对应用并进入详情页

1. 在最新截图中确认当前是 App Store Connect `Business` 页面、账号会话有效、顶部有 `Apps`。若标签/页面首次不可见，保持同一 guest Edge 做三轮相隔至少 3 秒的进程、窗口、标签、VM 与账号独立只读核对；记录 `BROWSER_SESSION_RECHECKS=3` 后仍不匹配才阻断，禁止启动/切换新浏览器进程。
2. 点击顶部 `Apps`，等待至少 3 秒并重新读取；确认已经离开 `Business` 页面并进入 `Apps` 页面。
3. 先执行 `verify-parent`，再用 `read-field --copy` 从匹配 Notion 页 `应用信息` 的精确标签 `'应用名: '` 读取应用名；确认其与 Apps 页面唯一应用名一致后再点击。
4. 等待至少 3 秒并重新读取；确认已进入应用详情页，而不是仍停留在 Apps 列表。
5. 从当前详情页地址栏/AX URL 读取 URL，提取 `/apps/` 后、下一个 `/` 前的纯数字。必须只有一个候选值；否则先按 `utm-15-app-id-url` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。

### 2. 写入 Notion 的 APP_ID

1. 执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，并要求 `<应用名>-<vm_name>`、`账号信息` 和 `APP_ID：` 都唯一。
2. 用 `read-field --copy` 读取 `APP_ID：` 并同时保存整个 `账号信息` before SHA-256；命令只输出字节数和哈希。空值进入写分支；已有相同值记录 `APP_ID_NOTION=equal` 并跳过 `set-field`；已有不同值按 `utm-15-app-id-conflict` 阻断。不要新增 `app_id:`。
3. 仅空值分支把刚提取的纯数字 App ID 放入宿主原生剪贴板，验证字节数/SHA-256；紧接写入前再次验证父页，再执行：

   ```bash
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   pbpaste | python3 scripts/notion_api.py set-field \
     --title '<应用名>-<vm_name>' --heading '账号信息' \
     --label 'APP_ID：' --value-stdin
   ```

4. 不使用 `--replace-existing`。脚本必须只替换该唯一字段、保留代码块其他内容并在 PATCH 后自动回读完全一致。
5. 再运行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，用 `read-field --copy` 回读 `APP_ID：`，确认字节数/SHA-256 与 URL 来源一致且只有一个字段匹配；整个账号区块除该字段外与 before 相同。记录 `APP_ID_NOTION=written` 和 `APP_ID_READBACK=exact`。
6. equal 分支也必须在一次新的 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'` 后独立回读并记录 `APP_ID_READBACK=exact`。两个分支结束后执行 `pbcopy </dev/null` 并要求 `pbpaste` 为空。

### 3. 保存和最终验证

1. API 返回必须是 `changed=true` 或已有相同值时的幂等 `changed=false`，不得有冲突错误。
2. 重新执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，并再次读取 `APP_ID：`；要求值准确、字段唯一。
3. `set-field` 的写后回读保证代码块其他内容未被整块覆盖；不得修改 `应用信息`。
4. 只有最终 API 回读仍匹配 App ID，才报告完成。

## 完成标准

```text
UTM_15=verified
APP_STORE_CONNECT=focused
APPS=opened
APP_DETAIL=opened
APP_ID=extracted
APP_ID_NOTION=equal|written
APP_ID_READBACK=exact
```

## 阻断条件

- `BROWSER_PROCESS_GUARD=blocked`
- `appstoreconnect_tab_missing`、`appstoreconnect_page_mismatch` 或 `account_session_missing`
- `business_return_not_verified`
- `dac7_info_not_verified`
- `apps_target_missing`、`apps_target_ambiguous` 或 Apps 点击最多重试一次仍未打开
- 应用名与 Notion 应用名不一致
- 当前详情 URL 没有唯一的 `/apps/<纯数字>/` 段
- Notion API 父页/页面/标题/代码块不匹配、`APP_ID：` 不存在或不唯一、已有值冲突
- API 写入或写后回读失败，或发现 `应用信息`/其他账号字段发生非预期变化

发生阻断时立即暂停新的副作用，不猜值、不创建应用、不新增 `app_id:`；先按对应 `utm-15-*` stage 执行本技能矩阵并独立复验，恢复穷尽或外部冲突仍存在时才发送最后故障卡。

## 连续交接

仅当本技能全部完成检查通过时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-16`；不得等待用户确认。阻断、失败或未完成状态不得交接。
