---
name: utm-25
description: Use when utm-24 has verified App Store submission and expedited review, while the same guest Edge and run remain available for final API credential registration and success notification.
---

# UTM-25：登记 API 信息并发送提审成功通知

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
  --stage 'utm-25:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-25' \
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
| API 页/Copy 误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图；`Escape`/重新定位唯一控件，复制前清空剪贴板并写入随机哨兵，复制后要求哨兵不得残留，记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立来源核对后仍失败才发卡 |
| Active 表格未稳定 | 5/10/20 秒只读等待并重新计数；只接受一行 | 稳定后 0/多行为 `unrepairable` |
| P8/SSH/SCP | 同一 VM 恢复三轮，完整 Downloads 重新扫描并按真实路径去重；只核对同一关联候选 | 零/多候选或 key 关联不明为 `unrepairable` |
| Notion replace 回读失败 | 使用 before 文件自动还原，独立 `read-toggle-code` 复验并记录 `NOTION_ROLLBACK=verified`；不得留下部分新值 | 还原也失败才发卡；成功卡门禁仍关闭 |

## 定位

`utm-25` 紧接 `utm-24` 执行。它继承当前精确 run 的 `UTM_24=verified`、`APP_REVIEW_STATUS=Waiting for Review|15 Items Submitted`、`EXPEDITED_REVIEW_RESULT=verified`、`API_CREDENTIALS_REGISTRATION=pending`、`REVIEW_SUCCESS_NOTIFICATION=not_sent|sent`，以及同一 VM、VM IP/SSH 身份和仍登录的同一 guest Edge。

本技能先在同一 guest Edge 新标签取得 App Store Connect API 的唯一 Issuer ID 和唯一 Active Key ID，再从同一 guest 用户的 Downloads 安全取得对应 P8，通过 Notion API 写入匹配页面 `更新信息` 下的 `退款回调及p8`。只有独立 API 回读按字节与 SHA-256 验证通过后，才允许沿用项目已有命令发送或核验一次绿色 `提审提交成功` 卡。

不得启动、重启或切换 Edge 进程；不得关闭、重载或改写 `utm-24` 保留的 App Store/加急成功标签页；不得点击 `Submit for Review`；不得点击加急页 `Send`。每次 GUI 操作后等待至少 3 秒并重新读取最新画面。

Notion 只通过项目 `scripts/notion_api.py` 读写；不得用宿主 Chrome、Notion 插件、Playwright、CUA、坐标或浏览器剪贴板读写 Notion。P8 不得经过剪贴板。Issuer ID、Key ID 和 P8 正文不得出现在终端输出、命令参数、日志、卡片、截图、测试结果或回复中。成功卡无按钮、无 callback、无需回复，不进入 3600 秒等待；所有卡片严禁发送到 `AI-Infra业务团队`。

## 操作步骤

1. 确认从 `utm-24` 到当前步骤没有任务中断或 VM/Edge 切换，且入口五项标记属于同一 run。只做一次继承 VM/IP/SSH 用户的轻量存活/身份检查。对 guest Edge 分别读取 UTM 窗口/前台应用归属和精确 VM 内 Edge PID/启动参数，等待 5 秒后再做第二次独立读取；存在但被遮挡时只激活同一既有进程。两轮匹配后记录 `BROWSER_SESSION_RECHECKS=2`；两轮都不存在才按浏览器全局规则进入最后恢复，绝不启动或重启。确认 `utm-24` 保留的 App Store 成功标签页和加急成功页仍在，不在其中继续导航。

2. 使用 `mktemp -d` 创建本技能专用的宿主随机临时目录并立即回读权限 `700`；其中 Issuer ID、Key ID、P8、Notion 写入源和 API 回读文件以 `umask 077`/排他创建，权限必须为 `600`。路径与文件名不得包含任何凭据值。禁止 `set -x`，禁止把文件内容交给 `echo`、标准输出、日志或命令参数。正常成功、未发生 Notion 写入的 stop/超时、或已验证回滚后删除；若 Notion 回滚失败，必须保留 before/源/after/rollback 文件供恢复，记录 `SECURE_TEMP_RETENTION=rollback_failure_only`，不得按无条件清理条款删除。

