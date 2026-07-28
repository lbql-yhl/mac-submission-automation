# UTM-18：启动 Edge CDP 并通过 SSH 填写应用描述

## SSH 全自动约束

直接继承 `utm-17` 已验证的同一 VM、IP、用户和宿主公钥；所有 SSH 调用使用 `BatchMode=yes`。连接失效时自动锁定同一精确 VM 刷新 IP、修复 Remote Login 并恢复宿主公钥，不向用户索取密码、SSH Key、IP，也不把 SSH 修复交给故障卡。`manual_continue` 与 `retry_skill` 只用于业务状态已查清后的恢复，绝不代表由用户修 SSH。

## 操作步骤

1. 接着 `utm-17`，确认同一台 VM 处于 `started`，并通过带 `-o BatchMode=yes -o ConnectTimeout=5` 的只读 SSH 核对 `id -un=<vm_name>`、`$HOME=/Users/<vm_name>`。
2. 先只读 `pgrep`。有旧进程才执行 `pkill -x "Microsoft Edge"`；退出 0 表示已发信号，退出 1 仅在新 `pgrep` 已证明进程数为 0 时视为幂等成功，其他退出码失败。等待至少 5 秒，用两条新 SSH 再确认旧进程为 0。
3. 用新的独立 BatchMode SSH 命令以 `--remote-debugging-port=9222`、`--user-data-dir=/tmp/edge-debug-profile`、`--no-first-run` 后台启动 guest Edge；等待至少 5 秒，再确认唯一进程参数、日志、监听 PID，并请求 `http://127.0.0.1:9222/json/version` 验证唯一 WebSocket URL，记录 `EDGE_CDP_HTTP=verified`。
4. 在同一 guest Edge 新建 tab，调用 `OP-BROWSER-URL-NO-SCHEME` 并执行 `printf '%s' 'developer.apple.com/account/' | python3 scripts/shared_operations.py browser-url --allow-bare`；只在 `BROWSER_URL_CLIPBOARD=verified` 且 `Paste and Go` 蓝色高亮后确认一次，随后清空剪贴板。如需登录，完整复用 `utm-10` 的 Notion API-only 路径：先执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，再用 `read-field --copy` 读取当前字段；不得用宿主浏览器或插件读取 Notion。随后确认 `Account` 页面和账号状态。
5. 不打开 guest Terminal。Apple Developer 登录确认后，从宿主 Terminal 前台 SSH 到同一 guest，通过 `/bin/zsh -lic` 加载登录/交互环境，再经 `source /dev/stdin` 执行固定运行器。运行器必须：

   - 重新核对 SSH 用户、`$HOME` 和 `Downloads/Fire_One_en1.2`；
   - 用 `command -v node`、`command -v npm`、`node --version`、`npm --version` 确认 Node/npm 环境；
   - 只检查 `.env` 中 `CDP_ENDPOINT=` 恰好出现一次且值严格为 `CDP_ENDPOINT=http://127.0.0.1:9222`，不得 source 或显示 `.env`；
   - 如果后置 `apple-store-bm/config/prod.yml` 校验失败，先只读确认 YAML 中 `key_id`、`private_key_path`、`bundle_id` 的两个前导空格与 `grep -Fqx` 的匹配文本一致；不得为缩进问题重换 Team Key、重下 `.p8` 或重跑业务命令；
   - 执行 `set -o pipefail`；
   - 业务 SSH 前由宿主生成 `UTM_18_ATTEMPT_ID`，在当前 run 的 mode-600 ledger 中预先保存固定日志/status 绝对路径；独立 SSH 以 noclobber 创建两文件并回读 `ATTEMPT_ID=<id>`、`RUN_STATE=prepared`、权限 600，记录 `UTM_18_LOG_PATH=precommitted`；
   - 前台执行 `npm run fill:description 2>&1 | /usr/bin/tee "$log_path"`；
   - 立即保存 `statuses=("${pipestatus[@]}")`，把 npm 与 `tee` 退出码分别写为 `REMOTE_NPM_EXIT=`、`REMOTE_TEE_EXIT=`；状态从 `RUN_STATE=running` 推进到 `RUN_STATE=finished`。

6. SSH 必须保持前台，不得给业务命令加 `nohup`、`&` 或宿主管道。npm 的 stdout/stderr 由 `tee` 完整实时回传并同步写入预提交日志；状态以原子替换从 `prepared → running → finished`。每个合法新 attempt 都必须先有新 ledger/log/status，旧文件不覆盖或删除。heredoc 结束后立即捕获 `SSH_EXIT`。
7. 用 host ledger 中已持久化的精确路径和 ID（不依赖业务 SSH 临时打印）新建只读 SSH，核对 status ID、mode 600、字节数、SHA-256、完整 status/log；不得猜“最新日志”。
8. 只有 `SSH_EXIT=0`、`RUN_STATE=finished`、`REMOTE_NPM_EXIT=0`、`REMOTE_TEE_EXIT=0`、日志验证通过，且完整日志同时含 `增强版内购创建完成！` 和 `📊 统计信息: 共处理 14 个产品`、无明确错误时，才完成。
9. `SSH_EXIT=255` 表示传输中断，不能代表 npm 结果。先恢复同一精确 VM 的连接，再只读检查本轮日志、`.status` 和对应进程：仍运行则继续等待同一 attempt；已完成则按第 7、8 步核验；状态不明、进程消失或没有本轮路径时记录 `FILL_DESCRIPTION=blocked_ambiguous`，继续只读对账，不猜测最新日志或自动重跑。
10. 环境预检、npm、`tee`、状态或日志失败时，用 ledger/log/status/进程/App Store Connect 四方分类。仍运行继续同一 attempt；只有四方证明 `ZERO_BUSINESS_SIDE_EFFECTS=verified` 且错误可确定修复时，才允许一个新 attempt。出现任意部分业务结果都禁止新 attempt 或以“幂等”推定续跑。
11. 日志/status 缺失、部分结果无法唯一对账、没有安全修复或修复后再次失败时，记录实际 `AUTO_RECOVERY_ATTEMPTS`、`AUTO_RECOVERY_ACTIONS` 和 `AUTO_RECOVERY_RESULT=exhausted|unrepairable`，此时才调用唯一 `notify-fault` 发最后故障卡并等待 3600 秒；严禁发到日报群。
12. `manual_continue` 或 `retry_skill` 都必须重新验证同一 VM、SSH、Edge/CDP、Apple 登录和上一 attempt 状态；只有第 10 步再次证明零副作用才允许新 attempt；否则继续只读，不得因卡片决定盲目重跑。

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

仅当上述成功标记全部成立时，立即继续 `utm-19`；阻断或等待故障卡决定的状态不得交接。

## 风险点

- guest Edge 是唯一允许重启的浏览器；不得影响宿主 Google Chrome。
- 裸 SSH shell 可能找不到 npm；必须使用 `/bin/zsh -lic` 并在执行业务命令前核对 Node/npm 路径和版本。
- 不显示或 source `.env`，不运行 `env`/`printenv`，不把账号、密码、链接、验证码或 token 写入日志、故障卡或总结。
- 业务 SSH 不得后台化；`tee`、`pipestatus`、状态文件和新连接日志复核缺一不可。
- 非幂等业务命令失败后先自动分类、修复并复验；本轮执行状态仍不明、完整日志不可读或成功结构不完整时只读恢复同一 attempt。恢复穷尽后才发最后故障卡；任何决定都不能跳过歧义检查，也不要求用户修 SSH 或提供凭据。
