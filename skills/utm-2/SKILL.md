---
name: utm-2
description: Use when the user asks to run UTM-2 after UTM-1 has logged in to the cloned UTM macOS VM desktop, to enable or use SSH from the host and record the machine identifiers from ioreg.
---

# UTM-2

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
  --stage 'utm-2:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-2' \
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
| IP/22 端口/Remote Login | 仅按同一 VM MAC 刷新 IP，自动检查服务并修复，最多三轮 | 三轮后记录 `SSH_AUTO_RECOVERY=blocked` |
| 公私钥缺失/权限错误 | 保留现有私钥；缺失才生成，缺 `.pub` 才从私钥导出；修正 guest 权限并比较 SHA-256 | 私钥冲突或三轮指纹仍不一致才发卡 |
| identity 与模板/历史冲突 | 再读模板、当前 clone 和 guest 三码；若当前 clone 明确由本 run 创建，自动回到同 run 克隆重建一次 | 所有权不明或重建仍冲突为 `unrepairable` |
| BatchMode 失败 | 保存具体阶段，完成服务、IP、key 三层诊断后从失败层复验 | 未完成三层诊断禁止发卡 |

## Overview

Run this only after `utm-1` has recorded `UTM_1=verified` at the macOS desktop. Prefer SSH from the host into the VM; use VM Terminal only as a fallback.

## SSH 全自动约束

- `demo` 的固定密码始终为 `1234`；自动化只在宿主 PTY 的 SSH、`sudo` 或 macOS 授权提示中输入，绝不向用户索取密码、SSH Key、IP 或其他信息。
- 宿主机固定密钥为 `${SUBMISSION_SSH_PRIVATE_KEY}` 和 `${SUBMISSION_SSH_PUBLIC_KEY}`。私钥缺失时自动生成一次；私钥存在但 `.pub` 缺失时从现有私钥重新导出公钥，绝不覆盖现有私钥，也不为每台 VM 重建。
- 本技能自动把宿主公钥配置给 `demo`，核对 guest `authorized_keys` 权限和宿主/guest SHA-256 公钥指纹，并验证 `BatchMode=yes`。SSH 连接、认证或 Remote Login 首先全自动恢复；只能锁定当前 run 的同一精确 VM。自动恢复耗尽后使用本技能三按钮故障卡，不向用户索取密码、Key 或 IP。

## Workflow

1. Confirm the target UTM macOS VM is already at the desktop after `utm-1`.
2. For Apple backend VMs, compare the clone and template `System.MacPlatform.MachineIdentifier` before querying the guest:

```bash
cmp -s \
  <(plutil -extract System.MacPlatform.MachineIdentifier raw -o - ${SUBMISSION_VM_TEMPLATE}/config.plist) \
  <(plutil -extract System.MacPlatform.MachineIdentifier raw -o - ${SUBMISSION_VM_IMAGES_DIR}/<vm-name>.utm/config.plist)
```

If `cmp` returns `0`, the clone identity is invalid. Preserve the running scene, normally shut down the same VM when safe, and execute `utm-2-clone-identity` by rebuilding only the same run through `utm-clone-macos` and `utm-1`, then compare all identities again. Only exhausted same-run recovery or an unsafe ownership ambiguity enters the last global fault-card flow; never select another VM.

3. Find the VM IP from the host by matching only the exact normalized VM MAC. Never accept every entry in the `192.168.64.*` subnet as a candidate:

```bash
vm="<vm-name>"
mac="$(/usr/libexec/PlistBuddy -c 'Print :Network:0:MacAddress' "${SUBMISSION_VM_IMAGES_DIR}/$vm.utm/config.plist")"
resolve_vm_ip() {
  /usr/bin/python3 - "$mac" <<'PY'
import re, subprocess, sys

def normalize(value):
    return ":".join(f"{int(part, 16):02x}" for part in value.split(":"))

want = normalize(sys.argv[1])
rows = re.findall(
    r"\(([^)]+)\)\s+at\s+([0-9A-Fa-f:]+)",
    subprocess.check_output(["/usr/sbin/arp", "-an"], text=True),
)
matches = sorted({ip for ip, candidate in rows if normalize(candidate) == want})
if len(matches) != 1:
    raise SystemExit(f"VM_MAC_IP_MATCH_COUNT={len(matches)}")
print(matches[0])
PY
}
vm_ip="$(resolve_vm_ip)"
printf 'VM_IP_MATCH=verified\n'
```

If the exact MAC is not visible, do not scan a guessed address range. Build two independent candidate sets:

1. Run `utmctl ip-address "$vm"` when supported and keep only canonical IPv4 output tied to this exact UTM name/UUID.
2. Read macOS ARP plus the active UTM/DHCP lease files and keep only rows whose normalized MAC equals the config MAC.
3. If set 1 has one address but ARP is empty, ping only that one address once, then refresh set 2.
4. Intersect the sets; require exactly one canonical address and re-read config MAC before accepting it:

```text
VM_CONFIG_MAC=verified
IP_CANDIDATE_INTERSECTION_COUNT=1
VM_IP_MATCH=verified
```

Zero candidates repeat the same UTM-name/MAC query after 2/5/10 seconds. Multiple/different candidates are an identity ambiguity; never take the first IP, probe a whole subnet, or broaden to other running VMs.

4. If SSH is not open, repair it inside the same VM with this exact GUI closure:
   - Take two screenshots/process-window reads 3 seconds apart and require the UTM title and clone marker name equal `vm_name`; never act on host System Settings.
   - Open guest System Settings, wait/re-read, click `General`, wait/re-read, click `Sharing`, wait/re-read, and locate the unique `Remote Login` row.
   - If already on, do not toggle. If off, click its switch once; wait for the guest authentication sheet, require it belongs to System Settings in this guest and shows `demo`, then call `OP-FIXED-PASSWORD-1234` for this verified GUI authorization sheet and submit once.
   - Wait at least 3 seconds and re-read the same row; require it visibly says on. Re-resolve IP from the exact MAC and require port 22 plus an SSH banner. Record `REMOTE_LOGIN=verified` only when the visible state and network state both pass.
   - Unknown prompt/window ownership is checked twice without input. Retry the entire read/repair/reverify closure up to three cycles; never toggle off/on blindly.
5. Verify SSH is reachable after each repair cycle:

```bash
nc -vz -w 5 <vm-ip> 22
```

If three automatic repair cycles still cannot open port 22, independently re-read the exact VM state/MAC/IP/port once, record `SSH_SERVICE=blocked` with the last non-sensitive evidence, then send the last global fault card with stage `utm-2-ssh-service` and wait. Do not ask the user to supply SSH information and do not switch to another VM. `manual_continue` rechecks the same MAC/IP/port; `retry_skill` reruns the same automatic repair cycles and skips checks already verified.

6. Ensure the fixed host key exists, then install its public key for `demo` only when a BatchMode probe fails:

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
ssh -o BatchMode=yes -o ConnectTimeout=5 -o IdentitiesOnly=yes -i "$private_key" \
  demo@<vm-ip> 'id -un' || \
  ssh-copy-id -o StrictHostKeyChecking=accept-new -i "$public_key" demo@<vm-ip>
```

Run `ssh-copy-id` in a host PTY and let the automation enter the fixed `1234` when prompted. If the exact MAC-resolved IP has a stale host-key entry, remove only that IP with `ssh-keygen -R <vm-ip>` and retry once. Never ask the user to type or provide anything.

After installation, verify the exact key and permissions without printing key material:

```bash
host_fp="$(ssh-keygen -lf "$public_key" -E sha256 | awk '{print $2}')"
guest_meta="$(ssh -o BatchMode=yes -o ConnectTimeout=5 -o IdentitiesOnly=yes -i "$private_key" demo@<vm-ip> '
  test -s "$HOME/.ssh/authorized_keys" || exit 20
  printf "ssh_dir_mode=%s\n" "$(stat -f %Lp "$HOME/.ssh")"
  printf "authorized_keys_mode=%s\n" "$(stat -f %Lp "$HOME/.ssh/authorized_keys")"
  ssh-keygen -lf "$HOME/.ssh/authorized_keys" -E sha256
')"
printf '%s\n' "$guest_meta" | rg -F "SHA256:${host_fp#SHA256:}"
printf '%s\n' "$guest_meta" | rg '^ssh_dir_mode=700$'
printf '%s\n' "$guest_meta" | rg '^authorized_keys_mode=600$'
```

Any missing file, key-generation/export failure, `ssh-copy-id` failure, fingerprint mismatch, permission mismatch, or failed BatchMode identity check must run the `utm-2-ssh-key` matrix: preserve an existing private key, regenerate only a missing public key, repair guest ownership/modes, remove only the exact stale IP host-key entry when proven, reinstall the same public key and independently recheck fingerprint/BatchMode for up to three cycles. Only recovery exhaustion records `SSH_KEY_AUTH=blocked` and uses the last global fault-card exit. Exact fingerprint, permission, username, and BatchMode success record `SSH_DEMO_KEY=verified`.

7. Verify the SSH service and `demo` key authentication, then record `SSH_SERVICE=verified` and `SSH_DEMO_KEY=verified`:

```bash
private_key="${SUBMISSION_SSH_PRIVATE_KEY}"
ssh -o BatchMode=yes -o ConnectTimeout=5 -o IdentitiesOnly=yes -i "$private_key" \
  demo@<vm-ip> 'test "$(id -un)" = demo'
