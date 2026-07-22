# UTM-25：登记 API 信息并发送提审成功通知

对应技能：`utm-25`。紧接 `utm-24`，继续使用同一 run、VM/IP/SSH 身份和同一 guest Edge。先把唯一 Active Key 的 Issuer ID、Key ID 与已下载 P8 登记到 Notion `退款回调及p8`，API 独立回读通过后才核验或发送一次绿色 `提审提交成功` 卡。

## Checklist

- [ ] 精确继承 `UTM_24=verified`、`APP_REVIEW_STATUS=Waiting for Review|15 Items Submitted`、`EXPEDITED_REVIEW_RESULT=verified`、`API_CREDENTIALS_REGISTRATION=pending` 和 `REVIEW_SUCCESS_NOTIFICATION=not_sent|sent`；未选择最新 run、VM 或浏览器。
- [ ] 保留 UTM-24 两个成功标签页；先对 UTM 窗口/前台应用归属和精确 VM 内 Edge PID/启动参数做两轮独立读取，并记录 `BROWSER_SESSION_RECHECKS=2`。在同一 guest Edge 新标签调用 `OP-BROWSER-URL-NO-SCHEME`，执行 `printf '%s' 'appstoreconnect.apple.com/access/integrations/api' | python3 scripts/shared_operations.py browser-url --allow-bare`，只在验证通过后用蓝色高亮 `Paste and Go` 打开。没有启动、重启或切换 Edge 进程，每次 GUI 操作后均等待至少 3 秒并重新读取画面。
- [ ] 页面唯一显示 `Users and Access`、`Integrations`、`App Store Connect API`、`Team Keys`、`Issuer ID` 和 `Active`；没有选择 `Individual Keys` 或从 `Revoked` 读取。
- [ ] `Active` 恰好一条并记录 `ACTIVE_API_KEY_COUNT=1`。0 条或多于 1 条时重新读取同一 Team Keys 页面、加载/权限、表格和筛选状态三轮。三轮仍为 0/多条属于无法安全选择的外部状态，记录三轮只读分类证据后才发送最后故障卡；不得按 `NAME`、最近使用时间或第一条猜测。
- [ ] Issuer ID 和唯一 Active Key ID 分别安全落入权限 `600` 的宿主临时文件，格式唯一有效；值只用字节数与 SHA-256 验证，未出现在命令参数、终端输出、日志、卡片或回复中。
- [ ] 所有 P8 都先与当前 Key ID 精确关联，不能因为候选只有一个就直接采用。第一阶段通过独立 SSH 只读收集精确文件名、`prod.yml` 中同 Key ID 的精确指向及完整 Downloads 范围，规范化 realpath、限制仍在 `/Users/<vm_name>/Downloads`、要求非符号链接普通非空文件并去重；stdout 只允许 `P8_CANDIDATE_COUNT=<n>` 和非敏感 hash/字节数。只有 `P8_CANDIDATE_COUNT=1` 才进入第二阶段安全字节流传输；零/多候选时做三轮完整重扫并保持路径不输出。
- [ ] P8 首尾为 `-----BEGIN PRIVATE KEY-----` / `-----END PRIVATE KEY-----` 且通过只读私钥解析。用 SSH/SCP 安全复制到宿主权限 `700` 临时目录中的 `600` 文件，guest/host 字节数和 SHA-256 一致，记录 `P8_FILE=verified`。P8 不经过剪贴板、不打印正文、不删除 guest 原文件。
- [ ] 权限 `600` 的登记源用随机同目录临时文件、创建时 mode 600、`fsync` 和原子替换生成，逐字符采用以下格式，并且仅记录总字节数、行数和 SHA-256；独立解析后记录 `P8_PAYLOAD=verified`：

  ```text
  issuer id: <Issuer ID>
  key id:<Key ID>
  p8文件内容：

  <完整 P8 PEM>
  ```

- [ ] Notion 只使用 `scripts/notion_api.py`。先执行 `verify-parent`，再读取匹配页 `更新信息` 下唯一 `退款回调及p8` toggle：

  ```bash
  python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
  python3 scripts/notion_api.py read-toggle-code \
    --title '<应用名>-<vm_name>' \
    --heading '更新信息' \
    --toggle '退款回调及p8' \
    --out '<secure-before-file>'
  ```

- [ ] 每一次 Notion 读或写之前都重新执行 `verify-parent`。当前内容相同时不能只凭首次读取跳过：再次 `verify-parent` 并把第二次 `read-toggle-code` 写入新 mode-600 文件，before/第二次回读/源文件三方字节完全相同才记录 `NOTION_EQUAL_READBACK=verified`。内容不同时只替换该 toggle 的唯一代码块，不新增/移动其他内容：

  ```bash
  python3 scripts/notion_api.py write-toggle-code \
    --title '<应用名>-<vm_name>' \
    --heading '更新信息' \
    --toggle '退款回调及p8' \
    --file '<secure-registration-file>' \
    --replace-existing
  python3 scripts/notion_api.py read-toggle-code \
    --title '<应用名>-<vm_name>' \
    --heading '更新信息' \
    --toggle '退款回调及p8' \
    --out '<secure-after-file>'
  ```

