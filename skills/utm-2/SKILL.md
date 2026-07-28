---
name: utm-2
description: Use after utm-1 has started the exact cloned UTM macOS VM, to establish nonvisual SSH access and record guest machine identities.
---

# UTM-2

## 无视觉执行边界

本技能只允许 UTM CLI/Registry、配置 plist、ARP/lease、端口检查、SSH/PTY 和 guest shell 回读；其他交互方式不属于本技能。执行前运行：

```bash
eval "$(python3 scripts/preflight.py --project-only --emit-shell)"
```

本技能继承 [`../_shared/AUTOMATION_CONTRACT.md`](../_shared/AUTOMATION_CONTRACT.md) 的自动诊断、自动修复、自动复验和最后故障卡规则。`OP-NATIVE-PASTE`、`OP-BROWSER-URL-NO-SCHEME`、`OP-APPLE-PHONE-OTP`、`OP-FIXED-PASSWORD-1234`、`OP-USER-CONFIRMATION` 不在正常路径调用；固定密码只允许出现在目标明确的宿主 PTY 提示中，绝不进入 argv、管道、脚本、输出或日志。

## SSH 全自动约束

- 所有正常 SSH 回读绑定 `${SUBMISSION_SSH_PRIVATE_KEY}`、`IdentitiesOnly=yes` 与 `BatchMode=yes`。
- 仅当 BatchMode probe 失败时，使用宿主 PTY 的 `ssh-copy-id` 为同一 `demo` 安装现有公钥；密码只由匹配提示接收。
- Remote Login 的无视觉前提是模板或首启 bootstrap 已启用服务；本技能以精确 MAC、端口、SSH banner 和后续 BatchMode 认证作为服务证据。

## 本技能自动恢复矩阵

| 故障点 | 自动诊断、修复和复验 | 最后出口 |
|---|---|---|
| MAC→IP 无唯一交集 | 2/5/10 秒重读 config MAC、UTM CLI、ARP 和同一 VM lease；只接受精确交集 | 三轮仍为零/多候选 |
| 22/SSH 不通 | 核对同一 VM started、MAC、IP、端口和 SSH banner；Remote Login 已可 SSH 时才用 `systemsetup` 修复 | 无 SSH 时记录 `SSH_AUTO_RECOVERY=blocked` |
| 公私钥缺失/权限错误 | 保留现有私钥；仅生成缺失私钥或从私钥导出缺失 `.pub`；重装同一公钥并核对权限/指纹 | 三轮后仍不一致 |
| guest 三码不唯一或冲突 | 三个新 SSH 会话读取固定两键，并对当前 run、当前配置 MachineIdentifier 与历史登记逐项比较；不启动源模板、不读取模板 guest 三码 | 持续缺失、重复或归属冲突 |

## 输入与前置状态

1. 继承 `utm-1` 已记录的同一 `run_id`、`vm_name`、bundle、config UUID 和 `UTM_1=verified`；不得按最新、名称相似或同子网对象替换。
2. 要求精确 VM 在 `utmctl list` 中为 `started`，并从 `$bundle/config.plist` 读取唯一 `Network[0].MacAddress`。配置 MAC 是 IP、guest MAC 与身份登记的唯一网络锚点。
3. 目标模板或首启 bootstrap 必须已提供 Remote Login。没有 SSH 通道时，本技能仅执行三轮精确只读诊断；不能以其它交互替代服务修复。

## MAC、IP 与 SSH 服务

1. 对 Apple backend VM，先读取模板和 clone 的 `System.MacPlatform.MachineIdentifier`；两者相同即为身份失效。正常停止同一 VM 后仅通过 `utm-clone-macos` 和 `utm-1` 重建同一目标；不得选用其他模板或 VM。
2. 规范化配置 MAC 后，以 ARP 和 UTM/lease 的交集解析唯一 IPv4。禁止扫描完整子网、接受第一个 ARP 项或把固定网段写进技能：

