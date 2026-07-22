---
name: utm-7
description: Use after utm-6 when the prepared UTM macOS guest must sign in to the Apple Account already registered on its matching Notion page.
---

# UTM-7

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
| 设置页/账号行/菜单误点 | 窗口尺寸、焦点或误点后至少 3 秒读取最新截图，`Escape`/`Back` 回到 Apple Account 锚点，作废坐标后重做；记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立定位后仍无法唯一确认才发卡 |
| 邮箱/密码粘贴失败 | 只清目标字段，清空剪贴板写随机哨兵，实时 API 重读后再粘贴并回读；完整做三轮安全重贴且每轮独立回读 | 三轮仍不一致才 `exhausted` |
| 2FA 页面加载/号码选择 | 5/10/20 秒只读等待；电话实时重读，唯一尾号才选；OTP 只取一次新码 | 零/多号码、零/多码、拒绝码为 `unrepairable` |
| CAPTCHA/锁号/未知挑战 | 只读确认页面和账号，不尝试猜答案或换账号 | 直接以只读分类 `--unrepairable` 发卡 |

## Preconditions

- Run only after `utm-6` reports `PROXY_EGRESS=verified`, `ZSHRC=verified`, and `UTM_6=verified`.
- Resolve the current `vm_name` from the active Feishu run or the target VM already used by `utm-6`; never generate a new name.
- The matching Notion registration page is named `<应用名>-<vm_name>` and already contains the `账号信息` block.
- The target VM is running and logged in as the VM-named user.
- `${PROJECT_ROOT}/.env` 已配置可读当前父页面的 `NOTION_TOKEN` 与 `NOTION_ROOT_PAGE_ID`。
- Notion 只读来源固定为项目根目录下的 `scripts/notion_api.py`；不得用宿主 Chrome、Notion 插件、Playwright、CUA、坐标或浏览器剪贴板读取 Notion，也不得打印凭据。

## Notion API 只读规则

1. 每次读取当前页面前，先在 `${PROJECT_ROOT}` 执行：

   ```bash
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   ```

2. 页面标题固定为 `<应用名>-<vm_name>`。只用 `read-field --copy` 读取 `账号信息` 中的 `邮箱：`、`修改后的密码：`、`初始密码：`、`电话：` 和 `电话短信接收平台：`；命令输出只允许出现 ID、计数和 SHA-256，不得输出字段值。
3. 每个值只在即将使用时读取。后续进入短信分支时必须重新执行 `verify-parent` 并重新读取电话与短信链接，不得复用登录阶段或旧任务的值。

## Workflow

1. 按 **Notion API 只读规则** 执行 `verify-parent`，再确认 API 能唯一匹配 `<应用名>-<vm_name>` 的 `账号信息`。若页面、标题、heading、紧随其后的 code block 或字段不能唯一匹配，暂停后续登录操作，先按 `utm-7-notion-fields` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；不得读取或编辑浏览器中的 Notion 页面。
2. Focus the target UTM guest. Use only Computer Use through `node_repl` and the `@oai/sky` wrapper for GUI actions; after every action, fetch a fresh `get_app_state`/screenshot and re-derive targets. UTM may switch between a large and compact window layout, so never reuse coordinates after a resize, menu open, focus change, or loading state. If a marker-side right-click does not open a menu, use the current screenshot to right-click the field center. Do not open the UTM resource library, VM menu, VM edit window, or any UTM setting.
3. Open the guest macOS `系统设置` and select the Apple Account sign-in row at the top of the sidebar. Confirm the page is the guest's System Settings window, not UTM's VM edit window.
4. Paste the email exactly; do not use `type_text`, character-by-character typing, or accessibility `set_value` for credentials:
   - 紧接粘贴前执行 `python3 scripts/notion_api.py read-field --title '<应用名>-<vm_name>' --heading '账号信息' --label '邮箱：' --copy`。要求安全元数据表明值非空，再用 `pbpaste` 做本地只读核对；不得把邮箱放入命令参数或日志。
   - From the latest screenshot, right-click inside the email field at the visible input area; when the right-side `required` marker is visible, use that current marker-side field position, then fall back to the current field center if no menu appears. After the menu appears, wait 3 seconds, take a fresh screenshot, and require the enabled `Paste` row to be visibly blue-highlighted before activation. Re-derive the row from this screenshot every time: extra `Look Up`, `Translate`, `Search With Google`, or `Share` rows can move `Paste` vertically. Never guess or reuse a menu coordinate. A `click_count:0` call is not proof that the pointer moved. If the UTM menu does not reliably accept a coordinate click after the blue state is confirmed, reopen it, press `Down` once to select `Paste`, wait for a fresh screenshot showing the same blue highlight, then press `Return`; this is the verified UTM fallback. Do not use a blind click or treat menu dismissal as success.
   - From a fresh screenshot, right-click the email field and click the visible enabled `Select All` item; then right-click it again and click the visible enabled `Copy` item. Require host `pbpaste` to equal the intended email. Do not use keyboard shortcuts for this verification. If it differs, clear the field/clipboard, re-read the same API field and repeat from fresh screenshots for two bounded recovery cycles; only persistent mismatch after `utm-7-clipboard-recovery` exhaustion may use the last fault-card exit.