3. 在同一 guest Edge 进程中新建标签页。重新确认 UTM/Edge 目标窗口和地址栏，调用 `OP-BROWSER-URL-NO-SCHEME`：执行 `printf '%s' 'appstoreconnect.apple.com/access/integrations/api' | python3 scripts/shared_operations.py browser-url --allow-bare`。只有 `BROWSER_URL_CLIPBOARD=verified` 且原生菜单 `Paste and Go` 已蓝色高亮时确认一次；粘贴后立即清空剪贴板。等待至少 3 秒后重新读取画面并验证目标页面。

4. 页面必须同时显示 `Users and Access`、已选中的 `Integrations`、`App Store Connect API`、已选中的 `Team Keys`、唯一 `Issuer ID` 区域和 `Active` 表格。若未登录，只允许在这个同一 Edge 标签内恢复同一 Apple Account：
   1. 每个字段前在宿主执行 `verify-parent`；邮箱只读 `账号信息/邮箱：`，密码先读 `修改后的密码：`，只有 API 元数据证明为空时才读 `初始密码：`；
   2. 每次用随机剪贴板哨兵证明旧值已被覆盖，右键当前明确字段并选择可见 `Paste`，等待至少 3 秒回读字段状态，随后清空剪贴板和变量；
   3. 电话/短信验证完整调用 `OP-APPLE-PHONE-OTP`：只用实时 `电话：` 的唯一掩码尾号，只从实时 `电话短信接收平台：` 请求唯一当前六位 Apple code，并按 `OP-NATIVE-PASTE` 输入；随后立即清空剪贴板和 `code/body/SMS_URL`。固定 Mac 密码提示调用 `OP-FIXED-PASSWORD-1234`；
   4. CAPTCHA、锁号、账号不匹配、零/多 OTP 或未知挑战按 5/10/20 秒完成三轮独立只读复核并回到同一页面锚点，三轮仍不能分类才发最后故障卡。

   登录后重新执行本步骤全部六个页面锚点核对。账号、页面或权限无法唯一确认时按本技能矩阵重读同一标签、会话和权限三轮，仍冲突才作为 `unrepairable` 进入最后故障卡。不得选择 `Individual Keys`，不得从 `Revoked` 取值。

5. 对 `Active` 做只读计数。只接受恰好一条数据行并记录 `ACTIVE_API_KEY_COUNT=1`；0 条或多于 1 条时重新读取同一 Team Keys 页面、加载/权限、表格和筛选三轮。三轮仍为 0/多条才记录只读分类证据，以 `utm-25:active-key-count` 进入最后故障卡。不得按 `NAME`、最近使用时间或第一条记录猜测，也不得生成、撤销或下载新 Key。

6. 使用页面 `Issuer ID` 旁的 `Copy` 取得唯一值；再从唯一 Active 行的 `KEY ID` 单元格取得 Key ID。两次复制分别完整执行下列闭环，不得复用上一次剪贴板：
   1. 生成不含任何凭据的随机哨兵，把宿主剪贴板清空后写入该哨兵，立即回读其字节数/SHA-256，证明写入成功；记录哨兵哈希但不记录正文。
   2. 用最新截图重新确认精确 Copy 控件或唯一 KEY ID 单元格、父区域和 Active 行；执行一次复制，等待至少 3 秒。
   3. 回读剪贴板；必须非空、与随机哨兵不同且格式符合当前字段。哨兵不得残留；若仍是哨兵，说明点击未生效，按矩阵完整做三轮安全 Copy 修复，每轮都重新确认来源、重置哨兵并独立回读，绝不能接受剪贴板中的旧合法值。
   4. 立即把值写入对应的宿主 `600` 临时文件，移除末尾换行；从页面再复制一次并只比较两次的字节数/SHA-256，完全一致才证明来源。随后清空剪贴板并验证为空。

   Issuer ID 必须唯一符合 UUID 格式，Key ID 必须唯一符合 Apple Key ID 的大写字母/数字格式；只记录字节数和 SHA-256，不得显示值。两项都通过后记录 `APP_STORE_CONNECT_API_PAGE=verified`。