```bash
vm="<inherited-vm_name>"
bundle="${SUBMISSION_VM_IMAGES_DIR}/$vm.utm"
mac="$(/usr/libexec/PlistBuddy -c 'Print :Network:0:MacAddress' "$bundle/config.plist")"
resolve_vm_ip() {
  /usr/bin/python3 - "$mac" <<'PY'
import re, subprocess, sys

def normalize(value):
    return ":".join(f"{int(part, 16):02x}" for part in value.split(":"))

want = normalize(sys.argv[1])
rows = re.findall(r"\(([^)]+)\)\s+at\s+([0-9A-Fa-f:]+)", subprocess.check_output(["/usr/sbin/arp", "-an"], text=True))
matches = sorted({ip for ip, candidate in rows if normalize(candidate) == want})
if len(matches) != 1:
    raise SystemExit(f"VM_MAC_IP_MATCH_COUNT={len(matches)}")
print(matches[0])
PY
}
vm_ip="$(resolve_vm_ip)"
printf 'VM_CONFIG_MAC=verified\nIP_CANDIDATE_INTERSECTION_COUNT=1\nVM_IP_MATCH=verified\n'
```

`utmctl ip-address "$vm"` 支持时只保留规范 MAC 相等的 lease；其有一条而 ARP 为空时才对该单一地址 ping 一次再取交集。三轮仍非唯一则停止。
3. 对唯一 IP 检查端口与 SSH banner：

```bash
nc -vz -w 5 "$vm_ip" 22
ssh -o BatchMode=yes -o PreferredAuthentications=none -o PubkeyAuthentication=no -o ConnectTimeout=5 demo@"$vm_ip" exit
```

4. Remote Login 的服务证据固定为：精确 MAC→IP、`nc` 成功、SSH banner 可达、以及后续 `demo` BatchMode 身份成功。四项均通过才记录 `REMOTE_LOGIN=verified`、`SSH_SERVICE=verified`。无 SSH 时不得伪造该标记；服务修复由模板/首启 bootstrap 负责。

## host key 与 demo 认证

1. 固定复用 `${SUBMISSION_SSH_PRIVATE_KEY}` 与 `${SUBMISSION_SSH_PUBLIC_KEY}`；不覆盖现有私钥：

```bash
private_key="${SUBMISSION_SSH_PRIVATE_KEY}"
public_key="${SUBMISSION_SSH_PUBLIC_KEY}"
if ! test -s "$private_key"; then
  umask 077
  ssh-keygen -t ed25519 -N '' -f "$private_key"
fi
if ! test -s "$public_key"; then
  umask 077
  ssh-keygen -y -f "$private_key" >"$public_key"
fi
chmod 600 "$private_key"
chmod 644 "$public_key"
ssh-keygen -lf "$public_key" -E sha256
```

2. 先用 BatchMode probe；仅失败时在宿主 PTY 执行 `ssh-copy-id`：

```bash
ssh -o BatchMode=yes -o ConnectTimeout=5 -o IdentitiesOnly=yes -i "$private_key" demo@"$vm_ip" 'id -un' || ssh-copy-id -o StrictHostKeyChecking=accept-new -i "$public_key" demo@"$vm_ip"
```

3. 新 BatchMode SSH 独立核对 `demo`、`$HOME/.ssh` mode `700`、`authorized_keys` mode `600` 和 host/guest SHA-256 指纹。全部精确匹配才记录 `SSH_DEMO_KEY=verified`；失败按矩阵最多三轮修复同一对象，最终记录 `SSH_KEY_AUTH=blocked` 后走最后出口。

## guest 三码、MAC 与登记

1. 本技能不启动源模板、不打开模板控制台、不读取模板 guest 三码，也不从克隆机反向生成模板基线。只读取当前目标 VM 的 `System:MacPlatform:MachineIdentifier`，并与当前 run 的 clone marker 和 `runtime/guest-identities.json` 做唯一性校验；该策略记录 `TEMPLATE_GUEST_IDENTIFIERS=not_required_by_policy`。
2. 通过新 BatchMode SSH 会话读取当前 guest 三码和 guest `ifconfig`，要求精确两行：一个 `IOPlatformSerialNumber` 和一个 `IOPlatformUUID`，以及唯一一条 `ether` 等于配置 MAC：

