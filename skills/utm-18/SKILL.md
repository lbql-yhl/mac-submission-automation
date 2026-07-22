---
name: utm-18
description: Use after utm-17 when the same UTM macOS guest must relaunch Microsoft Edge with CDP, verify Apple Developer Account login, and run the description-fill npm command.
---

# UTM-18：启动 Edge CDP 并通过 SSH 填写应用描述

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
  --stage 'utm-18:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-18' \
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
| Edge 启停/登录页误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图，回到本轮 CDP Edge/Account 锚点重做可逆导航，记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立确认后仍失败才发卡 |
| SSH 255 | 恢复同一 VM 后只读检查同一日志、status 和进程 | attempt 不明为 `unrepairable`，禁止重跑 |
| 已知 npm 失败 | 完整日志、status、进程和 App Store Connect 当前状态共同分类；只有四方证据证明旧 attempt 已结束且 `ZERO_BUSINESS_SIDE_EFFECTS=verified`，才允许确定性修复后创建一个新 attempt | 有任何部分副作用、无法对账或再次失败才发卡 |
| status/log 不一致 | 不猜最新日志；只用持久化的精确路径和 attempt ID 三轮复查 | 仍 ambiguous 才发卡 |

## SSH 全自动约束

- 直接继承 `utm-17` 的同一精确 VM/IP、`<vm_name>` 和 `SSH_KEY_AUTH=verified`；所有宿主 SSH 调用统一使用 `-o BatchMode=yes -o ConnectTimeout=5`，不重复配置 SSH。
- SSH 服务、IP、Key 或认证失败时，自动按同一 VM 的精确 MAC 刷新 IP、检查 Remote Login/端口，并用固定 `1234` 恢复 `${SUBMISSION_SSH_PUBLIC_KEY}`；不得向用户索取任何信息。自动恢复仍失败时记录 `SSH_AUTO_RECOVERY=blocked`，先按 `utm-18-ssh-auto-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
- SSH 自动恢复与 `npm run fill:description` 的非幂等重跑是两件事：`manual_continue` 或 `retry_skill` 后都先恢复连接并只读检查同一轮日志、状态和进程；状态未唯一确认前绝不启动第二次业务命令。

## 前置条件

- `utm-17=verified`，继续使用同一台已启动的 VM、同一 `vm_name` 和 SSH 用户。
- Edge 停止、启动和检查继续使用分开的宿主 SSH 调用；`npm run fill:description` 改为前台 SSH 调用，不打开或操作 guest Terminal。
- 本技能是项目唯一既定的 guest Microsoft Edge 重启例外；不得关闭、启动或切换宿主 Google Chrome。
- Edge 相关的每个 SSH 命令执行后先检查退出码和错误输出，再等待至少 5 秒。业务命令不得使用 `nohup`、`&` 或本地管道隐藏 SSH 退出码。
- 不执行 `env`、`printenv` 或 `cat .env`，不输出 `.env`、账号、密码、手机号、短信链接、验证码或 token；只校验非敏感环境状态。
- 如需重新登录 Apple Developer，Notion 凭据只通过 `${PROJECT_ROOT}/scripts/notion_api.py` 读取；不得用宿主浏览器或插件读取 Notion。

## 操作步骤

1. 确认目标 VM 为 `utm-17` 使用的 VM 且状态为 `started`。先用只读 SSH 确认 `id -un` 为 `<vm_name>`、`$HOME` 为 `/Users/<vm_name>`；不匹配时先按 `utm-18-identity` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
2. 先用只读 SSH 执行 `pgrep -fl '/Microsoft Edge( |$)'` 并保存旧进程计数。计数大于 0 时才单独执行 `pkill -x "Microsoft Edge"`；退出码 `0` 表示本轮发出停止信号，退出码 `1` 只有在新的只读 `pgrep` 已证明进程数为 0 时才是“本来就未运行”的合法幂等状态，其他退出码均失败。等待至少 5 秒，再用新的只读 SSH 连续两次确认旧 Edge 进程不存在；两次检查间隔至少 5 秒，成功记录 `EDGE_OLD_PROCESS=stopped`。
3. 单独通过 SSH 后台启动 Edge；这里的 `nohup` 和 `&` 只允许用于浏览器进程：

   ```bash
   nohup "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" \
     --remote-debugging-port=9222 \
     --user-data-dir=/tmp/edge-debug-profile \
     --no-first-run \
     > /tmp/utm-18-edge.log 2>&1 < /dev/null &
   ```

   等待至少 5 秒，再用新的只读 SSH 检查并同时满足：进程的可执行文件是 `Microsoft Edge`，命令行唯一包含 `--remote-debugging-port=9222` 和 `--user-data-dir=/tmp/edge-debug-profile`；`/tmp/utm-18-edge.log` 无启动错误；只有该进程监听 guest `127.0.0.1:9222`；`curl -fsS --max-time 5 http://127.0.0.1:9222/json/version` 返回一个 JSON 对象，且唯一非空 `webSocketDebuggerUrl` 指向 `ws://127.0.0.1:9222/`。不得输出完整 JSON。成功记录 `EDGE_CDP_PROCESS=verified`、`EDGE_CDP_PORT_9222=verified` 和 `EDGE_CDP_HTTP=verified`。
