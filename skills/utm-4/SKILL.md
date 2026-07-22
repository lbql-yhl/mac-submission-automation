---
name: utm-4
description: "Use after vm-down when a cloned UTM macOS VM is logged in as the VM-name administrator and needs final command-line cleanup: disable automatic software update switches, delete the default demo user, and verify both by SSH."
---

# UTM-4

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
  --stage 'utm-4:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-4' \
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
| 更新开关未全部为 0 | 只重写不匹配的键，重新读取全部键，完整做三轮安全修复且每轮独立回读 | 三轮仍回弹才 `exhausted` |
| 删除 `demo` 传输中断 | 只读检查目录服务记录、进程和 home；已删除即完成，存在且删除未执行才续做 | 删除结果不明禁止重复破坏，发卡 |
| home 仍存在 | 先确认用户记录已消失且路径精确为 `/Users/demo`，再执行一次清理并验证 | 所有权/路径不明为 `unrepairable` |
| SSH 失败 | 同一 VM 自动恢复三轮，从最后验证点继续 | 恢复耗尽才发卡 |

## Overview

Finalize the cloned UTM macOS VM from the host over SSH. This skill closes automatic software update switches and removes the default `demo` user after the VM-name administrator account has already been verified.

## SSH 全自动约束

- 直接继承 `vm-down` 的 `VM_DOWN=verified`、`SSH_KEY_AUTH=verified`、精确 VM/IP 和 `<vm_name>`；所有 SSH 登录统一使用宿主机现有 Key 与 `BatchMode=yes`。
- 仅远端 `sudo` 需要固定 `1234`，由自动化在 PTY 提示中输入；不得向用户索取密码、SSH Key 或 IP。
- BatchMode 失败时，只对同一精确 VM 自动刷新 IP、检查 Remote Login/端口并恢复 `${SUBMISSION_SSH_PUBLIC_KEY}`，不向用户索取任何 SSH 信息；自动恢复仍失败时记录 `SSH_AUTO_RECOVERY=blocked`，先按 `utm-4-ssh-auto-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。

## Preconditions

- Run only after `vm-down` has recorded `VM_DOWN=verified` for the `<vm_name>` desktop, sharing mount, and SSH/admin access.
- Reuse the current Feishu-run `vm_name`; never operate on the `macOS` source template.
- Use the VM IP already verified by `utm-2`/`vm-down`. Only if the inherited connection is unreachable may the IP be refreshed once by matching this exact `<vm_name>.utm` config MAC in `arp -an`; never scan for or select another/latest VM.
- The `demo` account and every `<vm_name>` account use password `1234`; it is the only macOS login/sudo password for this project and has no user or run override. Automation supplies this same fixed password at every password prompt in this skill; never ask the user.

## Workflow

1. 固定 SSH 身份并验证目标是 clone 的最终管理员；后续每条 SSH 都复用这些参数：

```bash
name="<inherited-vm_name>"
vm_ip="<inherited-exact-vm-ip>"
run_id="<current-run-id>"
private_key="${SUBMISSION_SSH_PRIVATE_KEY}"
test -s "$private_key" -a ! -L "$private_key"
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
  -o ConnectTimeout=5 "$name@$vm_ip" \
  'id -un; id -Gn; sw_vers -productVersion'
```

The username must equal `<vm_name>` and groups must include `admin`. If SSH logs in as `demo`, pause cleanup, resolve the same run's exact VM/IP/key again and perform the bounded `utm-4-identity` recovery checks. Only an exhausted mismatch or proven external ownership conflict may send the last global fault card and wait.

2. Disable software update automatic switches:

```bash
ssh -tt -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
  -o ConnectTimeout=5 "$name@$vm_ip" "sudo /bin/sh -c '
if /usr/sbin/softwareupdate --schedule off >/dev/null 2>&1; then
  printf \"SOFTWAREUPDATE_SCHEDULE=disabled\n\"
else
  printf \"SOFTWAREUPDATE_SCHEDULE=legacy_command_unsupported\n\"
