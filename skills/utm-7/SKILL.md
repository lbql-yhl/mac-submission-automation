---
name: utm-7
description: Use after utm-6 when the prepared UTM macOS guest must sign in to the Apple Account already registered on its matching Notion page.
---

# UTM-7

本技能只替换 guest macOS System Settings 内的 Apple Account 登录。`utm-10`/`utm-18` 的 Apple Developer/Edge 网页会话是独立流程，继续按各自技能使用既有 Edge 会话和 Notion API-only 凭据读取，不调用本 helper。

## 全局自动恢复与最后故障卡规则

本技能强制继承共享重复操作记忆；Apple Account 登录本身只调用 `OP-APPLE-ACCOUNT-LOGIN-SCRIPT`。`OP-NATIVE-PASTE`、`OP-BROWSER-URL-NO-SCHEME`、`OP-APPLE-PHONE-OTP`、`OP-FIXED-PASSWORD-1234` 和 `OP-USER-CONFIRMATION` 仍是共享合同中的唯一操作定义，但仅由其各自适用的后续技能调用，utm-7 不直接执行这些 GUI 操作。不得在本技能内发明简化版或冲突步骤。可安全修复的故障必须做满三轮“诊断→实际修复→独立复验”；只有不可逆动作、不能安全重复写入或外部不可修复状态，才改做三轮独立只读复核。少于三轮时运行时拒绝发卡。

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
  --stage 'utm-7:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-7' \
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
| Notion 字段/页面不唯一 | 同一父页、同一页面和同一 heading 做三轮 API 只读重读；只接受唯一、非空字段 | 三轮仍缺失/冲突才 `unrepairable` |
| SSH/脚本上传或哈希失败 | 锁定同一 VM/IP/用户，恢复 Remote Login、同一公钥和脚本目录，三轮 BatchMode、哈希和编译独立复验 | 三轮仍失败才 `exhausted` |
| 邮箱/密码/电话/SMS 字段异常 | 重新读取同一 Notion 页面，检查字段字节数/格式，不把值放入 argv 或日志；三轮后再分类 | 权威字段持续缺失、冲突或无效才 `unrepairable` |
| 2FA/随机安全提示 | helper 在同一 guest 内重读当前 AX 树；按当前唯一电话尾号和最新 SMS URL 重新取码；有时间按时间最新、无时间按页面顺序最后一条；不重用旧码 | 零/多号码、无法判定最新码、CAPTCHA、锁号或未知挑战三轮后 `unrepairable` |
| 邮箱成功/重开复核 | 先只读确认详情页邮箱，再关闭并重开同一 System Settings，重新进入 Apple Account 详情页复核；失败只重试同一 VM | 第二次邮箱复核三轮仍失败才发卡 |

## Preconditions

- Run only after `utm-6` reports `PROXY_EGRESS=verified`, `ZSHRC=verified`, and `UTM_6=verified`.
- Resolve the current `vm_name` from the active Feishu run or the target VM already used by `utm-6`; never generate a new name.
- The matching Notion registration page is named `<应用名>-<vm_name>` and already contains the `账号信息` block.
- The target VM is running, logged in as the VM-named user, and reachable by the inherited BatchMode SSH identity.
- `${PROJECT_ROOT}/.env` 已配置可读当前父页面的 `NOTION_TOKEN` 与 `NOTION_ROOT_PAGE_ID`。
- Notion 只读来源固定为项目根目录下的 `scripts/notion_api.py`；不得用宿主 Chrome、Notion 插件、Playwright、CUA、坐标或浏览器剪贴板读取 Notion，也不得打印凭据。

## Notion API 只读规则

1. 每次读取当前页面前，先在 `${PROJECT_ROOT}` 执行：

   ```bash
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   ```

2. 页面标题固定为 `<应用名>-<vm_name>`。不要使用 `read-field --copy`、剪贴板或浏览器读取敏感字段；由 `scripts/utm_7_login.py` 通过同一 `api_from_env()` 客户端在当前进程内读取 `账号信息` 中的 `邮箱：`、`修改后的密码：`、`初始密码：`、`电话：` 和 `电话短信接收平台：`。外部命令输出只允许出现 ID、计数、SHA-256 和非敏感状态标记，不得输出字段值。
3. 每个值只在即将使用时读取。后续进入短信分支时必须重新执行 `verify-parent` 并重新读取电话与短信链接，不得复用登录阶段或旧任务的值。

## Workflow

1. 按 **Notion API 只读规则** 执行 `verify-parent`，再确认 API 能唯一匹配 `<应用名>-<vm_name>` 的 `账号信息`。若页面、标题、heading、紧随其后的 code block 或字段不能唯一匹配，暂停后续登录操作，先按 `utm-7-notion-fields` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；不得读取或编辑浏览器中的 Notion 页面。
2. 不启动 UTM Computer Use、`node_repl`、`@oai/sky`、截图点击或 guest Terminal。只通过继承的 BatchMode SSH 轻量核对同一 `vm_name`、IP、最终用户、`HOME` 和项目 SSH 公钥指纹；连接失败时只恢复同一 VM 的 SSH，不得切换 VM。
3. 在项目根目录执行：

   ```bash
   eval "$(python3 scripts/preflight.py --project-only --emit-shell)"
   python3 scripts/utm_7_login.py \
     --parent-title '<宿主机名称>' \
     --page-title '<应用名>-<vm_name>' \
     --vm-ip '<当前精确 VM IP>' \
     --vm-user '<vm_name>'
   ```

   命令参数只允许非敏感的宿主机名、页面标题、IP 和用户名；不得把账号、密码、电话或短信链接放入命令参数。`scripts/utm_7_login.py` 先通过 `scripts/notion_api.py` 同一 API 客户端验证父页并读取 `邮箱：`、非空 `修改后的密码：`（为空才读取 `初始密码：`）、`电话：` 和 `电话短信接收平台：`，所有值只留在当前进程内存。