4. 返回同一 guest，等待至少 3 秒并读取最新画面。只在刚启动的 Edge 中新建 tab，调用 `OP-BROWSER-URL-NO-SCHEME` 并执行 `printf '%s' 'developer.apple.com/account/' | python3 scripts/shared_operations.py browser-url --allow-bare`；只有 `BROWSER_URL_CLIPBOARD=verified` 且 `Paste and Go` 已蓝色高亮才确认一次，粘贴后立即清空剪贴板：
   1. 先确认当前窗口属于精确 VM、进程属于上述 CDP Edge、地址栏是当前新 tab；每次点击、粘贴或导航后等待至少 3 秒并读取新截图。
   2. 页面已显示 `Account` 标题和账号头像时，不重新登录；仍要执行 `verify-parent` 和 `read-field --heading '账号信息' --label '邮箱：' --copy`，仅用可见完整账号或唯一掩码后缀/域名证明是同一账号，随后清空剪贴板。
   3. 出现登录表单时，每个字段前都重新执行 `verify-parent`；邮箱只读精确标签 `邮箱：`，密码先读 `修改后的密码：`，只有 API 安全元数据证明它为空时才读 `初始密码：`。每次把值写入宿主原生剪贴板、用 `pbpaste` 做字节/hash 核对、右键目标字段并点击当前可见 `Paste`；粘贴后读回邮箱可见值/密码 bullet 状态，立即清空剪贴板和 shell 变量，再点击一次当前可见 `Sign In`。
   4. 出现电话或短信验证时完整调用 `OP-APPLE-PHONE-OTP`：实时读取电话和短信平台，只点击唯一掩码尾号匹配项；在宿主 Terminal 请求当前响应并要求唯一新六位 `Apple Account Code is:`，再按 `OP-NATIVE-PASTE` 只粘贴到首个验证码框。Apple 消费或拒绝后立即清空剪贴板和 `code/body/SMS_URL`；过期码不得重用。
   5. 已知本机密码提示调用 `OP-FIXED-PASSWORD-1234`；当前账号的 `Allow/Trust` 自动处理。CAPTCHA、账号锁定、账号不匹配、零/多 OTP 或未知安全挑战按 5/10/20 秒完成三轮独立只读复核并回到同一页面锚点，三轮仍不可分类才进入最后故障卡。

   页面最终必须同时显示 `Account` 标题、匹配账号状态和稳定 URL，记录 `APPLE_DEVELOPER_ACCOUNT=verified`；未确认登录不得继续。不得用宿主 Chrome、Notion 插件、Playwright、CUA、坐标或浏览器剪贴板读取 Notion。