7. 通过继承的 BatchMode SSH 在同一 `<vm_name>` 用户下查找 P8，不打开 guest Terminal：

   1. 所有 P8 候选必须先与当前 Key ID 建立精确关联；不得因候选只有一个就直接采用。首选精确文件名 `AuthKey_<当前 Key ID>.p8`，大小写与 Key ID 逐字符一致。
   2. 检查 `/Users/<vm_name>/Downloads/apple-store-bm/config/AuthKey_<当前 Key ID>.p8` 并加入关联候选。若同目录存在 `prod.yml`，只允许复用 `utm-22` 的现有私密读取方式取得其中的 key ID 与 P8 路径；仅当配置 key ID 逐字符等于页面 Key ID、路径位于同一 `<vm_name>` 用户的 Downloads 内且精确指向普通文件时，才把该路径加入关联候选。不得打印完整 `prod.yml`、P8 路径中的敏感文件名或任何字段值。
   3. 无论标准目录是否已经命中，都必须始终扫描完整 Downloads 允许范围：只在 `/Users/<vm_name>/Downloads` 内递归查找精确名为 `AuthKey_<当前 Key ID>.p8` 的普通文件，并把所有结果加入同一候选集合。不得用泛化 `*.p8` 的唯一数量推断归属，不得搜索其他用户、系统目录或其他 VM。
   4. 对标准路径、`prod.yml` 路径和递归查找结果先限制在 Downloads 内，再按规范化真实路径去重；每个结果都必须是普通、非空文件。只有去重后总数恰好为 1 才可继续。零个或多个时重新扫描完整 Downloads、重读 `prod.yml`、解析真实路径/inode/Key ID 关联三轮。三轮仍非唯一才以 `utm-25:p8-file` 进入最后故障卡；不得选择第一项、“最新”文件或仅凭 PEM 可解析就猜测归属。
   5. 不输出正文地验证首行精确为 `-----BEGIN PRIVATE KEY-----`、末个非空行精确为 `-----END PRIVATE KEY-----`，并用系统私钥解析器执行只读有效性检查。全部通过才记录 guest 文件路径的非敏感哈希证据。

   扫描必须是两阶段固定实现，不能靠人眼选文件：
   - 第一阶段在单个 BatchMode SSH 中从 stdin 读取 Key ID（以 NUL 结尾），不得把它放入 argv。远端固定 Python 以 `Path("/Users/<vm_name>/Downloads").resolve(strict=True)` 为根，递归 `rglob("AuthKey_" + key_id + ".p8")`；每项先 `lstat` 拒绝 symlink，再 `resolve(strict=True)` 并要求仍在 Downloads 根下、为普通非空文件。随后用 `utm-22` 同一私密 YAML 解析器只读取得配置 key ID/path；仅 exact key ID 且 resolved path 满足相同根目录/普通文件条件才合并。集合按 `(realpath, st_dev, st_ino)` 去重，完整扫描结束后必须恰好一个。
   - 第一阶段标准输出只允许 `P8_CANDIDATE_COUNT=<n>`、选定真实路径的 SHA-256（不是路径）和内容 bytes/SHA-256；`P8_CANDIDATE_COUNT=1` 才进入第二阶段。
   - 第二阶段重新执行完整扫描，并把唯一 P8 的原始字节作为 SSH stdout 直接重定向到预先排他创建的宿主 mode-600 文件；远端不得混入 marker，SSH stderr 单独捕获。退出码、候选路径 hash、bytes 和内容 SHA-256 必须与第一阶段一致。shell 随即 `unset key_id`，不得把正文送入终端或日志。

