---
name: vm-down
description: Use after utm-3 has created the VM-name administrator for nonvisual shutdown, shared-directory verification, and persistent guest settings; never restart or open the cloned VM.
---

# vm-down

## 无视觉执行边界

本技能只允许 UTM CLI/Registry、宿主 shell、SSH/PTY、guest shell、launchd、文件与命令回读；其他交互方式不属于本技能。先运行：

```bash
eval "$(python3 scripts/preflight.py --project-only --emit-shell)"
```

本技能继承 [`../_shared/AUTOMATION_CONTRACT.md`](../_shared/AUTOMATION_CONTRACT.md) 的自动诊断、自动修复、自动复验和最后故障卡规则。`OP-NATIVE-PASTE`、`OP-BROWSER-URL-NO-SCHEME`、`OP-APPLE-PHONE-OTP`、`OP-FIXED-PASSWORD-1234`、`OP-USER-CONFIRMATION` 不在正常路径调用；固定密码只在精确 SSH PTY 的远端 `sudo` 提示中输入。

## SSH 全自动约束

- 直接继承 `utm-3` 的 `SSH_KEY_AUTH=verified` 和同一最终管理员；所有读取命令均使用 `${SUBMISSION_SSH_PRIVATE_KEY}`、`IdentitiesOnly=yes` 与 `BatchMode=yes`。
- 正常关机的唯一例外是带 PTY 的远端 `sudo`，固定密码只能在该已核对的提示中输入。
- 连接失效时仅刷新同一 config MAC 对应地址、检查 22 和恢复同一公钥；三轮仍失败记录 `SSH_AUTO_RECOVERY=blocked`。

## 本技能自动恢复矩阵

| 故障点 | 自动诊断、修复和复验 | 最后出口 |
|---|---|---|
| 关机传输中断 | 只读轮询同一 VM `stopped`；已停机绝不重发 shutdown | 状态仍不明确 |
| Registry 共享冲突 | 三轮导出/结构化读取 UUID、路径、ReadOnly 和 bookmark 字节数 | 多项、路径不匹配或书签不可用 |
| 挂载/只读探针失败 | 正常停机后只修复当前 UUID 的一项，再由外部启动后做新 SSH 回读 | 三轮仍缺失或可写 |
| 服务/电源设置不持久 | 重启后新 SSH 读取 launchd、日志、Remote Login、pmset 和用户偏好 | 三轮仍不一致 |

## 输入与不可变目标

1. 继承 `utm-3` 的 `UTM_3=verified`、`SSH_KEY_AUTH=verified`、同一 run、`vm_name`、VM IP、config UUID 和 host key。缺失时只对同一 run 执行 `utm-3` 恢复入口；不得创建第二个账号或改选 VM。
2. `share` 只能是当前 `${SUBMISSION_SHARED_DIR}`，必须为绝对、已存在、非符号链接目录。`source_uuid` 来自 `${SUBMISSION_VM_TEMPLATE}/config.plist`，`target_uuid` 来自当前 bundle 的 `config.plist`；二者必须不同。
3. 所有 SSH 都绑定 `${SUBMISSION_SSH_PRIVATE_KEY}`、`BatchMode=yes`、精确 `<vm_name>@<vm-ip>`。不得使用 `demo`、其他地址或默认身份。

## 正常关机与 UTM Registry 共享

1. 两次读取 `utmctl status <vm-name>`。VM 为 running 时，使用继承 key 从 guest 正常关机；不得使用强停或其它电源路径：

```bash
private_key="${SUBMISSION_SSH_PRIVATE_KEY}"
ssh -tt -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" -o ConnectTimeout=5 <vm-name>@<vm-ip> "sudo /sbin/shutdown -h now"
```

连接中断不是失败证据；只读轮询同一 `utmctl status` 直到 `stopped`。
2. VM stopped 后，确认 UTM 进程未运行，精确同步共享配置。helper 只可复制模板中同路径、已有的只读 bookmark 到当前 UUID，不生成或猜测任何 bookmark：

```bash
target_uuid="$(/usr/libexec/PlistBuddy -c 'Print :Information:UUID' "$bundle/config.plist")"
source_uuid="$(/usr/libexec/PlistBuddy -c 'Print :Information:UUID' "${SUBMISSION_VM_TEMPLATE}/config.plist")"
share="${SUBMISSION_SHARED_DIR}"
test -d "$share" -a ! -L "$share"
test "$target_uuid" != "$source_uuid"
! pgrep -x UTM
python3 scripts/utm_registry_share.py sync --source-uuid "$source_uuid" --target-uuid "$target_uuid" --share-path "$share"
python3 scripts/utm_registry_share.py verify --target-uuid "$target_uuid" --share-path "$share"
```

输出 `UTM_SHARE_READONLY=verified` 后才继续。多项、书签为空、路径不同或 UTM 进程存在时只做三轮只读分类，不导入 preferences。
3. 本技能不启动、不打开目标克隆机。完成共享同步后记录 `VM_START_GUARD=blocked`；后续需要运行态时只接管外部已启动的同一 UUID，状态不明时只读复核，不执行任何启动动作。

