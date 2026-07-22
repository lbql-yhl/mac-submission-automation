---
name: files
description: "Use after utm-5 when the guest macOS shared directory is mounted and its contents must be copied into the logged-in VM user's Downloads directory over SSH."
---

# Files

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
  --stage 'files:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'files' \
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
| SSH/挂载暂时不可用 | 同一 VM 恢复 SSH 三轮；重新检查唯一只读挂载，不改选路径 | 恢复耗尽才发卡 |
| `ditto` 中断/漏项 | 逐项比较源/目标；只对缺失或哈希不符项重新复制一次，再全量复验 | 仍有差异才 `exhausted` |
| 目标已有同名冲突 | 哈希相同视为完成；不同则不覆盖，记录精确冲突 | 所有权无法证明为 `unrepairable` |
| 隐藏项遗漏 | 使用 `source/.` 重新执行一次并比较完整条目集合 | 三轮安全复制修复且每轮独立比较后仍不一致才发卡 |

## Overview

Copy the contents of the UTM guest shared-folder mount into the current guest user's `Downloads` directory. Preserve hidden files and subdirectories, leave the source untouched, and verify every copied entry.

## SSH 全自动约束

- 直接继承 `utm-5` 的 `UTM_5=verified`，以及 `utm-4` 的 `UTM_4=verified`、同一精确 VM/IP、`<vm_name>` 和 `SSH_KEY_AUTH=verified`；只做一次 `BatchMode=yes` 身份/存活检查，不重复配置 SSH。
- 检查失败时自动对同一 VM 刷新 IP、检查 Remote Login/端口并用固定 `1234` 恢复宿主机现有公钥；不得向用户索取密码、SSH Key 或 IP。
- 恢复后必须重新验证 `id -un=<vm_name>`、home 和 `admin`；仍不匹配则记录 `SSH_AUTO_RECOVERY=blocked`，先按 `files-ssh-auto-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定，禁止改选其他 VM。

## Preconditions

- Run only after `utm-5` has recorded `UTM_5=verified`, before `utm-clash`.
- Target the cloned UTM VM, never the `macOS` template or the host's own Downloads folder.
- Confirm SSH reaches the VM as `<vm_name>` with key-based/non-interactive authentication before sending the heredoc.
- In the guest, use `/Volumes/My Shared Files/共享文件` as the source. The host path `${SUBMISSION_SHARED_DIR}` is not the guest source path.

## Workflow

1. 先做完全只读的 guest 边界检查；身份确认前不得 `mkdir` 或复制：

```bash
name="<inherited-vm_name>"
vm_ip="<inherited-exact-vm-ip>"
run_id="<current-run-id>"
private_key="${SUBMISSION_SSH_PRIVATE_KEY}"
test -s "$private_key" -a ! -L "$private_key"
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
  -o ConnectTimeout=5 "$name@$vm_ip" \
  'printf "user=%s\nhome=%s\n" "$(id -un)" "$HOME"; id -Gn; test -d "/Volumes/My Shared Files/共享文件"; test ! -L "/Volumes/My Shared Files/共享文件"'
