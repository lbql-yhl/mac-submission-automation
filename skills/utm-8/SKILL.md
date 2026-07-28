---
name: utm-8
description: Use after utm-7 when the signed-in Apple Account in a target UTM macOS VM needs its Personal Information recorded in the matching Notion registration page and its password changed.
---

# UTM-8

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
  --stage 'utm-8:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-8' \
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
| 页面/字段误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图，`Escape`/`Back` 回到 Sign-In & Security，重新定位并记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立定位后仍不唯一才发卡 |
| 密码字段不一致 | 只清两目标字段，实时生成/读取本轮密码并用哨兵剪贴板重贴，比较圆点数 | 三轮安全重贴且每轮独立回读后仍不一致才 `exhausted` |
| Apple 复杂度拒绝 | 按拒绝类别最多生成三个互不重复候选；每个候选都重新填写两框、完整自检并只提交一次，持久化 attempt 计数 | 三个不同候选都被策略拒绝、限流、锁定或未知挑战才 `unrepairable` |
| Change 结果不明 | 不再点击；只读等待并检查当前密码变更成功/拒绝状态 | 仍 ambiguous 才发卡 |

## Preconditions

- `utm-7` recorded `APPLE_ACCOUNT=verified` and `UTM_7=verified` after the project SSH helper's exact email match and close/reopen confirmation on the current `vm_name`; do not create or rename a VM.
- The target UTM guest is running, logged in as `<vm_name>`, and shows the signed-in Apple Account.
- `.env` contains a working Notion connection; `NOTION_ROOT_PAGE_ID` points directly to the current host page and the matching child page is `<应用名>-<vm_name>`.
- The page contains `账号信息` labels `用户名：`, `生日：`, `初始密码：`, and `修改后的密码：`.
- Use the current Notion page as the credential source. The effective current Apple password is the non-empty `修改后的密码：`, otherwise `初始密码：`. If both are empty, keep the guest page unchanged and run `verify-parent` plus both field reads immediately, after 5 seconds, and after 10 seconds. Any complete round continues automatically. Only three empty rounds prove external authoritative-data absence; then record recovery evidence and use the `utm-8-credential-source` last fault card without entering a credential.

## Control and secrecy

- Use Computer Use through `node_repl` and `@oai/sky` only for the UTM guest UI. After every action, call `get_app_state` and take a fresh screenshot when coordinates or field focus matter; never reuse coordinates after scrolling, resizing, menus, or page transitions.
- Perform every Notion read and write through `scripts/notion_api.py`. Do not open or operate Notion in Chrome, a plugin, Playwright, CUA, or browser clipboard APIs.
- Start with `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`; exact page, heading, and field matching is mandatory.
- Never log, report, screenshot-share, or persist passwords outside the intended Notion `账号信息` field. Do not use `type_text`, browser clipboard APIs, `Command+V`, or CDP/Playwright insertion for credentials.
- For every guest credential paste, put only the intended value on the host clipboard, verify it by byte count and SHA-256 without printing it, then use the current UTM right-click/Edit menu. Press `Down` with fresh screenshots until `Paste` is visibly blue-highlighted, then activate it once and verify the field state or bullet count. If paste fails, clear only that field and retry once; never type the password.
- Use `read-field --copy` to place one Notion field directly on the verified host clipboard without printing or creating a temporary file. Use `pbpaste | python3 scripts/notion_api.py set-field ... --value-stdin` for writes; command output must contain only non-secret metadata.

## Workflow

1. **Read the current Notion state by API.** Verify the parent and exact `<应用名>-<vm_name>` page. Use `read-field --copy` separately for `邮箱：`, `初始密码：`, `修改后的密码：`, `用户名：`, and `生日：`; never print their values. Confirm the Apple Account email shown in the guest matches `邮箱：`. The effective current password is the non-empty `修改后的密码：`, otherwise `初始密码：`; use the safe metadata byte count to select it and leave only that value on the clipboard for the guest.