5. Paste the password exactly:
   - 先用 `read-field --copy` 读取 `修改后的密码：`，仅根据安全元数据判断是否为空；为空时才读取 `初始密码：`。确定有效字段后，紧接粘贴前再次执行该字段的 `read-field --copy`，并用 `pbpaste` 做本地只读核对。不得打印、记录或保存密码。
   - From the latest screenshot, right-click inside the password field, using the visible `required` marker or the current field center if marker-side right-click does not open a menu. Wait 3 seconds after the menu appears, then from a fresh screenshot require the visible enabled `Paste` row to be blue-highlighted before activation. Re-derive the point from the current menu; never guess or reuse a menu coordinate. If a coordinate click closes the UTM menu without inserting, reopen it, press `Down` once, confirm the blue `Paste` row in a fresh screenshot, and press `Return`. Do not use `super+v`. If `Paste` is disabled or the field remains empty, 自动重新读取同一字段并重试一次，再按矩阵检查/修复同一 VM 剪贴板共享并复验；恢复穷尽后才进入 `utm-7-clipboard-recovery` 最后故障卡，不得键入密码兜底。
   - Do not copy the password back. Take a fresh screenshot and confirm the password field has focus and the visible bullet count equals the password length. If the count or focus is unclear, clear/refocus, validate a fresh clipboard readback and retry for two bounded recovery cycles; only persistent ambiguity after `utm-7-clipboard-recovery` exhaustion may use the last fault-card exit.
6. Before clicking Continue, take one more fresh screenshot and confirm the email field is populated and the password field contains the verified bullet count. Only then click Continue. If Apple shows the known phone/SMS verification flow, continue automatically: first re-run `verify-parent`, then use `read-field --copy` to re-read `电话：` and compare only its suffix with the masked options; continue only when exactly one visible option matches. Immediately before requesting the code, use `read-field --copy` to re-read `电话短信接收平台：`, assign the current clipboard value to `SMS_URL` without printing it, then clear the clipboard. Use the host Terminal—not Chrome, guest Edge, or guest Terminal—to run:

   ```zsh
   body=$(curl -fsSL --max-time 15 "$SMS_URL") || exit 1
   code="$(BODY="$body" python3 - <<'PY'
   import os, re
   codes = re.findall(r"Apple Account Code is: ([0-9]{6})", os.environ["BODY"])
   if len(codes) != 1:
       raise SystemExit(f"OTP_MATCH_COUNT={len(codes)}")
   print(codes[0], end="")
   PY
   )" || exit 1
   [[ "$code" =~ ^[0-9]{6}$ ]] || exit 1
   printf '%s' "$code" | pbcopy
   test "$(pbpaste | wc -c | tr -d ' ')" -eq 6
   test "$(printf '%s' "$code" | shasum -a 256 | awk '{print $1}')" = \
        "$(pbpaste | shasum -a 256 | awk '{print $1}')"
   printf 'OTP_CLIPBOARD=verified\n'
   ```

   Continue only when the response yields exactly one six-digit code for the current Apple prompt; zero or multiple matches enter `OP-APPLE-PHONE-OTP` 的三轮恢复/复核。按 `OP-NATIVE-PASTE` 把验证码只粘贴到第一个 UTM code box；禁止 `type_text`、快捷键或逐字输入兜底。Verify all six boxes are filled and wait for the page to advance. Immediately after Apple consumes or rejects the code, run `pbcopy </dev/null`, require `pbpaste` empty, then `unset code body SMS_URL`. If the known `Enter Mac Password` prompt appears for the current `<vm_name>` guest, call `OP-FIXED-PASSWORD-1234`, verify four bullets, and continue. No user password or authorization is requested.