```bash
guest_ids="$(ssh -o BatchMode=yes -o ConnectTimeout=5 -o IdentitiesOnly=yes -i "$private_key" demo@"$vm_ip" "ioreg -rd1 -c IOPlatformExpertDevice | grep -E 'IOPlatformSerialNumber|IOPlatformUUID'")"
test "$(printf '%s\n' "$guest_ids" | rg -c '"IOPlatformSerialNumber"')" -eq 1
test "$(printf '%s\n' "$guest_ids" | rg -c '"IOPlatformUUID"')" -eq 1
test "$(printf '%s\n' "$guest_ids" | wc -l | tr -d ' ')" -eq 2
ssh -o BatchMode=yes -o ConnectTimeout=5 -o IdentitiesOnly=yes -i "$private_key" demo@"$vm_ip" 'ifconfig'
printf 'GUEST_IDENTIFIER_LINES=2\nGUEST_MAC_MATCH=verified\n'
```

3. 与同 run config UUID、当前 clone marker MachineIdentifier 以及 `${PROJECT_ROOT}/runtime/guest-identities.json` 的已登记 pair 比较。pair 重复、被其他 run 占用或当前 MachineIdentifier 与已拒绝目标重复即为冲突。成功时原子更新 mode `600` 登记、独立回读并记录：

```text
VM_CONFIG_MAC=verified
IP_CANDIDATE_INTERSECTION_COUNT=1
VM_IP_MATCH=verified
REMOTE_LOGIN=verified
SSH_SERVICE=verified
SSH_DEMO_KEY=verified
TEMPLATE_GUEST_IDENTIFIERS=not_required_by_policy
GUEST_IDENTIFIER_LINES=2
GUEST_MAC_MATCH=verified
GUEST_IDENTITY_DIFF=verified
UTM_2=verified
```

## 禁止动作与最后出口

- 不得在宿主机运行 `ioreg`，不得使用 `utmctl exec`；Apple backend 不支持该操作。
- 不得改 CPU、内存、磁盘、显示、模板或任何其他 VM 设置。
- 后续技能连接失败时，only when that skill explicitly delegates SSH recovery 才可调用本技能恢复；后续技能自身的 attempt 边界优先。`utm-18` 出现 `SSH_EXIT=255` 时只检查该 attempt，不得重复业务命令。
- 每个最后出口必须完成三轮同一 VM 的诊断、可安全修复和独立复验，保留 `AUTO_RECOVERY_ATTEMPTS`、`AUTO_RECOVERY_ACTIONS`、`AUTO_RECOVERY_RESULT`，再使用 `notify-fault`/`wait-decision`；`--recovery-result unrepairable` 必须同时追加 `--unrepairable`。

```bash
python3 services/feishu_bot.py notify-fault \
  --run-id '<current-run-id>' --chat-id '<original-chat-id>' \
  --stage 'utm-2:<fault-stage>' --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-2' --recovery-attempts '<actual-count-at-least-3>' \
  --recovery-actions '<diagnose,repair,reverify>' --recovery-result '<exhausted|unrepairable>'
python3 services/feishu_bot.py wait-decision --run-id '<current-run-id>' --decision-kind fault --timeout-seconds 3600
```

`manual_continue` 和 `retry_skill` 都只重读并恢复同一 MAC/IP/VM；不得接受替换凭据、IP 或 VM。

少于三轮时运行时拒绝发卡。

## 连续交接

仅当 `UTM_2=verified` 后，原样交接同一 run、`vm_name`、VM IP、config MAC、guest identity registry 和 host key 给 `utm-3`。阻断、冲突或未完成状态不得交接。