5. Apple Developer 登录确认后，先在宿主创建并持久化本轮 attempt；不能等业务 SSH 已开始后才从远端输出猜日志名：
   1. 校验 `<current-run-id>` 只匹配 `[A-Za-z0-9][A-Za-z0-9_-]{0,127}`、`vm_name` 只匹配四位小写字母。
   2. 在 `${PROJECT_ROOT}/runtime/utm-18-attempts/<current-run-id>/` 以 `uuid.uuid4().hex` 生成唯一 `UTM_18_ATTEMPT_ID`，用 `os.open(..., O_CREAT|O_EXCL|O_WRONLY, 0o600)` 原子创建 attempt JSON，内容固定保存 run、VM、IP、`prepared_at`、guest 日志绝对路径和 status 绝对路径；写完 `fsync` 文件和目录，权限必须回读为 `600`。
   3. guest 路径由该 ID 确定为 `/Users/<vm_name>/Downloads/utm-18-fill-description-<UTM_18_ATTEMPT_ID>.log` 及同名 `.status`。用一条独立 SSH 以 `noclobber` 创建两个 mode-600 普通文件，status 初始内容固定为 `ATTEMPT_ID=<id>`、`RUN_STATE=prepared`；新连接逐字回读路径、权限和 status。成功记录 `UTM_18_LOG_PATH=precommitted`。任一路径已存在都按碰撞停止，禁止覆盖或换成“最新”文件。

   宿主 ledger 必须按以下等价代码建立；标准输出只有 ID 和三个非敏感路径：

   ```bash
   run_id='<current-run-id>'
   vm_name='<vm_name>'
   vm_ip='<vm-ip>'
   attempt_meta="$(python3 - "$run_id" "$vm_name" "$vm_ip" <<'PY'
   import ipaddress, json, os, re, sys, uuid
   from datetime import datetime, timezone
   from pathlib import Path

   run_id, vm_name, vm_ip = sys.argv[1:]
   if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", run_id):
       raise SystemExit("RUN_ID_INVALID")
   if not re.fullmatch(r"[a-z]{4}", vm_name):
       raise SystemExit("VM_NAME_INVALID")
   ipaddress.IPv4Address(vm_ip)
   root = Path.cwd().resolve()
   ledger_dir = root / "runtime" / "utm-18-attempts" / run_id
   ledger_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
   ledger_dir.chmod(0o700)
   attempt_id = uuid.uuid4().hex
   log_path = f"/Users/{vm_name}/Downloads/utm-18-fill-description-{attempt_id}.log"
   status_path = f"{log_path}.status"
   final = ledger_dir / f"{attempt_id}.json"
   temp = ledger_dir / f".{attempt_id}.json.tmp"
   payload = json.dumps({
       "attempt_id": attempt_id,
       "run_id": run_id,
       "vm_name": vm_name,
       "vm_ip": vm_ip,
       "log_path": log_path,
       "status_path": status_path,
       "state": "prepared",
       "prepared_at": datetime.now(timezone.utc).isoformat(),
   }, sort_keys=True).encode()
   fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
   try:
       with os.fdopen(fd, "wb", closefd=True) as handle:
           fd = -1
           handle.write(payload)
           handle.flush()
           os.fsync(handle.fileno())
   finally:
       if fd >= 0:
           os.close(fd)
   os.replace(temp, final)
   dir_fd = os.open(ledger_dir, os.O_RDONLY)
   try:
       os.fsync(dir_fd)
   finally:
       os.close(dir_fd)
   if final.stat().st_mode & 0o777 != 0o600:
       raise SystemExit("LEDGER_MODE_INVALID")
   print("\t".join((attempt_id, log_path, status_path, str(final))))
   PY
   )" || exit 1
   IFS=$'\t' read -r UTM_18_ATTEMPT_ID UTM_18_LOG UTM_18_STATUS UTM_18_LEDGER <<< "$attempt_meta"
   unset attempt_meta
   ```

   然后创建并独立回读 guest 文件：

   ```bash
   ssh -i "$SUBMISSION_SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o BatchMode=yes \
     -o ConnectTimeout=5 "<vm_name>@<vm-ip>" \
     /bin/zsh -s -- "$UTM_18_LOG" "$UTM_18_STATUS" "$UTM_18_ATTEMPT_ID" <<'PRECOMMIT'
   set -euo pipefail
   log_path=$1; status_path=$2; attempt_id=$3
   [[ ${#attempt_id} -eq 32 && "$attempt_id" != *[^0-9a-f]* ]]
   [[ "$log_path" == "/Users/<vm_name>/Downloads/utm-18-fill-description-$attempt_id.log" ]]
   [[ "$status_path" == "$log_path.status" ]]
   umask 077
   set -o noclobber
   : > "$log_path"
   if ! {
     print -r -- "ATTEMPT_ID=$attempt_id"
     print -r -- "RUN_STATE=prepared"
   } > "$status_path"; then
     /bin/rm -f "$log_path"
     exit 1
   fi
   /bin/chmod 600 "$log_path" "$status_path"
   /bin/sync
   PRECOMMIT
   ssh -i "$SUBMISSION_SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o BatchMode=yes \
     -o ConnectTimeout=5 "<vm_name>@<vm-ip>" \
     /bin/zsh -s -- "$UTM_18_LOG" "$UTM_18_STATUS" "$UTM_18_ATTEMPT_ID" <<'VERIFY_PRECOMMIT'
   set -euo pipefail
   log_path=$1; status_path=$2; attempt_id=$3
   [[ -f "$log_path" && ! -L "$log_path" && ! -s "$log_path" ]]
   [[ -f "$status_path" && ! -L "$status_path" ]]
   [[ "$(/usr/bin/stat -f %Lp "$log_path")" == 600 ]]
   [[ "$(/usr/bin/stat -f %Lp "$status_path")" == 600 ]]
   [[ "$(/usr/bin/wc -l < "$status_path" | /usr/bin/tr -d ' ')" == 2 ]]
   /usr/bin/grep -Fqx "ATTEMPT_ID=$attempt_id" "$status_path"
   /usr/bin/grep -Fqx 'RUN_STATE=prepared' "$status_path"
   print 'UTM_18_LOG_PATH=precommitted'
   VERIFY_PRECOMMIT
   ```