7. Verify the guest System Settings Apple Account page shows the signed-in account (display name/email) and no pending sign-in error. A sidebar name alone is not sufficient; require the Apple Account detail page after verification.

## Guardrails

- Do not create, rename, delete, or edit Notion pages or fields.
- Do not use the Feishu desktop app as a data source.
- Do not report, echo, screenshot-share, or persist the Apple Account password.
- Never reuse cached account, phone, SMS URL, or OTP data after the Notion account information changes; re-read through `scripts/notion_api.py` and do not expose any full credential, phone number, SMS URL token, or verification code.
- Do not click Continue until both fields pass the exact paste checks; a populated-looking field is not sufficient.
- Use the right-click context-menu `Paste` action for both credential fields; `Down` plus `Return` is allowed only to activate the already blue-highlighted menu item when UTM coordinate clicking is unreliable. Never type credentials or use a general clipboard shortcut as a fallback.
- A context menu closing is not proof of success. Require a fresh screenshot showing the field populated; if blank, close the menu, revalidate the host sentinel/new-value transition, repair only the same VM clipboard sharing and retry twice from fresh screenshots. Only exhausted `utm-7-clipboard-recovery` may classify `CLIPBOARD_BRIDGE_UNAVAILABLE` and send the last global fault card before the next credential.
- For UTM guest menus, blue `Paste` highlighting is a required visual gate. The validated activation sequence is: right-click, wait 3 seconds, confirm blue `Paste`, then activate; when coordinate mouse-click dispatch is unreliable, use `Down` plus `Return` only after that blue confirmation.
- Use right-click context-menu `Select All`/`Copy` for account verification; do not use keyboard shortcuts in the credential fields.
- If the guest secure password field rejects context-menu paste, automatically re-read the same Notion field, validate a fresh native clipboard/menu state, clear/refocus the exact field and retry twice. Only persistent rejection after the `utm-7-clipboard-recovery` matrix is exhausted may send the last global fault card before submission.
- Do not change UTM settings, Clipboard Sharing, VM identity, network, proxy, sharing, users, or shell configuration. Repeated paste attempts are not a reason to enter the UTM settings.
- Handle the known phone selection, SMS-code retrieval, and current-guest Mac Password prompt automatically with live matching Notion data and fixed VM password `1234`. For CAPTCHA, account lock/disabled state, an unknown challenge, zero/multiple OTP matches, or an account/phone mismatch, first run the matrix's read-only page/account classification and 5/10/20-second live-source checks. Only a proven external/unrepairable state may invoke the last `notify-fault`/`wait-decision` exit; a fresh `manual_continue` still re-runs the same live-source recovery rather than serving as evidence.
- If the guest is not the target VM or the active user is not `<vm_name>`, refocus only the same run's exact VM and repeat the read-only run/VM/user identity checks through `utm-7-guest-identity` without selecting another VM. Only an exhausted mismatch proven to be external ownership conflict may send the last global fault card; do not enter credentials first.

## Completion

Report only the VM name, the signed-in Apple Account display name/email (email may be partially redacted), and `APPLE_ACCOUNT=verified`. After the current guest/account detail page is verified with no pending sign-in error, record `UTM_7=verified`. Any blocked result must first exhaust the matching automatic recovery matrix and independently reverify before entering the last global fault-card stage; then report only `APPLE_ACCOUNT=blocked` and the visible blocker category without secrets.

## 连续交接

仅当本技能全部完成检查通过并记录 `UTM_7=verified` 时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-8`；不得等待用户确认。阻断、失败或未完成状态不得交接。
