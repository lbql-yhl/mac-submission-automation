---
name: utm-10
description: Use after utm-9 when the same UTM macOS guest must use Microsoft Edge to open Apple Developer, sign in to the registered Apple Account, or continue to developer.apple.com/account/.
---

# UTM-10

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
  --stage 'utm-10:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-10' \
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
| Edge 标签/地址误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图；关闭仅本轮错误新标签，回到既有 Edge，重新 Paste and Go；记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立定位后仍无法到唯一页面才发卡 |
| 登录字段不符 | 只清目标字段，实时 API 重读并用剪贴板哨兵重贴，逐字段回读 | 三轮安全重贴且每轮独立回读后仍失败才 `exhausted` |
| 2FA 瞬态 | 5/10/20 秒等待、实时电话/短信重读、唯一新 OTP 自动输入 | CAPTCHA、锁号、零/多码为 `unrepairable` |
| Account 页加载错误 | 同一 tab 只读等待，证明登录动作未发生时才重新导航一次 | 登录状态仍不明才发卡 |

## Preconditions

- Continue directly after `utm-9` in the same guest and same `<vm_name>`.
- Do not create, rename, restart, reconfigure, or inspect the VM.
- Do not open a host browser, host Chrome, Feishu, or a second browser process.
- `${PROJECT_ROOT}/.env` contains `NOTION_TOKEN` and the current host page's `NOTION_ROOT_PAGE_ID`.

## Notion API read rule

- Before each current-page read batch, run `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'` from `${PROJECT_ROOT}`.
- Read the exact `<应用名>-<vm_name>` page only through `scripts/notion_api.py read-field --copy`. For login use `账号信息` labels `邮箱：`, `修改后的密码：`, and fallback `初始密码：`; for SMS use `电话：` and `电话短信接收平台：`.
- Do not use host Chrome, a Notion plugin, Playwright, CUA, coordinates, or browser clipboard access to read Notion. Do not print, persist, or reuse field values.

## Click map

### Allowed clicks

1. Guest Edge `+` to open a new tab when a new page is requested.
2. The guest Edge address bar.
3. The current address-bar context menu's visibly enabled `Paste and Go` item.
4. Apple's visible `Continue`, `Sign In`, or equivalent login control, only when the Apple sign-in form is actually shown.
5. The Apple device-code `Allow` or `Trust` control when the current-account 2FA flow is visibly confirmed; handle it automatically.
6. The first Apple verification-code box, then its current context menu's visibly enabled `Paste` item.
7. The masked phone option only after re-reading `电话：` through the Notion API and confirming exactly one suffix match.
8. The visible Edge `Save` button when the password-save prompt appears after successful login.
9. The Apple account/avatar control only to verify that the signed-in account is present; do not open unrelated account resources.

### Forbidden clicks/actions

- Never click `Review agreement`, App Store Connect, Profile, Membership details, Certificates, IDs & Profiles, or other developer resources unless the user explicitly asks.
- Never click a phone option before the live Notion suffix comparison.
- Never close the active Apple code or device-code prompt before capturing the current code for this run.
- Use only the host Terminal flow below for SMS retrieval; browser-based SMS retrieval is not allowed.
- Never type credentials, URLs, or codes character by character; do not use `type_text`, blind `Command+V`, or guessed/stale coordinates.
- Never add `http://` or `https://` to workflow URLs.
- Never reuse coordinates after a click, navigation, menu, scroll, resize, or focus change.
- Do not follow CAPTCHAs, payment, legal, membership, password-reset, account-lock, unknown security, download, extension, or unrelated permission prompts.

## Strict paste rule

Before every paste, set the exact value with native clipboard input and verify `pbpaste` matches byte-for-byte. Then focus the intended field, right-click, and click the currently visible enabled `Paste` or `Paste and Go` item. Wait at least 3 seconds after every action and read a fresh screenshot/state before the next action.

Use these bare URLs exactly:

```text
developer.apple.com/app-store/small-business-program/
developer.apple.com/account/
```