6. 只有 attempt ledger 和远端路径预提交完成后，才在宿主 Terminal 前台执行以下唯一 SSH 运行器。所有 SSH 都显式使用已验证的 `-i "$SUBMISSION_SSH_PRIVATE_KEY" -o IdentitiesOnly=yes`。日志路径、status 路径和 attempt ID 作为已校验的三个参数传入；整段由宿主 shell 通过 SSH 标准输入送入 guest 的登录交互 zsh，不得粘贴到 guest Terminal：

   ```bash
   ssh -i "$SUBMISSION_SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o BatchMode=yes \
     -o ConnectTimeout=5 "<vm_name>@<vm_ip>" \
     '/bin/zsh -lic "source /dev/stdin"' <<'UTM18_REMOTE'
   set -o pipefail

   attempt_id="<UTM_18_ATTEMPT_ID>"
   log_path="/Users/<vm_name>/Downloads/utm-18-fill-description-<UTM_18_ATTEMPT_ID>.log"
   status_path="${log_path}.status"
   expected_user="<vm_name>"
   expected_home="/Users/<vm_name>"
   project_dir="$expected_home/Downloads/Fire_One_en1.2"

   if [[ "$(/usr/bin/id -un)" != "$expected_user" || "$HOME" != "$expected_home" ]]; then
     print -u2 -r -- "UTM18_PRECHECK=ssh_identity_mismatch"
     exit 90
   fi
   [[ ${#attempt_id} -eq 32 && "$attempt_id" != *[^0-9a-f]* ]] || {
     print -u2 -r -- "UTM18_PRECHECK=attempt_id_invalid"; exit 96;
   }
   [[ "$log_path" == "$expected_home/Downloads/utm-18-fill-description-$attempt_id.log" ]]
   [[ -f "$log_path" && ! -L "$log_path" && ! -s "$log_path" ]]
   [[ -f "$status_path" && ! -L "$status_path" ]]
   [[ "$(/usr/bin/stat -f %Lp "$log_path")" == 600 ]]
   [[ "$(/usr/bin/stat -f %Lp "$status_path")" == 600 ]]
   /usr/bin/grep -Fqx "ATTEMPT_ID=$attempt_id" "$status_path"
   /usr/bin/grep -Fqx 'RUN_STATE=prepared' "$status_path"

   cd "$project_dir" || { print -u2 -r -- "UTM18_PRECHECK=project_missing"; exit 91; }
   [[ -f package.json && -s .env ]] || { print -u2 -r -- "UTM18_PRECHECK=project_or_env_missing"; exit 92; }
   [[ "$(/usr/bin/grep -c '^CDP_ENDPOINT=' .env)" == "1" ]] || {
     print -u2 -r -- "UTM18_PRECHECK=cdp_endpoint_count_mismatch"
     exit 93
   }
   /usr/bin/grep -Fqx 'CDP_ENDPOINT=http://127.0.0.1:9222' .env || {
     print -u2 -r -- "UTM18_PRECHECK=cdp_endpoint_mismatch"
     exit 93
   }

   node_path="$(command -v node)" || { print -u2 -r -- "UTM18_PRECHECK=node_missing"; exit 94; }
   npm_path="$(command -v npm)" || { print -u2 -r -- "UTM18_PRECHECK=npm_missing"; exit 95; }
   print -r -- "SSH_LOGIN_SHELL=verified"
   print -r -- "NODE_PATH=$node_path"
   print -r -- "NPM_PATH=$npm_path"
   node --version || { print -u2 -r -- "UTM18_PRECHECK=node_version_failed"; exit 94; }
   npm --version || { print -u2 -r -- "UTM18_PRECHECK=npm_version_failed"; exit 95; }

   write_status() {
     local state="$1"
     local npm_exit="${2-}"
     local tee_exit="${3-}"
     local tmp="$status_path.tmp.$$"
     (
       umask 077
       {
         print -r -- "ATTEMPT_ID=$attempt_id"
         print -r -- "RUN_STATE=$state"
         [[ -z "$npm_exit" ]] || print -r -- "REMOTE_NPM_EXIT=$npm_exit"
         [[ -z "$tee_exit" ]] || print -r -- "REMOTE_TEE_EXIT=$tee_exit"
       } > "$tmp"
     ) || return 1
     /bin/chmod 600 "$tmp" &&
       /bin/mv -f "$tmp" "$status_path" &&
       /bin/sync
   }
   write_status running || exit 99

   npm run fill:description 2>&1 | /usr/bin/tee "$log_path"
   statuses=("${pipestatus[@]}")
   npm_rc="${statuses[1]}"
   tee_rc="${statuses[2]}"
   write_status finished "$npm_rc" "$tee_rc" || exit 99
   print -r -- "REMOTE_NPM_EXIT=$npm_rc"
   print -r -- "REMOTE_TEE_EXIT=$tee_rc"
   (( tee_rc == 0 )) || exit 98
   exit "$npm_rc"
   UTM18_REMOTE
   ssh_exit=$?
   printf 'SSH_EXIT=%s\n' "$ssh_exit"
   ```

   `/bin/zsh -lic` 必须加载与 guest 日常 Terminal 相同的登录/交互环境，再用 `command -v node`、`command -v npm`、成功的版本命令和 `.env` 中唯一固定 CDP 地址完成非敏感预检。不得以写死 `/usr/local/bin/npm` 代替环境加载，也不得 source `.env`。
