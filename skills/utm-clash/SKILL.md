---
name: utm-clash
description: "Use after files when the cloned UTM macOS VM is logged in as the VM-name administrator and Clash Verge must be configured inside that VM, then the local Downloads/socks5.yml profile imported and selected."
---

# UTM Clash

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
  --stage 'utm-clash:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-clash' \
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
| 配置/进程异常 | SSH 检查配置语法、profile 路径和进程；修复后重启 guest Clash 一次并复验 | 三轮 SSH/进程恢复后仍失败才发卡 |
| Profile/菜单误点 | 窗口尺寸/焦点变化或误点后至少 3 秒读取最新截图，`Escape` 关闭菜单，回到 Profiles 再右键唯一 `socks5.yml`；记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立核对后仍不能选中才 `exhausted` |
| 代理 check 未变延迟 | 每次重新截图并核对 PROXY/My-SOCKS5-Proxy，最多五次；随后重启 Clash 一次再做最终复验 | 全部耗尽才发卡 |
| 开关错位 | 逐项读当前值，只切换不匹配项；每项后等待并回读，误切立即恢复期望值 | 未完成逐项校正禁止发卡 |

## Overview

Configure Clash Verge inside the cloned UTM macOS VM after `files`, preferably over SSH by editing the app's own config files and restarting Clash Verge, then import and select the local `$HOME/Downloads/socks5.yml` profile. Do not edit the proxy contents or verify BrowserScan unless the user explicitly asks.

## SSH 全自动约束

- 直接继承 `files` 的 `FILES=verified`、同一 VM/IP、`<vm_name>` 和宿主机 Key；正常路径只做一次 `BatchMode=yes` 检查，不重新配置 SSH。
- BatchMode 失败时锁定同一精确 VM，最多三轮自动刷新 IP、检查 Remote Login/端口并用固定 `1234` 恢复 `${SUBMISSION_SSH_PUBLIC_KEY}`，每轮后重新验证用户/home/admin/指纹和 BatchMode；自动恢复阶段无需人工确认，也不得向用户索取信息或仅因认证失败改走 GUI。三轮后仍失败时记录 `SSH_AUTO_RECOVERY=blocked`，先按 `utm-clash-ssh-auto-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；`manual_continue` 重查同一 VM，`retry_skill` 重跑同三轮恢复。
- GUI fallback 只处理 Clash Verge 配置文件不存在或可见状态与文件不一致，不承担 SSH 认证恢复。

## Preconditions

- Run only after `files` has recorded `FILES=verified` and the cloned VM is logged in as `<vm_name>`.
- Operate inside the UTM guest macOS desktop, not on the host Mac.
- Reuse the current Feishu-run `vm_name`; never operate on the `macOS` source template.
- Confirm Clash Verge is installed in the guest VM before changing settings.
- Confirm `socks5.yml` exists at `$HOME/Downloads/socks5.yml`; if missing, 自动重新执行 `files` for the same run/VM and skip its already verified copy checks, then recheck this exact path. If it is still missing, compare the exact shared source, mount, target ownership and SHA-256 through the `utm-clash-socks5-missing` recovery matrix and repair only the first failed reversible step. Only exhausted recovery or a proven external source-data fault may send the last global fault card; never select another VM or a different profile file.

## SSH Workflow

1. Confirm non-interactive SSH logs into the cloned VM as `<vm_name>`:

```bash
name="<inherited-vm_name>"
vm_ip="<inherited-exact-vm-ip>"
private_key="${SUBMISSION_SSH_PRIVATE_KEY}"
test -s "$private_key" -a ! -L "$private_key"
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
  "$name@$vm_ip" 'id -un; id -Gn; sw_vers -productVersion; test -f "$HOME/Downloads/socks5.yml" -a ! -L "$HOME/Downloads/socks5.yml"'