8. 使用上述 stdout-to-file 安全传输把精确 P8 放入第 2 步的宿主临时目录，设置权限 `600`，再以新的只读 SSH 连接重新完整扫描并核对 guest/host 字节数和 SHA-256 一致；任何传输结果不明都只核对同一关联集合，不能改选候选或打印正文。通过后记录 `P8_CANDIDATE_COUNT=1` 和 `P8_FILE=verified`。

9. 在宿主内把两个 ID 临时文件和 P8 临时文件拼成权限 `600` 的写入源，值不得出现在 shell 命令参数或输出中。必须用文件路径参数调用固定 Python（不能用含值的 shell 插值）执行：拒绝 symlink/非普通文件；读取并去除 ID 文件唯一末尾换行；验证 Issuer UUID、Key ID 格式及 P8 首尾/解析；以 `os.open(temp, O_CREAT|O_EXCL|O_WRONLY, 0o600)` 创建同目录随机临时文件，按以下固定字节顺序写入、`fsync`、`os.replace` 并同步目录：

   ```text
   issuer id: <Issuer ID>
   key id:<Key ID>
   p8文件内容：

   -----BEGIN PRIVATE KEY-----
   <完整 P8 正文>
   -----END PRIVATE KEY-----
   ```

   `issuer id: ` 后有一个半角空格；`key id:` 后直接接 Key ID；`p8文件内容：` 使用中文全角冒号，其后空一行再写完整 PEM。用第二个独立 Python 重新解析生成文件，要求只有一组这三个标签、一组 PEM 首尾，ID 与两个临时文件逐字节一致、P8 与宿主 P8 bytes/SHA-256 完全一致、mode 为 `600`；只输出总字节数、行数和 SHA-256。全部通过后记录 `P8_PAYLOAD=verified`。

10. 在宿主项目根目录先验证当前 Notion 父页面，再读取目标 toggle 的当前代码块到排他创建、非符号链接、权限 `600` 的 before 文件：

    ```bash
    python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
    python3 scripts/notion_api.py read-toggle-code \
      --title '<应用名>-<vm_name>' \
      --heading '更新信息' \
      --toggle '退款回调及p8' \
      --out '<secure-before-file>'
    ```

    父页面、目标子页面、`更新信息` heading、`退款回调及p8` toggle 和其唯一代码块必须全部唯一。命令输出只能包含 action、bytes、lines、SHA-256 和输出路径，不能包含正文。

11. before 与写入源逐字节相同时不得只凭第一次读取成功：再次执行 `verify-parent`，把第二次 `read-toggle-code` 写入另一个 mode-600 equal-readback 文件；before、equal-readback 与源文件三方完整字节/行数/SHA-256 都相同后才记录 `NOTION_EQUAL_READBACK=verified` 并跳过写入。

    不同时只替换该唯一 toggle 代码块，不新建页面、heading、toggle 或代码块，不修改其他 Notion 内容。**下面每一次** `write-toggle-code` 或 `read-toggle-code` 前都必须紧邻执行新的 `verify-parent --title '<宿主机名称>'`；前一次验证不能复用：

    ```bash
    python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
    python3 scripts/notion_api.py write-toggle-code \
      --title '<应用名>-<vm_name>' \
      --heading '更新信息' \
      --toggle '退款回调及p8' \
      --file '<secure-registration-file>' \
      --replace-existing
    python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
    python3 scripts/notion_api.py read-toggle-code \
      --title '<应用名>-<vm_name>' \
      --heading '更新信息' \
      --toggle '退款回调及p8' \
      --out '<secure-after-file>'
    ```

    使用新的宿主只读检查，要求 after 与写入源字节数、行数、SHA-256 和完整内容都一致；不能用写入命令成功或浏览器画面代替回读。write 分支通过，或 equal 分支已经取得 `NOTION_EQUAL_READBACK=verified` 后，才记录 `NOTION_REFUND_CALLBACK_P8=verified` 和 `API_CREDENTIALS_REGISTRATION=verified`。在这两个标记出现前严禁调用成功通知命令。

    若写入命令、网络返回或 after 回读任一失败/不一致，不得留下可能部分成功的新内容，也不得直接发卡。立即用步骤 10 的 before 文件自动还原同一唯一 toggle：

    ```bash
    python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
    python3 scripts/notion_api.py write-toggle-code \
      --title '<应用名>-<vm_name>' \
      --heading '更新信息' \
      --toggle '退款回调及p8' \
      --file '<secure-before-file>' \
      --replace-existing
    python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
    python3 scripts/notion_api.py read-toggle-code \
      --title '<应用名>-<vm_name>' \
      --heading '更新信息' \
      --toggle '退款回调及p8' \
      --out '<secure-rollback-file>'
    ```

    独立比较 rollback 与 before 的完整字节、行数和 SHA-256；完全一致才记录 `NOTION_ROLLBACK=verified`，保持成功卡门禁关闭，再把原写入失败作为自动恢复已穷尽的故障处理。若自动还原也失败，保留安全临时目录和 before，不再写第二次新内容，按最后故障卡报告 `AUTO_RECOVERY_ACTIONS=write,readback,rollback,reverify`。