7. 保持该 SSH 调用在前台直到自然结束。远端 `tee` 会把 npm 的 stdout/stderr 完整实时回传当前任务，同时写入预提交的 guest 日志；不得只保留 `tail`、截图或摘要。每个合法新 attempt 都先产生新的固定 ledger/log/status，旧文件不覆盖、不删除。heredoc 结束后立即用 `ssh_exit=$?` 捕获并打印 SSH 自身退出码 `SSH_EXIT=<值>`；远端状态以同一预提交 status 的 `REMOTE_NPM_EXIT` 和 `REMOTE_TEE_EXIT` 为准。
8. 使用 host ledger 中已经持久化的日志绝对路径，在新的只读 SSH 中验证 attempt ID、状态文件、权限、字节数、SHA-256 并完整输出日志；不得依赖业务连接打印路径，也不得猜测“最新文件”：

   ```bash
   ssh -i "$SUBMISSION_SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o BatchMode=yes \
     -o ConnectTimeout=5 "<vm_name>@<vm_ip>" \
     /bin/zsh -s -- "$UTM_18_LOG" "$UTM_18_ATTEMPT_ID" <<'UTM18_VERIFY'
   log_path="$1"
   attempt_id="$2"
   status_path="${log_path}.status"
   [[ -f "$log_path" && ! -L "$log_path" && -f "$status_path" && ! -L "$status_path" ]] || exit 101
   [[ "$(/usr/bin/stat -f %Lp "$log_path")" == "600" ]] || exit 102
   [[ "$(/usr/bin/stat -f %Lp "$status_path")" == "600" ]] || exit 103
   /usr/bin/grep -Fqx "ATTEMPT_ID=$attempt_id" "$status_path" || exit 104
   /bin/cat "$status_path"
   /usr/bin/wc -c "$log_path"
   /usr/bin/shasum -a 256 "$log_path"
   /bin/cat "$log_path"
   UTM18_VERIFY
   ```

   这次 `cat` 必须完整回传，不得截成片段。向用户报告日志绝对路径、字节数和 SHA-256，使完整输出可随时通过只读 SSH 再查看；最终摘要不得复述日志中的敏感值。