```

The username must equal `<vm_name>` and groups must include `admin`. If `BatchMode` fails, run the automatic exact-VM SSH recovery above and recheck; never run the long heredoc through a password prompt or ask the user.

2. Configure Clash Verge files. Do not allocate a TTY because interactive zsh can mangle heredocs. Enumerate every candidate below `$HOME/Library/Application Support` and keep only directories containing both regular non-symlink `verge.yaml` and `config.yaml`. The canonical directory is not accepted merely because it is first; require exactly one complete candidate and record `CONFIG_DIR_MATCH_COUNT=1`. Zero or multiple candidates are read-only recovery states.

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
  "$name@$vm_ip" '/bin/zsh -s' <<'EOF'
set -euo pipefail
APP_DIR="$(/usr/bin/python3 - <<'PY'
from pathlib import Path
root = Path.home() / "Library/Application Support"
candidates = []
for verge in root.rglob("verge.yaml"):
    parent = verge.parent
    config = parent / "config.yaml"
    if "clash" not in str(parent).lower() or "verge" not in str(parent).lower():
        continue
    if verge.is_file() and not verge.is_symlink() and config.is_file() and not config.is_symlink():
        candidates.append(parent.resolve())
candidates = sorted(set(candidates))
if len(candidates) != 1:
    raise SystemExit(f"CONFIG_DIR_MATCH_COUNT={len(candidates)}")
print(candidates[0])
PY
)"
printf 'CONFIG_DIR_MATCH_COUNT=1\n'

if /usr/bin/pgrep -x "Clash Verge" >/dev/null 2>&1; then
  /usr/bin/osascript -e 'tell application "Clash Verge" to quit'
  /bin/sleep 3
  if /usr/bin/pgrep -x "Clash Verge" >/dev/null 2>&1; then
    printf 'CLASH_QUIT=failed\n'; exit 3
  fi
fi

/usr/bin/python3 - "$APP_DIR/verge.yaml" "$APP_DIR/config.yaml" <<'PY'
from pathlib import Path
import os, re, sys, uuid

paths = [Path(value) for value in sys.argv[1:]]
expected = {
    paths[0]: {
        "enable_tun_mode": "true",
        "enable_system_proxy": "false",
        "enable_auto_launch": "true",
        "enable_silent_start": "true",
    },
    paths[1]: {"ipv6": "false", "unified-delay": "true"},
}
before = {path: path.read_bytes() for path in paths}

def render(path, values):
    text = before[path].decode("utf-8")
    lines = text.splitlines()
    for key, value in values.items():
        pattern = re.compile(rf"^{re.escape(key)}\s*:")
        indexes = [i for i, line in enumerate(lines) if pattern.match(line)]
        if len(indexes) > 1:
            raise RuntimeError(f"duplicate top-level key: {key}")
        replacement = f"{key}: {value}"
        if indexes:
            lines[indexes[0]] = replacement
        else:
            lines.append(replacement)
    return ("\n".join(lines) + "\n").encode()

try:
    staged = {}
    for path, values in expected.items():
        payload = render(path, values)
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        with tmp.open("xb") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        tmp.chmod(path.stat().st_mode & 0o777)
        staged[path] = tmp
    for path in paths:
        os.replace(staged[path], path)
    for path, values in expected.items():
        text = path.read_text()
        for key, value in values.items():
            hits = re.findall(rf"(?m)^{re.escape(key)}\s*:\s*{value}\s*$", text)
            if len(hits) != 1:
                raise RuntimeError(f"readback failed: {key}")
except BaseException:
    for path, payload in before.items():
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.restore")
        with tmp.open("xb") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        tmp.chmod(path.stat().st_mode & 0o777)
        os.replace(tmp, path)
    raise
finally:
    for tmp in locals().get("staged", {}).values():
        tmp.unlink(missing_ok=True)
print("CONFIG_WRITE=atomic_verified")
PY

/usr/bin/open -a "Clash Verge"
/bin/sleep 5
if ! /usr/bin/pgrep -x "Clash Verge" >/dev/null 2>&1; then
  printf 'CLASH_PROCESS=missing\n'; exit 4
fi
printf 'CLASH_PROCESS=verified\n'

/usr/bin/python3 - "$APP_DIR/clash-verge.yaml" <<'PY'
from pathlib import Path
import re, sys
p = Path(sys.argv[1])
if not p.is_file() or p.is_symlink():
    raise SystemExit("runtime config missing")
lines = p.read_text().splitlines()
def top(key, value):
    hits = [line for line in lines if re.fullmatch(rf"{re.escape(key)}\s*:\s*{value}\s*", line)]
    if len(hits) != 1:
        raise SystemExit(f"runtime key failed: {key}")
top("ipv6", "false")
top("unified-delay", "true")
tun = [i for i, line in enumerate(lines) if re.fullmatch(r"tun\s*:\s*", line)]
if len(tun) != 1:
    raise SystemExit("runtime tun block ambiguous")
base = len(lines[tun[0]]) - len(lines[tun[0]].lstrip())
enabled = False
for line in lines[tun[0] + 1:]:
    if line.strip() and len(line) - len(line.lstrip()) <= base:
        break
    if re.fullmatch(r"\s+enable\s*:\s*true\s*", line):
        enabled = True
if not enabled:
    raise SystemExit("runtime tun disabled")
print("RUNTIME_TUN=verified")
PY
EOF
```