fi
/usr/bin/defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticCheckEnabled -bool false
/usr/bin/defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticDownload -bool false
/usr/bin/defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticallyInstallMacOSUpdates -bool false
/usr/bin/defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticallyInstallAppUpdates -bool false
/usr/bin/defaults write /Library/Preferences/com.apple.SoftwareUpdate CriticalUpdateInstall -bool false
/usr/bin/defaults write /Library/Preferences/com.apple.SoftwareUpdate ConfigDataInstall -bool false
/usr/bin/defaults write /Library/Preferences/com.apple.commerce AutoUpdate -bool false
'"
```

SSH authentication must not prompt. Let the automation enter the project-wide fixed `1234` only at the remote `sudo` prompt. `softwareupdate --schedule off` is kept for older macOS versions; if unsupported, the `defaults` writes still do the work.

3. 删除前做两条独立只读 SSH：要求当前用户仍为 `$name`、admin/key 指纹仍匹配；读取 `id demo`、`dscl . -read /Users/demo`、`who`、`pgrep -u demo` 和 `/Users/demo` 的 `lstat`。成功前置是没有 demo 登录会话/活跃进程，home 若存在必须是非符号链接目录且规范路径精确为 `/Users/demo`。有活动会话时先正常退出该会话并重查，绝不直接 kill 或删 home。
4. 在 guest 的 `/var/db/submission-automation/` 原子创建/继承 mode-600 marker，绑定 run/name/key fingerprint，持久化稳定 `DEMO_DELETE_ATTEMPT_ID` 和 `status=planned`。marker 冲突时不删除。若两轮读取已经证明 user record 与 home 都不存在，则记录 `DEMO_STATE=absent` 并跳到验证。
5. 仅当 demo record 存在、marker 属于当前 run 且 status=planned 时，将 status 更新为 `deleting_user`，再执行一次：

   ```bash
   ssh -tt -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
     -o ConnectTimeout=5 "$name@$vm_ip" \
     'test "$(id -un)" != demo; sudo /usr/sbin/sysadminctl -deleteUser demo -secure'
   ```

   等待命令完整返回。若 SSH/命令结果不明，先用两条新连接读取 `id` 与 `dscl`：两者都不存在即视为删除已完成，不再执行删除；仍存在时只在日志明确证明 `sysadminctl` 在任何删除副作用前因“不支持该操作”失败，才允许一次 `sudo dscl . -delete /Users/demo` fallback。普通非 0、超时或权限错误禁止用 `||` 直接串联第二个删除器。
6. 仅当 `id` 与 `dscl` 都已独立证明账号不存在后，重新 `lstat /Users/demo`。路径不存在即完成；路径仍是精确的非符号链接目录且 marker 属于当前 attempt 时，执行一次 `sudo /bin/rm -rf -- /Users/demo`。符号链接、mount point、规范路径不等或所有权不明均不得删除。

7. Verify software update switches:

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
  -o ConnectTimeout=5 "$name@$vm_ip" '
for k in AutomaticCheckEnabled AutomaticDownload AutomaticallyInstallMacOSUpdates AutomaticallyInstallAppUpdates CriticalUpdateInstall ConfigDataInstall; do
  v=$(/usr/bin/defaults read /Library/Preferences/com.apple.SoftwareUpdate "$k" 2>/dev/null || echo "<unset>")
  printf "%s=%s\n" "$k" "$v"
done
v=$(/usr/bin/defaults read /Library/Preferences/com.apple.commerce AutoUpdate 2>/dev/null || echo "<unset>")
printf "AutoUpdate=%s\n" "$v"
'
```

Every listed value should be `0`.

8. Verify `demo` was removed with assertions rather than output-suppressing `|| true`:

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
  -o ConnectTimeout=5 "$name@$vm_ip" '/bin/zsh -s' <<'EOF'
set -euo pipefail
if /usr/bin/id demo >/dev/null 2>&1; then
  printf 'DEMO_ID=present\n'; exit 1
fi
if /usr/bin/dscl . -read /Users/demo >/dev/null 2>&1; then
  printf 'DEMO_DSCL=present\n'; exit 1
fi
test ! -e /Users/demo -a ! -L /Users/demo
printf 'DEMO_ID=absent\n'
printf 'DEMO_DSCL=absent\n'
printf 'DEMO_HOME=absent\n'
printf 'DEMO_STATE=absent\n'
EOF
```

9. 原子更新 marker `status=complete`，新连接回读 attempt/run/name 和最终四项断言；记录 `DEMO_DELETE_ATTEMPT_ID=<stable-id>`、`DEMO_STATE=absent`。任一 update key 不为 0 或 demo 仍存在都不得记录 `UTM_4=verified`。

## Guardrails

- Do not run these commands on the host macOS; run them only through SSH into the cloned VM.
- Do not run before the VM-name administrator account has been verified by `vm-down`.
- Do not delete `demo` while logged in as `demo` or while still relying on `demo` for SSH recovery.
- Before deleting `demo`, require a fresh BatchMode login as `<vm_name>`, matching host/guest key fingerprints, and `admin` membership; this final-user key is the only SSH recovery identity used afterward.
- Do not change the Desktop & Dock "click wallpaper to show desktop" setting; that item is intentionally excluded.
- Do not change VM CPU, memory, disk, network, identity, or sharing settings.
- Do not put passwords in command arguments, `echo` pipelines, or `sshpass`.

## Completion Report

Report:

- Target VM name and IP.
- SSH user and `admin` group verification.
- Software update switch values, all `0`.
- `demo` user record removed.
- `/Users/demo` removed.
- `DEMO_DELETE_ATTEMPT_ID=<stable-id>`.
- `DEMO_STATE=absent`.
- `UTM_4=verified`.

## 连续交接

仅当本技能全部完成检查通过并记录 `UTM_4=verified` 时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-5`；不得等待用户确认。阻断、失败或未完成状态不得交接。