```

The username must equal `<vm_name>` and the groups must include `admin` when the workflow requires the administrator account. If the VM/host boundary or source mount is unclear, pause copying, re-resolve the same run/VM/IP, re-read `id -un`, home, groups and the exact mount in the bounded `files-boundary` recovery matrix, and independently reverify them. Only recovery exhaustion or a proven external ownership conflict may send the last global fault card and wait in the current executor.

2. 用远端 Python 只读生成源 manifest（相对路径、类型、符号链接目标、文件字节数/SHA-256），要求至少一个条目、`socks5.yml` 是非空常规非符号链接文件，并输出 `SOURCE_ENTRIES=>0`、manifest SHA-256 与 `SOCKS5_SOURCE_SHA256`。任何空源目录都失败，不能以 `0 missing/0 mismatched` 冒充成功。
3. 在复制前读取 `$HOME/Downloads/.submission-files-$run_id.json` 并逐个预检目标同名项：
   - 目标不存在或与源完全相同：安全；
   - 目标不同、marker 不存在或不属于当前 run/`vm_name`/同一源 manifest：`DEST_CONFLICTS>0`，禁止 `ditto`；
   - 目标不同但 marker 精确证明它是本次中断 attempt 已登记的源条目：只允许同一 attempt 修复该项。

   首次安全预检后先创建 Downloads，再以原子 replace 写入 mode-600 marker，绑定稳定 attempt 和源 manifest；新进程回读后记录 `COPY_PREFLIGHT=verified`、`DEST_CONFLICTS=0`。不得先复制再发现冲突。
4. Copy all source contents, including hidden files, without deleting unrelated files already in `Downloads`:

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
  "$name@$vm_ip" '/bin/zsh -s' <<'EOF'
set -euo pipefail
src='/Volumes/My Shared Files/共享文件'
dst="$HOME/Downloads"
test -d "$src"
test -f "$dst/.submission-files-<current-run-id>.json"
mkdir -p "$dst"
/usr/bin/ditto "$src/." "$dst/"
EOF
```

`ditto` may refresh only entries authorized by the successful preflight/marker. It never grants ownership of a pre-existing conflict, and the source is never removed.

5. Verify paths, types, symlink targets, and SHA-256 content for every source entry. Report failure if any entry is missing or differs; do not claim completion from directory existence alone.

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
  "$name@$vm_ip" '/usr/bin/python3 -' <<'PY'
from pathlib import Path
import hashlib, os
src = Path('/Volumes/My Shared Files/共享文件')
dst = Path('/Users') / os.environ.get('USER', '') / 'Downloads'
if not dst.is_dir():
    dst = Path.home() / 'Downloads'

def entries(root):
    return sorted(p.relative_to(root) for p in root.rglob('*'))

def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

missing, mismatched = [], []
for rel in entries(src):
    a, b = src / rel, dst / rel
    if not b.exists() and not b.is_symlink():
        missing.append(str(rel)); continue
    if a.is_symlink() or b.is_symlink():
        if not (a.is_symlink() and b.is_symlink() and os.readlink(a) == os.readlink(b)):
            mismatched.append(str(rel))
    elif a.is_dir() != b.is_dir() or a.is_file() != b.is_file():
        mismatched.append(str(rel))
    elif a.is_file() and sha256(a) != sha256(b):
        mismatched.append(str(rel))
print(f'source_entries={len(entries(src))}')
print(f'missing={len(missing)}')
print(f'mismatched={len(mismatched)}')
if not entries(src):
    raise SystemExit("empty source")
if missing or mismatched:
    raise SystemExit(1)
print('verification=passed')
PY
```

6. 用第二个全新 SSH 会话单独核对 `socks5.yml`：源/目标都必须是非空常规非符号链接文件，mode 不得让其他用户可写，两边 SHA-256 必须相同；不打印内容。更新 marker `status=complete` 后再读一次，成功证据为：

   ```text
   COPY_PREFLIGHT=verified
   SOURCE_ENTRIES=>0
   DEST_CONFLICTS=0
   missing=0
   mismatched=0
   SOCKS5_COPY_HASH=verified
   verification=passed
   FILES=verified
   ```

## Guardrails

- Do not use the host path as a guest path.
- Do not use Finder or GUI copy when SSH is available.
- Do not delete or move source files.
- Do not print passwords or place them in command arguments.
- Do not configure Clash Verge in this skill; that remains `utm-clash`.

## Completion Report

Report the VM name/IP, source and destination paths, SSH method, positive source-entry count, preflight conflict count, and verification result. Include `COPY_PREFLIGHT=verified`, `SOURCE_ENTRIES=>0`, `DEST_CONFLICTS=0`, `missing=0`, `mismatched=0`, `SOCKS5_COPY_HASH=verified`, and `verification=passed`; only then record `FILES=verified`.

## 连续交接

仅当本技能全部完成检查通过并记录 `FILES=verified` 时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-clash`；不得等待用户确认。阻断、失败或未完成状态不得交接。