- [ ] after 与源文件字节数、行数、SHA-256 和完整内容一致后，记录 `NOTION_EQUAL_READBACK=not_applicable_written`、`APP_STORE_CONNECT_API_PAGE=verified`、`NOTION_REFUND_CALLBACK_P8=verified`、`API_CREDENTIALS_REGISTRATION=verified`。若写入/回读不一致，必须用 before 自动还原并由新进程证明 `NOTION_ROLLBACK=verified`；回滚失败时保留敏感临时文件作为唯一可恢复证据，不得删除。在验证标记出现前不得调用成功通知。
- [ ] 正常成功、`stop` 或超时终止时清空剪贴板并删除宿主敏感临时目录；只有 Notion 回滚失败时保留，记录 `SECURE_TEMP_RETENTION=rollback_failure_only`。guest 原始 P8 和 `apple-store-bm` 保持不变。
- [ ] 只读解析 `runtime/feishu-runs.json`，唯一匹配当前 `run_id`，核对原 `chat_id`、非日报群和本机/运行宿主机。
- [ ] 顶层 `review_submission_approval` 是唯一授权源，要求 `kind=review_submit`、`status=approved`、`decision=submit_review` 和完整 `decision_id`、版本、构建、14 个 IAP、五图/15 项 evidence、时间与操作人；新 run 还要求 `source=automatic_self_check`、`operator_id=automation:self-check`。同时必须有绑定同一 `decision_id` 的 `review_submit_attempt.status=verified`。故障 `pending_decision` 不得覆盖快照或推断授权。旧 run 只在顶层快照完全不存在时迁移：同一 runtime 文件独立读取两次，要求唯一 answered review pending 的全部字段一致，重算五图 hash 并核对当前提交成功证据，原子写入后由第三个进程回读，才记录 `LEGACY_APPROVAL_MIGRATION=independently_verified`；正常新 run 记录 `not_needed`。
- [ ] `review_success.status=sent` 仅在状态匹配、`completed_at` 存在、`message_id` 非空时防重跳过。新尝试先持久化 `review_success.status=sending` 和稳定 `message_uuid`；命令结果未知只恢复同一 UUID，不创建新通知。
- [ ] 只有 Notion 登记已验证后才运行 `notify-review-success --run-id '<run_id>' --app-review-status '<Waiting for Review|15 Items Submitted>'`；退出 0 且标准输出为同一 run id。
- [ ] 新只读 runtime 显示完整匹配的 sent 记录后，记录 `REVIEW_SUCCESS_NOTIFICATION=sent`、`UTM_25=verified`。成功卡标题为 `提审提交成功`，无按钮、无 callback、无需回复且不进入超时等待。

## 异常边界

- 页面/Active 数量、ID 落盘、P8 查找/解析/传输、Notion 唯一定位/写入/回读或成功卡状态任一不明确，都先按本技能矩阵完成自动诊断、修复、回滚和独立复验。只有恢复穷尽或外部状态无法安全修复时，才由 `utm-25` 发送不含敏感信息的最后三按钮故障卡并固定等待 3600 秒；不得静默结束，也不得跳过恢复直接发卡。
- `manual_continue` 重新检查同一故障点；`retry_skill` 立即重跑当前技能并跳过已验证步骤。两者都不能重新点击 `Submit for Review`、加急页 `Send`，也不能绕过 `NOTION_REFUND_CALLBACK_P8=verified`。
- 当前 `review_success.status=sending` 时只恢复已持久化的同一 `message_uuid`。用户可见成功卡最多一张。
- `stop` 或等待超时在更新/发送规定卡片后终止主线，并清除宿主敏感临时文件；迟到回调无效。

## 完成标记

```text
UTM_24=verified
APP_REVIEW_STATUS=Waiting for Review|15 Items Submitted
EXPEDITED_REVIEW_RESULT=verified
APP_STORE_CONNECT_API_PAGE=verified
ACTIVE_API_KEY_COUNT=1
P8_CANDIDATE_COUNT=1
P8_FILE=verified
P8_PAYLOAD=verified
NOTION_EQUAL_READBACK=verified|not_applicable_written
NOTION_REFUND_CALLBACK_P8=verified
API_CREDENTIALS_REGISTRATION=verified
SECURE_TEMP_RETENTION=rollback_failure_only
LEGACY_APPROVAL_MIGRATION=not_needed|independently_verified
REVIEW_SUCCESS_NOTIFICATION=sent
UTM_25=verified
```

`UTM_25=verified` 是 31 项技能主线终点，不再交接其他技能。