9. 只有 `SSH_EXIT=0`、status 的 `ATTEMPT_ID` 与 host ledger 相同、状态文件为 `RUN_STATE=finished`、`REMOTE_NPM_EXIT=0`、`REMOTE_TEE_EXIT=0`、日志验证成功，且完整日志同时含原文 `增强版内购创建完成！` 和 `📊 统计信息: 共处理 14 个产品`、没有明确错误时，才标记 `FILL_DESCRIPTION=verified`。
10. 若 `SSH_EXIT=255`，把它视为 SSH 传输中断而不是 npm 成功或失败。先执行本节的同一精确 VM 全自动 SSH 恢复；恢复后只读检查 host ledger 指向的该轮日志、`.status` 和 `pgrep -fl 'npm run fill:description|fill-description'`：
   - `RUN_STATE=running` 且进程仍在：继续等待并只读查看同一日志，不启动第二次执行；
   - `RUN_STATE=finished`：按第 8、9 步核验；
   - `RUN_STATE=prepared`：业务命令未越过运行态提交，可修复预检后使用同一 attempt 启动一次；
   - `RUN_STATE=running` 但进程不存在、status 缺失/截断或与 ledger ID 不同：状态不明，记录 `FILL_DESCRIPTION=blocked_ambiguous`，先按 `utm-18-business-ambiguous` 执行恢复矩阵；恢复穷尽后才发送最后故障卡；不得猜测最新日志或自动重跑。
11. 在 SSH 已恢复且传输状态明确的前提下，任一环境预检、npm、`tee`、状态文件或日志验证失败时先暂停新的业务副作用，不得立刻发卡或盲重试。完整读取本轮唯一 ledger/log/status/进程与 App Store Connect 14 项当前状态并自动分类：
    - 业务命令尚未启动、status 仍为 `prepared` 的环境/路径/CDP/登录问题：修复同一环境，重新执行第 6 步预检；全部通过后只使用同一 prepared attempt 启动一次。
    - `tee` 失败但 npm 进程仍在：继续只读等待同一进程并从其 status/业务页面核对，不启动第二次。
    - npm 明确在处理任何产品前失败，且日志、status、进程和业务页面四方共同证明零业务副作用：记录 `ZERO_BUSINESS_SIDE_EFFECTS=verified`，修复明确根因，生成新的唯一 attempt/ledger/log 并自动重试一次。
    - 已产生任意部分业务结果：只读对账并保留证据，禁止创建新 attempt、禁止以“幂等”推定续跑；作为不可逆结果不明确进入最后故障卡。
    - 日志/status 缺失、部分结果无法唯一对账或修复后仍失败：记录恢复次数、动作和结果，才进入最后故障卡。

    最后故障卡使用文件开头唯一的统一命令，stage 为 `utm-18-fill-description`，并填写实际恢复次数、动作和结果；故障正文与 evidence 不得包含日志中的账号、密码、手机号、链接、验证码、联系人或 token。卡片必须发回当前运行原有 `chat_id`，严禁发到仅用于日报的 `AI-Infra业务团队` 群。