```

8. Before accepting guest identifiers, obtain the template baseline. The configured template must carry a mode-600 `.submission-template-identifiers.json` containing exactly one previously captured `IOPlatformSerialNumber` and `IOPlatformUUID` plus the template MachineIdentifier hash. Verify its schema, template realpath and MachineIdentifier hash twice and record `TEMPLATE_GUEST_IDENTIFIERS=verified`. If missing, the bounded recovery is a one-time read-only template-baseline capture: cleanly halt only when the current clone has no unsaved work, boot the exact configured template, log in as `demo`, read only the two `ioreg` keys, cleanly halt the template, atomically save the baseline, then restart the same clone and restore its SSH identity. Never modify the template account/key or substitute another VM; an unsafe/ambiguous baseline capture is a last-card infrastructure fault.

9. From the host, run:

```bash
private_key="${SUBMISSION_SSH_PRIVATE_KEY}"
guest_ids="$(ssh -o BatchMode=yes -o ConnectTimeout=5 -o IdentitiesOnly=yes -i "$private_key" \
  demo@<vm-ip> "ioreg -rd1 -c IOPlatformExpertDevice | grep -E 'IOPlatformSerialNumber|IOPlatformUUID'")"
test "$(printf '%s\n' "$guest_ids" | rg -c '"IOPlatformSerialNumber"')" -eq 1
test "$(printf '%s\n' "$guest_ids" | rg -c '"IOPlatformUUID"')" -eq 1
test "$(printf '%s\n' "$guest_ids" | wc -l | tr -d ' ')" -eq 2
printf '%s\n' "$guest_ids"
```

10. Compare both current values byte-for-byte with the verified template baseline and with every prior/rejected clone identity in `${PROJECT_ROOT}/runtime/guest-identities.json`. Either current key matching its corresponding template value, a duplicate current pair, or a pair already owned by another run invalidates this clone. On success, atomically update the mode-600 registry with this run/`vm_name`/config UUID/two value hashes, independently reread it, and record `GUEST_IDENTITY_DIFF=verified`. Do not print the registry or use a rejected identity as a new baseline.
11. A password prompt in steps 9–10 means key setup is incomplete and must be repaired automatically before continuing. Success requires every marker below from fresh reads:

```text
VM_CONFIG_MAC=verified
IP_CANDIDATE_INTERSECTION_COUNT=1
REMOTE_LOGIN=verified
SSH_SERVICE=verified
SSH_DEMO_KEY=verified
TEMPLATE_GUEST_IDENTIFIERS=verified
GUEST_IDENTIFIER_LINES=2
GUEST_IDENTITY_DIFF=verified
UTM_2=verified
```

## Guardrails

- Do not run `ioreg` directly on the host Mac.
- Do not change VM settings during this skill.
- Do not use `utmctl exec` for Apple backend macOS VMs; it reports that the operation is not supported by the backend.
- If `IOPlatformSerialNumber` or `IOPlatformUUID` matches the source/template or a rejected clone, mark the VM invalid and rebuild it.
- Success requires 精确两行: one unique `IOPlatformSerialNumber` and one unique `IOPlatformUUID`. If the command returns fewer or more than those two lines, duplicates either key, or omits either key, keep the exact non-sensitive output, rerun the read-only command through three fresh SSH sessions after identity verification, and reconcile the fixed keys through `utm-2-guest-identifiers`. Only persistent missing/duplicate identifiers after recovery exhaustion enter the last global fault-card flow; do not invent values.
- A Terminal fallback is only for recording guest identifiers; do not continue to `utm-3` until Remote Login and host SSH are working.
- Never request a user-supplied password or public key. The only `manual_continue` path is the standard three-button fault-card callback after automatic recovery has already been exhausted; it rechecks the same exact VM and never accepts replacement credentials.
- If SSH drops during a later skill, use this repair procedure only when that skill explicitly delegates SSH recovery. The later skill's own ambiguity and retry boundary takes precedence; never automatically rerun its command. In particular, `utm-18` with `SSH_EXIT=255` permits only read-only inspection of that attempt and does not delegate rerun authorization.

## 连续交接

仅当本技能全部完成检查通过并记录 `UTM_2=verified` 时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-3`；不得等待用户确认。阻断、失败或未完成状态不得交接。