3. Verify the output includes:
   - `CONFIG_DIR_MATCH_COUNT=1`
   - `CONFIG_WRITE=atomic_verified`
   - `enable_tun_mode: true`
   - `enable_system_proxy: false`
   - `enable_auto_launch: true`
   - `enable_silent_start: true`
   - `ipv6: false`
   - `unified-delay: true`
   - `CLASH_PROCESS=verified`
   - `RUNTIME_TUN=verified`

4. If TUN does not start after restart, open Clash Verge once in the VM and handle the macOS authorization prompt; do not guess through SSH.

## Required Profile Import

Import the proxy profile after the SSH configuration and restart. This step is required even when the SSH configuration verification passes.

1. Verify the guest file without exposing its password:

```bash
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" "$name@$vm_ip" \
  'test -f "$HOME/Downloads/socks5.yml" && ls -l "$HOME/Downloads/socks5.yml"'
```

2. In the guest VM, open Clash Verge and select `Profiles`.
3. Choose the local-file import action (`Import`, `Import from file`, or the equivalent label).
4. Select `/Users/<vm_name>/Downloads/socks5.yml`; do not select the host path `${SUBMISSION_SHARED_DIR}/socks5.yml`.
5. Wait for the profile to appear, then select the imported `socks5.yml` profile as the active profile.
6. Confirm the imported profile is selected and the required settings remain unchanged: Tun Mode on, System Proxy off, Auto Launch on, Silent Start on, IPv6 off, Unified Delay on.

### Proven GUI method for selecting the local profile

The UTM guest display is a canvas/WebView, so host-level right-click injection may be swallowed. Use the current Computer Use `node_repl`/`sky` runtime for this part; this is an operation driver, not another project workflow skill:

1. Load the currently installed `computer-use:computer-use` skill and initialize the runtime exactly as that live skill documents; never depend on a versioned plugin-cache path. Then call `sky.get_app_state({app: "com.utmapp.UTM"})`.
2. Use the latest screenshot's image-space coordinates. Right-click the visible `socks5.yml` card with:

```js
await sky.click({app: "com.utmapp.UTM", x, y, mouse_button: "right"});
```

3. Read a fresh app state and screenshot. Only after the context menu visibly contains `Select`, click that menu item using coordinates from that fresh screenshot.
4. Read another fresh app state and confirm the menu closed and the `socks5.yml` card remains selected. Do not reuse coordinates from an older screenshot.
5. Open `Proxies`, locate the `PROXY` group, select `My-SOCKS5-Proxy`, and click its right-side check control once. Read a fresh screenshot: success requires the check control to change to a latency number (for example `306`). If it does not become a number, the click failed; re-read the latest screenshot and retry, up to 5 total attempts. Stop immediately when a number appears; do not click again after success. Five failed UI checks trigger the automatic diagnosis below, not an immediate card.