12. 清空宿主剪贴板；保留全部 `600` 临时文件直到以下之一成立：
    - equal 分支第二次独立回读成功；
    - write 分支 after 与源完整相同；
    - write 失败后 rollback 与 before 完整相同。

    前两种成功或已验证回滚后才删除本技能临时目录并验证不存在，记录 `SECURE_TEMP_RETENTION=rollback_failure_only`。若 rollback 未验证，保留目录并只记录其非敏感路径/hash 清单，禁止删除或发送成功卡。不得删除 guest 原始 P8 或 `apple-store-bm` 内容。

13. 只读解析 `runtime/feishu-runs.json` 中 `id` 等于当前精确 `run_id` 的唯一记录；不存在或不唯一时重载同一路径并按精确 ID 独立复验三轮，仍不唯一才进入最后故障卡，不得选择其他 run。核对 runtime 的 `chat_id` 非空、逐字符等于原 `chat_id` 且不是日报专用群。任何卡片或 runtime 副作用前重新核对本机 `SUBMISSION_HOST_MACHINE` 与 run 登记宿主机精确相等；缺失或不匹配时只记录审计并返回未执行提示。

14. 把顶层 `review_submission_approval` 作为唯一送审授权源，要求 `kind=review_submit`、`status=approved`、`decision=submit_review`，并要求匹配且非空的 `decision_id`、App Version、build、14 个 IAP、五图/15 项完整 evidence、`answered_at` 和 `operator_id`。automatic 来源还必须有 `source=automatic_self_check` 和按 01→05 顺序的五个唯一 screenshot hashes，并与当前 run 文件独立重算一致；同时要求顶层 `review_submit_attempt.status=verified`、decision/version/build/15 项与授权完全相同。当前 `pending_decision` 可为 UTM-24/25 fault，不能据此否定、覆盖或推断授权。

    只有顶层字段完全不存在的旧 run 才允许迁移，且必须按固定流程：同一 runtime 文件独立读取两次，确认 pending 是唯一 answered `review_submit`、决定为 `submit_review`、decision ID/版本/build/14 IAP/evidence 完整且两次相同；重算五图哈希并核对 UTM-24 当前提交成功证据；原子写入顶层快照后由第三个进程重读全部字段，且 `is_approved_review_submission` 返回真。全部通过记录 `LEGACY_APPROVAL_MIGRATION=independently_verified`；非 legacy 正常分支记录 `LEGACY_APPROVAL_MIGRATION=not_needed`。显式 rejected/malformed 快照、`do_not_submit`、不匹配 `decision_id`、非 answered 状态或缺少已验证 submit attempt 都不得迁移或发送。

15. 只读分类 runtime 的 `review_success`：

    - `status=sent`：要求 `app_review_status` 与继承状态一致、`completed_at` 存在且 `message_id` 非空；满足时跳过重复发送。
    - 不存在：入口必须是 `REVIEW_SUCCESS_NOTIFICATION=not_sent`；命令会在网络发送前持久化 `status=sending`、目标状态、开始时间和稳定非空 `message_uuid`。
    - `status=sending`：只有目标状态一致、开始时间存在且 `message_uuid` 非空才可恢复同一逻辑通知尝试。
    - 其他或字段不完整：重新读取同一 run 三轮并核对稳定 UUID/状态转移；仍不完整才进入最后故障卡，不覆盖状态、不创建第二个尝试。