Do not alter host, path, query, or token in a workflow URL.

### Exact SMS code source

The verification code must be obtained from the matching page's exact `电话短信接收平台：` field through the Notion API:

1. Re-run `verify-parent`, then execute `read-field --copy` for `电话：`. Use only the phone tail to match Apple's masked phone option; do not edit Notion.
2. Immediately before the request, execute `read-field --copy` for `电话短信接收平台：`, assign the exact clipboard value to `SMS_URL` without printing it, then clear the clipboard. Use the host Terminal—not host Chrome, guest Edge, or guest Terminal—to run:

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

3. Continue only when the response yields exactly one six-digit code for the current Apple prompt. Do not use a code from Notion, an earlier prompt, or a prior request.
4. Return to the unchanged Apple sign-in tab immediately, right-click the first verification box, and click the visible `Paste`. Confirm all six code boxes fill before continuing. After Apple consumes or rejects it, execute `pbcopy </dev/null`, require empty `pbpaste`, and `unset code body SMS_URL` before any next action.
5. If Apple reports an incorrect or expired code, do not reuse it. Keep the Apple prompt open, re-run `verify-parent`, re-read `电话短信接收平台：` through `read-field --copy`, request the current response again through the same host Terminal flow, and require one unique six-digit code before retrying.

## Tested workflow

1. In the current UTM guest Edge, click `+`, wait, and confirm the new tab/address bar from a fresh screenshot.
2. 调用 `OP-BROWSER-URL-NO-SCHEME`：执行 `printf '%s' 'developer.apple.com/app-store/small-business-program/' | python3 scripts/shared_operations.py browser-url --allow-bare`，只在 `BROWSER_URL_CLIPBOARD=verified` 后右键地址栏并激活可见蓝色高亮的 `Paste and Go`。Confirm the Small Business Program page and clear the clipboard.
3. If the page is already signed in, do not re-enter credentials. If Apple shows the sign-in form, run `verify-parent`, then use `read-field --copy` for `邮箱：`. For the password, read `修改后的密码：` first and use `初始密码：` only when the safe metadata says the modified field is empty; immediately re-copy the selected password field before pasting. Apply the strict paste rule and verify the visible email and password bullets before submitting.
4. If 2FA appears, call `OP-APPLE-PHONE-OTP`: click `Allow` after the account/prompt self-check; capture the new device code transiently before closing the prompt; if SMS is offered, re-read the matching Notion data through the API, use the host Terminal request, require one unique current six-digit code, then use `OP-NATIVE-PASTE` on the first code box. Click `Trust` after Apple accepts the code when it is shown. For CAPTCHA, account lock, unknown security prompts, non-unique phone/OTP results, or account mismatch, complete the operation's 5/10/20-second three independent live-source/page checks. Only a proven external/unrepairable state after all three rounds may use the current run's last `notify-fault`/`wait-decision` exit.
5. Click Edge `Save` if and only if the visible save-password prompt is present. Do not click `Not now` when the requested action is to save.
6. To continue to the account page, click Edge `+`, call `OP-BROWSER-URL-NO-SCHEME` with `printf '%s' 'developer.apple.com/account/' | python3 scripts/shared_operations.py browser-url --allow-bare`, and wait for the page. Confirm a visible `Account` header plus the signed-in name/avatar. Re-run `verify-parent` and read `邮箱：` immediately before this check; use the account/avatar menu's masked or full account label only to prove the same email (full exact match when visible, otherwise a unique suffix/domain match plus the already verified login session). Record `APPLE_ACCOUNT_EMAIL=verified`. Do not click anything else.

## Completion

Report only `vm_name`, `UTM_10=verified`, `EDGE=verified`, and `APPLE_ACCOUNT=verified`. If blocked, report `UTM_10=blocked` and only the non-secret blocker category. Never report passwords, full email, phone number, URL tokens, or verification codes.

## 连续交接

仅当本技能全部完成检查通过时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-11`；不得等待用户确认。阻断、失败或未完成状态不得交接。
