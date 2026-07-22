---
name: utm-3
description: Use when a cloned UTM macOS VM is ready after UTM-2 and a new administrator account must be created remotely from the host over SSH.
---

# UTM-3

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
  --stage 'utm-3:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-3' \
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
| SSH 中断 | 自动恢复同一 VM 连接，再只读检查用户、admin、Secure Token、home 和 key 的实际完成点 | 恢复三轮失败才发卡 |
| 创建用户结果不明 | 以稳定用户名为 attempt 身份；不存在才创建，完整匹配则幂等完成，部分状态只补安全可补项 | 非本 run 所有权/属性冲突禁止删除，`unrepairable` |
| 系统弹窗或 GUI 误点 | 本技能正常不依赖 GUI；若意外切入 GUI，等待至少 3 秒读取最新截图并关闭本轮弹窗，回到 SSH；记录 `GUI_RECOVERY=verified` | 无法确认弹窗归属才发卡 |
| key/admin 复验失败 | 自动修正权限、组成员和同一公钥一次，再用新连接复验 | 仍不一致才 `exhausted` |

## Overview

Create a VM-name-matching macOS administrator account over SSH. This skill does not use the System Settings GUI.

## SSH 全自动约束

- `demo` 与新建 `<vm_name>` 用户的固定密码始终都是 `1234`；不存在用户提供其他密码的分支。
- 直接继承 `utm-2` 的 `UTM_2=verified`、VM IP、`demo` BatchMode 登录和宿主机 `${SUBMISSION_SSH_PUBLIC_KEY}`，不重新配置 Remote Login。
- 创建最终用户后，本技能必须自动把同一宿主公钥安装到其 `authorized_keys`，验证 `BatchMode=yes` 并记录 `SSH_KEY_AUTH=verified`。SSH 连接或认证先全自动恢复且不向用户索取信息；自动恢复仍失败时记录 `SSH_AUTO_RECOVERY=blocked`，先按 `utm-3-ssh-auto-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。

## Preconditions

- Run only after `utm-2` has recorded `UTM_2=verified` for the target VM desktop, SSH service, key authentication, IP address, and identifiers.
- Reuse the current Feishu-run `vm_name`; never operate on the `macOS` source template.
- The `demo` account and every `<vm_name>` account use password `1234`; it is the only macOS login/sudo password for this project and has no user or run override.

## Workflow

1. 固定继承值并验证安全边界；所有 SSH 命令都显式绑定同一把私钥，禁止依赖 ssh-agent 误选身份：

   ```bash
   name="<inherited-vm_name>"
   vm_ip="<inherited-exact-vm-ip>"
   run_id="<current-run-id>"
   private_key="${SUBMISSION_SSH_PRIVATE_KEY}"
   public_key="${SUBMISSION_SSH_PUBLIC_KEY}"
   [[ "$name" =~ ^[a-z]{4}$ ]]
   [[ "$run_id" =~ ^[A-Za-z0-9-]{8,80}$ ]]
   test -s "$private_key" -a ! -L "$private_key"
   test -s "$public_key" -a ! -L "$public_key"
   ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
     -o ConnectTimeout=5 demo@"$vm_ip" \
     'test "$(id -un)" = demo; id -Gn; printf "SSH_TRANSPORT=verified\n"'
   ```

   非 0 先按 `utm-2` 对同一精确 VM 做三轮 SSH 恢复；它不是“用户不存在”。只有输出用户名为 `demo` 且组含 `admin` 才继续。
2. 在创建任何账号前，用独立 SSH 会话确认 `demo` Secure Token 为 enabled；disabled 时先恢复模板账号授权，禁止尝试创建最终用户。随后为本 run 准备 guest marker `/var/db/submission-automation/utm-3-$run_id.json`：
   - marker 不存在：生成一个稳定 `ACCOUNT_ATTEMPT_ID`，通过带 TTY 的 `sudo` 原子写入 mode 600，字段为 run_id、vm_name、目标 home、宿主公钥 SHA-256、attempt_id、`status=planned`；
   - marker 存在：两条独立只读 SSH 都必须读到完全相同的这些字段，才继承原 attempt；
   - marker 缺失但账号已存在，或 marker 所有权字段不匹配：独立只读检查三轮后判为外部冲突，不能补写 marker 来“认领”旧账号；只有三轮均一致才允许最后故障卡。
3. 用不带 TTY 的只读命令区分 SSH 传输与账号状态：

   ```bash
   ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
     -o ConnectTimeout=5 demo@"$vm_ip" \
     "/usr/bin/id -u '$name' >/dev/null 2>&1; rc=\$?; printf 'ACCOUNT_LOOKUP_RC=%s\n' \"\$rc\"; exit 0"
   ```

   `ACCOUNT_LOOKUP_RC=1` 且目录服务明确返回 no-such-user 才是 `UTM_3_USER_PRECHECK=missing`。0 是 exists；其他值或命令无输出先恢复传输，不得创建。
4. 若 exists，用两条新 SSH 会话逐项读取：UID/GID、`NFSHomeDirectory=/Users/$name`、`UserShell=/bin/zsh`、admin membership、两名用户 Secure Token、home owner、`.ssh`/`authorized_keys` 权限、host key 指纹是否唯一包含于 guest 文件，以及 marker/attempt：
   - 全部匹配且 marker 属于当前 run：`UTM_3_USER_PRECHECK=resume_verified`，从第一个未完成状态继续；
   - marker 属于当前 run 且只有一个可逆子项缺失：只修该项，随后重新执行全部两轮检查；
   - marker 缺失/冲突、home/UID 所有权冲突或账号早于本 run：记录 `AUTO_RECOVERY_RESULT=unrepairable`，禁止删除、改名、重建或猜测。
5. 仅 missing + marker=planned 时，持久化 marker `status=creating` 后执行一次创建命令：

   ```bash
   ssh -tt -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
     -o ConnectTimeout=5 demo@"$vm_ip" \
     "sudo /usr/sbin/sysadminctl -addUser '$name' -fullName '$name' -password - -admin"
   ```

   自动化只在已确认的远端 `sudo`/`User password` 提示输入固定 `1234`，不得把密码写入 argv、管道或日志。连接中断后先只读执行步骤 3/4；账号存在则绝不重发 addUser。
6. 账号属性检查通过但 Secure Token 未启用时，将 marker 更新为 `status=enabling_token`，执行一次：

   ```bash
   ssh -tt -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
     -o ConnectTimeout=5 demo@"$vm_ip" \
     "sudo /usr/sbin/sysadminctl -secureTokenOn '$name' -password - -adminUser demo -adminPassword -"
   ```

   仅对已识别的远端提示输入固定 `1234`。结果不明先以两条只读 `sysadminctl -secureTokenStatus` 判断，enabled 时不得重做。
7. 将 host public key 安装给最终用户。先尝试显式私钥的 BatchMode；失败且步骤 4 已证明账号归当前 run 时，才用 mode-600 `$public_key` 通过 host PTY 执行一次 `ssh-copy-id -i "$public_key"`，固定 `1234` 只进密码提示：

   ```bash
   ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
     -o ConnectTimeout=5 "$name@$vm_ip" 'id -un' ||
   ssh-copy-id -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new \
     -i "$public_key" "$name@$vm_ip"
   ```

8. 用两次全新 BatchMode 会话执行最终断言：当前用户精确为 `$name`；UID 是唯一的非系统 UID；home/shell 精确；组含 admin；`demo` 与 `$name` Secure Token 都 enabled；home owner 为 `$name:staff`；`~/.ssh`=700、`authorized_keys`=600；host public-key 指纹在 guest 中恰好匹配；marker 的 run/name/key fingerprint/attempt 均一致。然后原子更新 marker `status=complete` 并第三次回读，记录：

   ```text
   ACCOUNT_ATTEMPT_ID=<stable-id>
   ACCOUNT_MARKER=verified
   ACCOUNT_IDENTITY=verified
   ACCOUNT_ADMIN=verified
   ACCOUNT_SECURE_TOKEN=verified
   SSH_KEY_FINGERPRINT=verified
   SSH_KEY_AUTH=verified
   UTM_3=verified
   ```

   任一项缺失都不是成功；不得只凭 `id -u` 或 addUser exit 0 交接。

## Guardrails

- Use `ssh -tt`; without a TTY, `sysadminctl` can fail with `errAuthorizationInteractionNotAllowed`.
- Always run `sysadminctl` through `sudo`; otherwise it can fail with `sysadminctl should be run as root`.
- Use `-password -` and `-adminPassword -` so passwords are prompted interactively. Never use `echo 1234 | ssh`, `sshpass`, or literal passwords in command arguments.
- Do not delete, rename, disable, or modify an existing account.
- Do not change VM CPU, memory, disk, network, identity, or sharing settings.
- This skill is SSH-only. If SSH fails, automatically reuse `utm-2`'s exact-VM Remote Login/IP repair and key bootstrap, then re-check the account before resuming. Never wait for an SSH-specific decision or request user information.
- If SSH drops during account creation, repair SSH automatically first and run `id '<vm_name>'` before retrying. A missing user may restart step 2; an existing or partially created user must run the same `utm-3-user-exists` ownership/admin/token/home/key recovery classification and resume from the first missing item when proven run-owned. Only an external conflict or exhausted ambiguity enters the last fault-card branch, so the account is never duplicated or silently reused.
- If Secure Token cannot be enabled, report the mismatch and do not claim the new account has the same privileges as `demo`.

## 连续交接

仅当本技能全部完成检查通过并记录 `UTM_3=verified` 时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `vm-down`；不得等待用户确认。阻断、失败或未完成状态不得交接。