2. **Capture Personal Information.** In the guest, open `System Settings` -> the signed-in Apple Account -> `Personal Information`. Screenshot-confirm the page, then record:
   - `Name`: the displayed Apple Account name; never derive it from the email prefix.
   - `Birthday`: convert to `年/月/日` (`YYYY/MM/DD`) only when the date order is unambiguous. If it is ambiguous or missing, reopen the same guest Apple Account `Personal Information`, re-read it from three fresh screenshots, and compare locale/date labels through `utm-8-birthday-source`; only recovery exhaustion or a proven missing authoritative value may send the last global fault card. Never guess.

3. **Write name and birthday to Notion by API.** For each captured value, put only that value on the verified host clipboard and run:

   ```bash
   pbpaste | python3 scripts/notion_api.py set-field \
     --title '<应用名>-<vm_name>' --heading '账号信息' \
     --label '<用户名：或生日：>' --value-stdin
   ```

   Do not use `--replace-existing`: an existing different value triggers two fresh reads of the same guest Apple Account and same Notion field. If the verified sources still conflict, classify it as external ownership/data conflict, record recovery evidence, and use the `utm-8-notion-conflict` last fault card without overwriting. The API preserves every other line and re-reads exact persistence. Use `read-field --copy` to verify each saved value by the previously recorded byte count/SHA-256; leave `应用信息` unchanged.

4. **Open password change.** Return to the guest Apple Account page, screenshot-confirm `Sign-In & Security`, open it, wait for the page to load, and screenshot-confirm `Change Password`. Handle an Apple Account password prompt with the effective current password from step 1 using the UTM right-click paste procedure. Never guess a password.

5. **Generate and fill the new password.** Use this host-side generator. It creates a 16-character random base and appends the literal trailing `y`; the final 17-character value is sent directly to `pbcopy` and only safe metadata is printed:

   ```bash
   python3 - <<'PY'
   import hashlib, secrets, subprocess
   alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
   while True:
       base = "".join(secrets.choice(alphabet) for _ in range(16))
       if any(c.isupper() for c in base) and any(c.islower() for c in base) and any(c.isdigit() for c in base):
           candidate = base + "y"
           break
   subprocess.run(["pbcopy"], input=candidate.encode(), check=True)
   copied = subprocess.check_output(["pbpaste"])
   if copied != candidate.encode():
       raise SystemExit("candidate clipboard mismatch")
   print(f"PASSWORD_CANDIDATE_BYTES={len(copied)}")
   print(f"PASSWORD_CANDIDATE_SHA256={hashlib.sha256(copied).hexdigest()}")
   PY
   ```

   Keep candidate values only in executor memory/current verified clipboard; persist only their SHA-256 and a stable attempt number. For each field, set the 16-character random base through the verified AX field path, then send the fixed trailing `y` as a real keyboard edit event to wake the macOS validator; verify both fields contain the same final 17-character value and equal bullet counts. If bullets are visible but `Change` remains disabled, do not submit; refill the same base and repeat the `y` wake-up event. On a policy rejection, clear the clipboard before generating the next value and require its hash differs from all earlier hashes. Record `PASSWORD_CANDIDATE_ATTEMPTS<=3`.

6. **Final change submission.** Re-read the latest guest state and confirm the current Apple Account is correct, both new-password fields remain filled with equal bullet counts, and the final `Change`/`Continue` action is uniquely identified and enabled. 全部自检通过后自动点击一次最终 `Change`/`Continue`，无需用户确认或操作。Wait at least 3 seconds and re-read the result page; do not click twice. If the account, fields, unique target, or enabled state changes, return to the verified account/form anchor, re-read the exact run/page/account and refill only reversible fields through `utm-8-run-context`. Only exhausted recovery or a proven ownership conflict may send the last global fault card, without clicking the final action.