## 挂载与只读回读

1. 新 BatchMode SSH 确认最终用户与 admin 组，并要求精确目录存在：

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" -o ConnectTimeout=5 <vm-name>@<vm-ip> 'id -un; id -Gn; test -d "/Volumes/My Shared Files/共享文件"; printf "MOUNT_PATH=/Volumes/My Shared Files/共享文件\n"'
```

2. 以单一 probe 验证只读。成功创建 probe 即为失败，立即删除后停止：

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" -o ConnectTimeout=5 <vm-name>@<vm-ip> '/bin/zsh -s' <<'EOF'
set -euo pipefail
mount='/Volumes/My Shared Files/共享文件'
probe="$mount/.codex_readonly_probe_$$"
if /usr/bin/touch "$probe"; then
  /bin/rm -f "$probe"
  printf 'READONLY_PROBE=writable_failure\n'
  exit 1
fi
test ! -e "$probe"
printf 'MOUNT_PATH=/Volumes/My Shared Files/共享文件\n'
printf 'READONLY_PROBE=verified\n'
EOF
```

3. 目录缺失或 probe 可写时，保留 `/Volumes` 列表和 helper 回读；正常停机后只重跑本技能共享同步与本节回读。三轮耗尽前不得交接 `utm-4`。

## 跨重启 Remote Login、电源与屏保策略

1. 通过 SSH 以 root 写入 `/Library/Application Support/submission-vm-bootstrap/bootstrap.sh`、`/Library/LaunchDaemons/com.submission.vm-bootstrap.plist`、`/Library/LaunchAgents/com.submission.no-idle-screensaver.plist`。三个文件必须 root:wheel；脚本 mode `755`，plist mode `644`。
2. bootstrap 脚本只运行以下有效设置，并写入完成标记和非敏感日志：

```bash
systemsetup -setremotelogin on
pmset -a displaysleep 0 sleep 0 disksleep 0 powernap 0 ttyskeepawake 1 tcpkeepalive 1 standby 0
```

LaunchAgent 在每个用户会话运行 `defaults write com.apple.screensaver idleTime -int 0`。
3. 载入系统 daemon 后，在新的 SSH 连接中回读完成标记、日志、`systemsetup -getremotelogin`、`pmset -g custom` 与当前用户：

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" -o ConnectTimeout=5 <vm-name>@<vm-ip> 'systemsetup -getremotelogin; pmset -g custom; defaults -currentHost read com.apple.screensaver idleTime'
```

4. 正常重启同一 guest 后，使用新 SSH 再读取上述值、LaunchDaemon 的 `runs` 与 `last exit code`。只有 `Remote Login: On`、`displaysleep 0`、`sleep 0`、`disksleep 0`、`powernap 0`、`standby 0`、`ttyskeepawake 1`、`tcpkeepalive 1` 和 `idleTime=0` 全部精确匹配才记录：

```text
REMOTE_LOGIN_PERSISTENCE=verified
PMSET_PERSISTENCE=verified
SCREENSAVER_IDLETIME=0
```

## 禁止动作与最后出口

- 不得修改 CPU、内存、磁盘、显示、网络、模板或其它 VM 项；共享只允许当前 UUID、当前 `$share` 的单项。
- 不得删除其他 Registry 条目、重建 bookmark、在系统盘创建 VM，或把共享父目录当作成功证据。
- 每个最后出口完成三轮同一目标的诊断、可安全修复和独立复验，保留 `AUTO_RECOVERY_ATTEMPTS`、`AUTO_RECOVERY_ACTIONS`、`AUTO_RECOVERY_RESULT`，再使用：

```bash
python3 services/feishu_bot.py notify-fault \
  --run-id '<current-run-id>' --chat-id '<original-chat-id>' \
  --stage 'vm-down:<fault-stage>' --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'vm-down' --recovery-attempts '<actual-count-at-least-3>' \
  --recovery-actions '<diagnose,repair,reverify>' --recovery-result '<exhausted|unrepairable>'
python3 services/feishu_bot.py wait-decision --run-id '<current-run-id>' --decision-kind fault --timeout-seconds 3600
```

`--recovery-result unrepairable` 必须同时追加 `--unrepairable`。`manual_continue`、`retry_skill` 都只重读同一 run、VM、UUID、share 和 SSH 身份。

少于三轮时运行时拒绝发卡。

## 完成与交接

成功必须同时有：

```text
UTM_SHARE_READONLY=verified
MOUNT_PATH=/Volumes/My Shared Files/共享文件
READONLY_PROBE=verified
REMOTE_LOGIN_PERSISTENCE=verified
PMSET_PERSISTENCE=verified
SCREENSAVER_IDLETIME=0
SSH_KEY_AUTH=verified
VM_DOWN=verified
```

仅当全部标记均由新回读取得后，将同一 run、`vm_name`、IP、SSH key、挂载路径和 Registry 证据交接给 `utm-4`。阻断或未完成状态不得交接。
