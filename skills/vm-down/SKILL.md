---
name: vm-down
description: Use after UTM-3 has created the VM-name administrator account, when the target UTM macOS VM must be shut down or restarted and then logged in with the newly created VM-named user.
---

# vm-down

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
  --stage 'vm-down:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'vm-down' \
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
| 关机传输中断 | 只读轮询同一 VM `stopped`；已停机不重发 shutdown，仍 running 且确认命令未执行才重试一次 | 状态仍不明时发卡，不强停 |
| Sharing 页误点/错行 | 窗口尺寸/焦点变化或误点后等待至少 3 秒，读取最新截图，`Escape`/`Cancel` 回到精确 VM 设置；只修改匹配目录行，记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立定位后仍不能唯一识别才发卡 |
| 共享目录非只读 | 保存前记录旧行；移除错误行后只读重加，保存并重开复验，失败则用旧行恢复 | 还原/复验仍失败才 `exhausted` |
| 首次登录/挂载失败 | 从当前欢迎页第一个未完成步骤续做；已到桌面不重跑；SSH/挂载做三轮同 VM 恢复 | 未知账号/安全提示为 `unrepairable` |

## Overview

Safely restart a cloned UTM macOS VM and log in as the VM-named administrator account created by `utm-3`.

## SSH 全自动约束

- 直接继承 `utm-3` 的 `UTM_3=verified`、`SSH_KEY_AUTH=verified`、精确 VM/IP 和 `<vm_name>`；所有 SSH 登录使用宿主机现有 Key 与 `BatchMode=yes`，不再要求登录密码。
- 只有远端 `sudo` 或 UTM 登录界面需要固定 `1234`，由自动化在已核对的提示中输入；不得向用户索取密码、SSH Key 或 IP。
- 连接失效时，只对同一精确 VM 自动刷新 IP、检查 Remote Login/端口并恢复同一宿主公钥，不向用户索取任何 SSH 信息；自动恢复仍失败时记录 `SSH_AUTO_RECOVERY=blocked`，先按 `vm-down-ssh-auto-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。

## Preconditions

- Run only after `utm-3` has recorded `UTM_3=verified` for the `<vm_name>` account.
- Reuse the current Feishu-run `vm_name`; never generate a new name.
- The `demo` account and every `<vm_name>` account use password `1234`; it is the only macOS login/sudo password for this project and has no user or run override.

## Target VM

- Directly inherit the exact `vm_name`, VM IP, and verified administrator account from `utm-3`.
- If that handoff is missing or inconsistent, 自动重新执行 `utm-3` 的同一 run 恢复入口：重新读取同一精确 run/`vm_name`，先重做最终用户、`admin`、Secure Token、`authorized_keys` 权限/指纹和 BatchMode 预检，只补做未验证步骤，不删除、复用或重复创建账号。恢复后重建并复核 `UTM_3=verified`/`SSH_KEY_AUTH=verified` 交接；仍缺失、部分完成或不一致时，先按 `vm-down-handoff-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。不得选择用户命名、最新或其他 VM。

Do not operate on the source template VM `macOS`.

## Workflow

1. Confirm the target UTM VM status:

```bash
utmctl status <vm-name>
```

2. If the VM is running, shut it down from inside guest macOS over SSH. Bind the inherited private key explicitly; let the automation enter fixed password `1234` only at the remote `sudo` prompt:

```bash
private_key="${SUBMISSION_SSH_PRIVATE_KEY}"
test -s "$private_key" -a ! -L "$private_key"
ssh -tt -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
  -o ConnectTimeout=5 <vm-name>@<vm-ip> "sudo /sbin/shutdown -h now"
```

Do not use `utmctl stop`, restart, or a UTM power button. This skill always closes the exact sequence `guest halt → UTM stopped → Sharing verification/repair → utmctl start`; a direct restart would skip the only safe settings window and is forbidden.

3. Wait until UTM reports the VM is stopped:

```bash
utmctl status <vm-name>
```