4. 脚本把项目内四个 helper 上传到 guest 的 `/Users/<vm_name>/Downloads/`，用 SHA-256 独立核对后，通过 SSH 标准输入 JSON 调用 `apple_account_login.py --stdin-json`。JSON 不进入 argv、剪贴板、日志或临时明文文件；guest 入口每次启动先结束旧登录实例，再加载同目录最新 helper。上传、哈希或 BatchMode 失败只修复同一目标并做三轮独立复验。
5. guest helper 全程使用 Accessibility API，不使用视觉或人工操作：自动打开/复用 System Settings，填写邮箱和密码，提交 Continue，匹配唯一电话尾号，获取当前短信页面的最新验证码并提交；Mac Password 固定使用 `1234`。`Don't know passcode?`、`Enter Passcode Later` 和 `Don't Merge` 任意一个出现即自动处理；AX 瞬态错误只重读同一页面。
6. 邮箱在启动后的任何轮次、验证码后或安全提示期间出现即视为登录成功，跳过不必要的后续步骤。首次确认后自动关闭 System Settings，重新打开并进入 Apple Account 详情页再次确认邮箱；第二次确认成功后保留 System Settings 打开。脚本必须输出 `APPLE_ACCOUNT=verified` 和 `UTM_7=verified`，并以退出码 `0` 结束。
7. 失败时只读归类同一 VM/账号/页面：账号或邮箱不匹配、CAPTCHA、锁号、未知挑战、无法判定最新验证码、脚本退出非零、第二次邮箱复核失败均先按本技能矩阵自动恢复三轮；恢复穷尽后才进入最后故障卡。成功不得依赖截图、弹窗消失、按钮点击或“脚本已启动”作为证据。

## Guardrails

- Do not create, rename, delete, or edit Notion pages or fields.
- Do not use the Feishu desktop app as a data source.
- Do not report, echo, screenshot-share, or persist the Apple Account password.
- Never reuse cached account, phone, SMS URL, or OTP data after the Notion account information changes; re-read through `scripts/notion_api.py` and do not expose any full credential, phone number, SMS URL token, or verification code.
- Do not use Computer Use, screenshots, coordinates, context menus, clipboard sharing, `type_text`, keyboard shortcuts, or manual input for Apple Account credentials or OTP. All such actions belong to `OP-APPLE-ACCOUNT-LOGIN-SCRIPT` and its guest Accessibility helper.
- Do not place account values in SSH argv, shell exports typed by an operator, guest files, logs, cards, screenshots, or project skill text. The only approved transport is the orchestrator's SSH-stdin JSON handoff.
- Do not treat helper startup, a dismissed dialog, a visible sidebar name, or a zero exit from `scp` as login success. Require the helper's `APPLE_ACCOUNT=verified`, exact email match, close/reopen confirmation, `UTM_7=verified`, and exit code `0`.
- Do not change UTM settings, Clipboard Sharing, VM identity, network, proxy, sharing, users, or shell configuration. Repeated paste attempts are not a reason to enter the UTM settings.
- Handle the known phone selection, SMS-code retrieval, and current-guest Mac Password prompt automatically with live matching Notion data and fixed VM password `1234`. For CAPTCHA, account lock/disabled state, an unknown challenge, an unclassifiable latest OTP, or an account/phone mismatch, first run the matrix's read-only page/account classification and 5/10/20-second live-source checks. Only a proven external/unrepairable state may invoke the last `notify-fault`/`wait-decision` exit; a fresh `manual_continue` still re-runs the same live-source recovery rather than serving as evidence.
- If the guest is not the target VM or the active user is not `<vm_name>`, refocus only the same run's exact VM and repeat the read-only run/VM/user identity checks through `utm-7-guest-identity` without selecting another VM. Only an exhausted mismatch proven to be external ownership conflict may send the last global fault card; do not enter credentials first.

## Completion

Report only the VM name, the signed-in Apple Account display name/email (email may be partially redacted), and `APPLE_ACCOUNT=verified`. After the current guest/account detail page is verified with no pending sign-in error, record `UTM_7=verified`. Any blocked result must first exhaust the matching automatic recovery matrix and independently reverify before entering the last global fault-card stage; then report only `APPLE_ACCOUNT=blocked` and the visible blocker category without secrets.

## 连续交接

仅当本技能全部完成检查通过并记录 `UTM_7=verified` 时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-8`；不得等待用户确认。阻断、失败或未完成状态不得交接。