7. **Verify acceptance and write back by API.** Confirm the password form closed or `Sign-In & Security` returned without an error. If Apple rejects complexity, read the exact non-sensitive rejection category, discard that value, and generate a new candidate that changes the rejected characteristic; never repeat or derive from the old value. Up to three distinct candidates may be tried automatically. Before every attempt, refill both fields and repeat every step 6 account/field/button check；重填验证通过后再次自动点击一次最终 `Change`/`Continue`。Each candidate is submitted exactly once. A successful attempt continues without user confirmation. Only three distinct policy rejections, rate limiting, account lock or an unknown security challenge may record recovery exhausted/unrepairable and enter the `utm-8-password-complexity-rejected` last fault card.

   Before each guest attempt, run `verify-parent`, invoke `scripts/notion_register_password.py` to write the final candidate to `修改后的密码：`, and independently read it back by byte count/SHA-256. Only then send the same candidate to the unchanged guest helper. If the guest returns a known non-zero failure, restore the exact preflight value (including blank) and independently verify `PASSWORD_NOTION_ROLLBACK=verified`; do not leave a rejected candidate in Notion. If Apple accepts, run `verify-parent` and independently re-read the prewritten candidate without writing again, then record `NOTION_PASSWORD_WRITE_RECOVERY=verified`. Never try the old password after Apple accepts and never claim that a later Notion read failure can roll Apple back. After exact readback, clear the clipboard and discard the in-memory value.

## Popup handling

- Solve ordinary loading, confirmation, and macOS permission dialogs by screenshot-confirming the text and choosing the button that continues the requested password-change flow.
- For a Mac password prompt belonging to the current `<vm_name>` guest, call `OP-FIXED-PASSWORD-1234` and its `OP-NATIVE-PASTE` GUI-authorization subflow; no run or user override exists.
- When the first real `y` wake-up key causes any `<requesting app> wants access to control System Events` consent dialog (for example `Terminal` or `sshd-keygen-wrapper`), detect that dialog, activate its unique `Allow`, wait for the `osascript` child to finish, and continue the same password-field attempt; do not relaunch the workflow or treat the consent dialog as an Apple challenge.
- If the random Apple Account dialog `Enter your password to view account details.` appears, read the current page's non-empty `修改后的密码：` through the Notion API, falling back to `初始密码：` only when the modified field is empty. Pass that value to the guest only through the current stdin payload, fill this dialog's password field, and click its unique `Continue` once after the field is verified. This is the Apple Account password, never the fixed `1234`; missing/ambiguous source is blocked before entry.
- For a dialog asking whether to sign out other devices, choose `Don’t Sign Out` when it is clearly part of this password-change flow; preserve other-device sessions.
- For the known SMS/2FA flow, reuse `utm-7`'s live Notion phone/SMS path automatically. For an iPhone passcode, CAPTCHA, account lock/disabled state, unknown security prompt, or unclear target account, first pause new credential entry, return to the verified account/page anchor, and perform the matrix's read-only account classification plus immediate/5/10-second live-source checks. A resolved known flow continues automatically. Only a proven CAPTCHA/lock/external challenge or an exhausted ownership ambiguity may record `AUTO_RECOVERY_RESULT=unrepairable|exhausted` and use the last fault card. `manual_continue` and `retry_skill` both re-run the same classification and live-source checks; neither response is evidence by itself.
- If the guest account, VM, Notion page, email, or password source does not match the current run, re-read the exact run and 重新读取同一 Notion 页面, refocus only the same guest, and repeat the identity/source checks through the bounded `utm-8-run-context` matrix. Only an exhausted mismatch proven to be an external ownership conflict may send the last global fault card; do not enter credentials first.

## Completion

Report only non-secret status: `vm_name`, `USERNAME=verified`, `BIRTHDAY=verified`, `PASSWORD_CHANGE=verified`, `MODIFIED_PASSWORD_NOTION=verified`, and `UTM_8=verified`. Any blocked result must first exhaust the matching automatic recovery matrix and independently reverify before entering the last global fault-card stage; then report `UTM_8=blocked` and the blocker category without any password, phone number, URL token, or verification code.

## Test contract

- Entry: `utm-7` is complete, the target guest account is signed in, and the Notion API uniquely resolves the configured parent and matching page.
- Success: the four completion markers above are all present; API verification proves only `用户名：`, `生日：`, and the accepted `修改后的密码：` were intentionally updated.
- Failure: any account/page mismatch, ambiguous date, exhausted clipboard recovery, all three distinct candidate rejections, rate limit/lock, or unknown security challenge stops before the next credential entry. One or two classified policy rejections continue with the next distinct candidate and are not terminal failures.

## 连续交接

仅当本技能全部完成检查通过时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-9`；不得等待用户确认。阻断、失败或未完成状态不得交接。