4. If SSH shutdown cannot be run, first perform the automatic exact-VM SSH recovery above and retry the shutdown check. If the VM still does not stop cleanly, preserve the VM and any unsaved-work/app-blocking prompt, classify `running|shutdown_requested|prompt_blocked|stopped` from fresh SSH/process/UTM state, and execute the bounded `vm-down-shutdown` recovery matrix without repeating a confirmed shutdown request. Only exhausted recovery or a proven unsaved-work prompt that cannot be handled safely may record `VM_SHUTDOWN=blocked`, send the last global fault card and wait. Never ask the user for SSH information, discard work, or fall back to `utmctl stop`/UTM GUI power control.
5. Before starting the VM again, verify the target VM's UTM edit settings have the shared directory configured and read-only. Do not confuse network `Mode = Shared` or `ClipboardSharing = true` with directory sharing. If the UTM Sharing list is missing the required row, configure it, save, and re-check before starting. If the row exists but read-only is not enabled, remove it, re-add it as read-only, save, and re-check before starting.
6. Start the VM:

```bash
utmctl start <vm-name>
```

7. Wait for the macOS login screen.
8. Log in as `<vm_name>` using the detailed login steps below.
9. If the first-login setup assistant appears, complete it using the fixed choices below.
10. Finish only when the macOS desktop is visible, the logged-in user matches `<vm_name>`, and the shared directory is mounted in the guest.

## Shared Directory Verification

Run these checks after the VM is stopped and before `utmctl start`.

First confirm the host directory is the exact absolute, non-symlink configured path:

```bash
share="${SUBMISSION_SHARED_DIR}"
case "$share" in
  /*) ;;
  *) exit 1 ;;
esac
test -d "$share" && test ! -L "$share"
```

Then verify or configure the UTM UI setting itself:

1. Open UTM and select the target VM.
2. Open the VM edit/settings window.
3. Select `共享` in the left sidebar.
4. If the sharing table already has `${SUBMISSION_SHARED_DIR}` and the same row has `只读?` enabled, it passes.
5. If the row is missing, enable `添加只读`, click `添加`, choose `${SUBMISSION_SHARED_DIR}`, click `打开`, then `存储`.
6. If the row exists but `只读?` is not enabled, remove the row and re-add it with `添加只读` enabled.
7. Reopen the target VM edit/settings `共享` page and verify the row exists with `只读?` enabled before starting.

The UTM edit/settings `共享` page is the source of truth. Seeing only `Network -> Mode -> Shared`, `ClipboardSharing`, or a host directory existing in Finder is not enough. `socks5.yml` is created later by `utm-5`, so `vm-down` must not require that file to exist.

After the desktop appears, verify the one exact guest directory rather than accepting a parent mount:

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
  -o ConnectTimeout=5 <vm-name>@<vm-ip> \
  'test -d "/Volumes/My Shared Files/共享文件"; printf "MOUNT_PATH=/Volumes/My Shared Files/共享文件\n"'
```

Verify read-only with a temporary write probe. A successful `touch` is an explicit failure; the shell must not turn that failure back into exit 0:

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
  -o ConnectTimeout=5 <vm-name>@<vm-ip> '/bin/zsh -s' <<'EOF'
set -euo pipefail
mount='/Volumes/My Shared Files/共享文件'
err="$(mktemp /tmp/codex-readonly.XXXXXX)"
probe="$mount/.codex_readonly_probe_$$"
trap '/bin/rm -f "$err"' EXIT
if /usr/bin/touch "$probe" 2>"$err"; then
  /bin/rm -f "$probe"
  printf 'READONLY_PROBE=writable_failure\n'
  exit 1
fi
test ! -e "$probe"
test -s "$err"
printf 'MOUNT_PATH=/Volumes/My Shared Files/共享文件\n'
printf 'READONLY_PROBE=verified\n'
EOF
```

If the shared directory is missing after login, or if the write probe succeeds, preserve the exact `/Volumes` listing and UTM `共享` page evidence, shut down normally when a settings correction is required, repair only the same VM's read-only share entry, restart, and re-run the mount/write probe through `vm-down-sharing-mount`. Only exhausted recovery may send the last global fault card and wait. Do not continue to `utm-4` or `utm-clash` before the recheck passes.

## Login Screen Operation

Use visible labels and the latest screenshot only; old absolute coordinates are not part of the contract. After every click/key action wait at least 3 seconds and re-read the target window before the next action.