### 五次点击失败后的自动诊断

1. 保持同一 VM/Profile，先用 SSH 只读核对 Clash Verge 配置实际选中 `socks5.yml`、代理 host/port 与当前 run 一致且六个固定开关未漂移；不得打印用户名或密码。
2. 使用该 guest 当前 SOCKS5 监听端口做一次带超时的代理连通性/公网 IPv4 检查，并与当前 run 代理 IP 对账。若网络已通，只是 UI latency 未更新，重新打开同一 `Proxies` 页面并做一次最新截图检查，不再连续点按钮。
3. 配置未加载时只重写本技能管理的同一配置项、重启 Clash Verge 应用一次（不影响任何浏览器），等待其恢复后重新验证 profile、开关、监听端口和公网 IPv4；成功即记录 `PROXY_CHECK_RECOVERY=verified` 并继续。
4. 只有配置、进程、端口或代理出口经过上述修复仍失败，才记录 UI 五次 + 自动诊断/修复次数和 `AUTO_RECOVERY_RESULT=exhausted|unrepairable`，使用文件开头统一入口发送 `utm-clash-proxy-check` 最后故障卡。卡片继续决定也必须重新从第 1 项诊断，不能直接再发卡或复用旧回调。

Do not substitute CuaDriver pixel `right_click`, SSH, AppleScript, or CGEvent for this menu action; they were tested against the UTM WebView and did not open the menu. If macOS shows an automation permission prompt that visibly belongs to the current UTM/Computer Use action, automatically click `Allow` once and verify the prompt closes. No user confirmation or authorization is required. For an unknown or mismatched prompt, pause input and re-read its app/process/window ownership twice; only matrix exhaustion or a proven external prompt may use the last fault-card exit.

If the profile already exists, select the current `Downloads/socks5.yml` import rather than editing or duplicating proxy contents.

## GUI Settings Fallback

Use this only after SSH authentication is verified but the app config files cannot be found, Clash Verge cannot be restarted, or the visible settings disagree with the verified files. The required profile import above still applies.

1. Confirm the active desktop is the cloned UTM VM.
2. Open Clash Verge inside the guest VM:
   - Use Finder `Applications`, Launchpad, Spotlight, or the Dock, whichever is already available.
   - If the opened Clash Verge window belongs to the host Mac, pause all GUI actions, close no process, refocus the same run's guest window, and re-read the window/process ownership twice through `utm-clash-window-boundary`. Only if the exact guest window remains unavailable after the matrix is exhausted may the skill send the last global fault card and wait.
3. Click `Settings` in Clash Verge's left sidebar.
4. Set and visually confirm these final states:
   - `Tun Mode`: on
   - `System Proxy`: off
   - `Auto Launch`: on
   - `Silent Start`: on
   - `IPv6`: off
   - `Unified Delay`: on
5. If a setting row is not visible, scroll only within Clash Verge Settings until it is visible, then set it.
6. Leave Clash Verge open on Settings after verification.

## Guardrails

- Do not configure the host Mac's Clash Verge.
- Do not edit proxy profile contents, DNS, ports, language, theme, or startup script settings; only import and select the local `Downloads/socks5.yml` profile.
- Do not enable `System Proxy`; the required final state is off.
- Do not enable `IPv6`; the required final state is off.
- Do not continue if the VM/host boundary is unclear.

## Completion Report

Report the target VM name and confirm:

- Method used: SSH config update or GUI fallback.
- Profile: guest `$HOME/Downloads/socks5.yml` imported and selected.
- Proxy: `Proxies → PROXY → My-SOCKS5-Proxy` selected; after one check click, a latency number is acceptable confirmation.
- `Tun Mode=on`, `System Proxy=off`, `Auto Launch=on`, `Silent Start=on`, `IPv6=off`, `Unified Delay=on`.
- `UTM_CLASH=verified`.

## 连续交接

仅当本技能全部完成检查通过并记录 `UTM_CLASH=verified` 时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-6`；不得等待用户确认。阻断、失败或未完成状态不得交接。