12. 只有飞书返回非空 `message_id` 后，才使用文件开头的 `wait-decision --decision-kind fault --timeout-seconds 3600` 等待本次决定。发送结果不明时只恢复同一稳定 UUID 的投递，禁止新建第二张卡。

    这不是 SSH 修复或凭据收集。收到反馈后不等待人工再次触发：
    - `stop`：原故障卡更新为已停止，立即停止整个流程并结束当前 run。
    - `manual_continue`：立即复核人工处理后的同一 VM、SSH、Edge/CDP、Apple 登录和第 5 步环境，从阻断点继续。
    - `retry_skill`：立即重跑当前技能 `utm-18`，继承同一 run/VM/日志现场，只跳过已验证成功的步骤；每个重新执行的业务命令都必须生成新的唯一日志。
13. `manual_continue` 或 `retry_skill` 都不能绕过第 8 至 11 步的状态判定；它们只是最后故障卡后的恢复入口。若本轮状态仍不明确，只能继续只读核验，禁止启动第二次业务命令；只有第 11 步产生 `ZERO_BUSINESS_SIDE_EFFECTS=verified` 时，才可创建一次新的 foreground attempt。再次失败也必须重新穷尽本轮自动恢复，仍失败才发送新故障卡并等待新决定。
14. 除第 11 步证明安全的新 attempt 外，不执行额外业务命令、不修改项目，也不运行发布或提审命令。成功或最后阻断后保留所有本轮 host ledger、guest 日志和状态文件。

## 完成标准

```text
UTM_17=verified
SSH_TARGET=verified
SSH_KEY_AUTH=verified
SSH_AUTO_RECOVERY=not_needed|verified
EDGE_OLD_PROCESS=stopped
EDGE_CDP_PROCESS=verified
EDGE_CDP_PORT_9222=verified
EDGE_CDP_HTTP=verified
APPLE_DEVELOPER_ACCOUNT=verified
SSH_LOGIN_SHELL=verified
NODE_NPM_ENV=verified
UTM_18_ATTEMPT_ID=verified
UTM_18_LOG_PATH=precommitted
UTM_18_LOG=verified
UTM_18_LOG_STATUS=finished
REMOTE_NPM_EXIT=0
REMOTE_TEE_EXIT=0
FEISHU_FAULT_DECISION=not_needed|manual_continue|retry_skill
FILL_DESCRIPTION=verified
UTM_18=verified
```

仅当上述成功标记全部成立时，立即继续 `utm-19`；不得等待用户确认。阻断、失败、未完成或仍在等待故障卡决定的状态不得交接。

## 阻断条件

- VM、IP、SSH 用户或 `$HOME` 不匹配。
- Edge 相关 SSH 命令非零退出、输出明确错误或未等待满 5 秒；旧 Edge 未停止，或新 Edge/CDP/登录验证失败。
- 登录 zsh 未能解析 `node`/`npm`、版本检查失败、项目/`package.json`/`.env` 缺失，或 `CDP_ENDPOINT` 不是固定值。
- 业务 SSH 被放入后台、使用 `nohup`/`&`、另加宿主管道而丢失退出码，或未完整回传 stdout/stderr。
- `tee`、状态文件、权限、字节数、SHA-256 或完整 `cat` 验证失败；日志路径不唯一或试图覆盖/删除旧日志。
- `SSH_EXIT=255` 后本轮进程/状态无法唯一确认，或有人尝试自动重跑。
- 故障卡发送/等待失败、返回值不是新的精确 `stop`/`manual_continue`/`retry_skill`、一次决定触发多次业务执行，或最终成功区块缺少任一固定原文。

发生阻断时立即暂停新的业务副作用，先按对应 `utm-18-*` stage 完成本技能状态分类、自动修复和独立复验；只有恢复穷尽或不可逆结果仍不明确时才发送最后故障卡并等待，同时保留本轮日志和非敏感证据。不泄露受保护数据，不盲目启动第二次业务执行。