1. Confirm the UTM window title exactly matches the inherited `<vm_name>`.
2. If only `demo` is visible, click the visible account-switch area once, wait, and require the fresh screenshot to show an account list.
3. Click the unique account whose name exactly matches `<vm_name>`; wait and verify the same name is now selected.
4. If the row only highlights, double-click the VM user avatar/name or click it again until the password field appears under `<vm_name>`.
5. Click the password field only after the selected username was reverified.
6. Call `OP-FIXED-PASSWORD-1234` 的 VM 登录子流程：do not paste; press `1`, `2`, `3`, `4` as separate key presses and verify four bullets.
7. Confirm exactly four password dots are visible.
8. Submit once by pressing `Return`; do not also click the arrow while the result is unknown. Wait and classify the fresh screen before any retry.
9. If macOS returns to the same password screen or shows a password error, preserve the exact screen state, verify the selected `<vm_name>` account, input source/keyboard layout and fixed password handling, then clear/refocus and retry the same value through the bounded `vm-down-login-password` matrix. Only repeated rejection after the identity and keyboard checks may send the last global fault card. Do not try other passwords.

## First-Login Setup Choices

When logging in to the newly created VM-named account for the first time, macOS may show setup assistant pages. Use these fixed choices and do not enter any Apple Account, personal information, or new settings.

1. **Accessibility**: click `Not Now`.
2. **Data & Privacy**: click `Continue`.
3. **Sign In to Your Apple Account**: click `Set Up Later`.
4. **Skip Apple Account confirmation**: click `Skip`.
5. **Analytics**: leave all analytics checkboxes unchecked and click `Continue`.
6. **Screen Time**: click `Set Up Later`.
7. **Siri**: uncheck `Enable Ask Siri`, then click `Continue`.
8. **Choose Your Look**: keep the default `Light` selection and click `Continue`.
9. **Update Mac Automatically**: click `Only Download Automatically`.
10. **Welcome to Mac**: click `Continue`.

After the desktop appears, dismiss nothing unless it blocks the workflow. System notifications such as extension notices can be left alone.

## Verification

After the desktop is visible, verify the VM-named user can SSH and is an administrator:

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
  -o ConnectTimeout=5 <vm-name>@<vm-ip> "id -un; id -Gn"
```

If the inherited IP is no longer reachable after reboot, refresh it once from this exact VM's config MAC and repeat the same BatchMode check. If key authentication is missing, automatically reinstall `${SUBMISSION_SSH_PUBLIC_KEY}` with fixed `1234` and verify again. The output must show `<vm_name>` and include `admin`; record `SSH_KEY_AUTH=verified` without user input.

## Guardrails

- Do not force-stop, delete, clone, rename, or edit VM settings unless the user explicitly instructs it.
- Do not use `utmctl stop` or UTM GUI power controls for shutdown/restart. SSH into guest macOS and run `/sbin/shutdown`; use UTM only to start the VM again.
- Do not change CPU, memory, display, disk, network, or identity settings. Sharing is the one settings exception: only the exact `${SUBMISSION_SHARED_DIR}` row may be added/re-added read-only as described above.
- Do not log in as `demo` when the VM-name account is missing or blocked. 自动重新执行 `utm-3` 的同一 run 恢复入口并复核精确账号；仍异常时使用 `vm-down-login-account` 故障卡，不得绕过最终用户继续。
- Do not paste the project-wide fixed password into UTM login. Use separate key presses and verify the dot count.
- Do not sign in to Apple Account during first-login setup; always choose `Set Up Later` then `Skip`.
- Do not enable Siri; uncheck `Enable Ask Siri` before continuing.
- Do not enable analytics sharing.
- Do not choose automatic installation for macOS updates; choose `Only Download Automatically`.
- If macOS says the account is locked, wait for the full lockout period before retrying; clear the password field before entering the password again.
- If the VM-named account is not visible at login, 自动重新执行 `utm-3` 的同一 run 恢复入口，重查同一精确账号和登录列表且不在本技能创建第二个账号；再次不可见或状态不明确时，先按 `vm-down-login-account` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。

## Completion Report

Report:

- Target VM name.
- VM stopped cleanly.
- Host shared directory existed before restart.
- UTM edit/settings `共享` page showed `${SUBMISSION_SHARED_DIR}` with read-only enabled.
- VM started successfully.
- First-login setup reached the desktop with the fixed choices.
- Logged-in macOS user matches the VM name.
- Guest shared directory mounted after login.
- `MOUNT_PATH=/Volumes/My Shared Files/共享文件`.
- `READONLY_PROBE=verified`.
- SSH verification shows the VM-named user and `admin` group.
- `VM_DOWN=verified`.

## 连续交接

仅当本技能全部完成检查通过并记录 `VM_DOWN=verified` 时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-4`；不得等待用户确认。阻断、失败或未完成状态不得交接。