16. 只有 `NOTION_REFUND_CALLBACK_P8=verified`、`API_CREDENTIALS_REGISTRATION=verified`、完整当前 approval、`review_submit_attempt.status=verified` 和 `LEGACY_APPROVAL_MIGRATION=not_needed|independently_verified` 已存在，且 runtime 不是完整 `sent` 时，才运行唯一成功通知命令：

    ```bash
    python3 services/feishu_bot.py notify-review-success \
      --run-id '<run_id>' \
      --app-review-status '<Waiting for Review|15 Items Submitted>'
    ```

    CLI 始终使用 runtime 原 `chat_id`。要求退出码 `0`，且标准输出去掉末尾换行后逐字符等于同一 `run_id`。命令结果未知时重新运行只能恢复同一 `sending` 尝试；底层必须复用已持久化的 `message_uuid`，不得生成新 UUID，不得创建新通知。

17. 使用新的宿主只读读取重新解析 runtime，要求同一 run 的 `review_success.status=sent`、`app_review_status` 匹配、`completed_at` 存在、`message_id` 非空。仍为完整 `sending` 时只能按第 16 步恢复同一 UUID；不得报告成功或创建新尝试。核验通过后记录：

    ```text
    REVIEW_SUCCESS_NOTIFICATION=sent
    UTM_25=verified
    ```

## 阻断条件

- 缺少或冲突的入口标记、任务/VM/Edge 现场切换、run 不唯一、原 `chat_id` 不匹配、宿主机授权不匹配或目标为日报专用群。
- API 页面身份或 Team Keys 状态不唯一；Active 为 0 条或多于 1 条；Issuer ID/Key ID 复制、格式或安全落盘失败；读取了 Revoked 或按 `NAME` 猜测。
- P8 缺失、无法通过精确 `AuthKey_<当前 Key ID>.p8` 或匹配 `prod.yml` 与当前 Key ID 建立唯一关联、不是普通非空文件、PEM/私钥校验失败、SSH/SCP/哈希不一致，或内容进入剪贴板/输出/日志。
- Notion 父页面、目标页、heading、toggle 或代码块不唯一；写入源格式不匹配；API 写入或独立回读与源文件不完全一致；在 `NOTION_REFUND_CALLBACK_P8=verified` 前尝试发成功卡。
- `review_submission_approval` 不是完整 approved/current 快照；显式 rejected/malformed 快照不得回退到 fault `pending_decision`。已有 sent 状态不匹配或没有 `message_id`；通知命令失败或恢复后没有完整 sent 记录。

所有可发送故障卡的异常都执行本技能的 `notify-fault` / `wait-decision` 合同。`manual_continue` 只重查相同故障点；`retry_skill` 继承同一 run/VM/Edge 和安全临时现场并跳过 `APP_STORE_CONNECT_API_PAGE=verified`、`P8_FILE=verified`、`NOTION_REFUND_CALLBACK_P8=verified` 等已验证步骤。任何故障决定都不能重做 App Store 提交、加急 `Send`，也不能绕过 Notion 登记门禁。若 runtime 已为完整 `sending`，两种继续决定只能恢复原 `message_uuid`。

## 完成标准

```text
UTM_24=verified
APP_REVIEW_STATUS=Waiting for Review|15 Items Submitted
EXPEDITED_REVIEW_RESULT=verified
BROWSER_SESSION_RECHECKS=2
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

## 流程终点

`utm-25` 是全部 31 个技能的最终技能。只有 Notion 中 `退款回调及p8` 已由 API 独立回读验证，且 runtime 中存在匹配状态、完成时间和非空 `message_id` 的成功通知记录时，才能记录 `UTM_25=verified`；完成后不再调用或交接其他技能。
