---
name: utm-20
description: Use after utm-19 when the same UTM macOS guest and matching host Notion page must continue from the completed App Store Connect screenshot upload into Business registration data capture.
---

# UTM-20：进入 Business 并登记商务信息

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
  --stage 'utm-20:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-20' \
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
| Business/银行页面误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图；提交 Add 前可用 `Escape`/`Back`/`Cancel` 回到当前银行阶段锚点，重新定位并记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立分类后仍失败才发卡 |
| 字段/下拉粘贴错误 | 只清目标字段，实时 Notion 重读，剪贴板哨兵后重贴；错选下拉恢复唯一期望值并逐项回读 | 三轮安全重贴且每轮独立回读后仍不符才 `exhausted` |
| 银行信息为空 | 初始飞书登记允许省略，前序技能不得提前阻断；只在本技能到达银行资料页后按首次、5 秒、10 秒三轮实时重读当前 Notion 页 | 三轮后外部权威数据确实缺失才 `--unrepairable` 发卡 |
| Add/2FA 结果不明 | `Add` 只一次；按现有现场分类器只读查 Certification/2FA/Processing，不刷新或重加 | 仍 ambiguous 才发卡 |

## 前置条件

- 已有 `UTM_19=verified`；首次进入直接继承其应用、截图数量 `N`、Media Manager 标签页和上传完成状态。若本技能中断后复跑，同一标签页可以已经导航到 Business/银行流程；按步骤 1 识别并保留，不强制返回 Media Manager，不重新统计缩略图或重跑 SSH 计数。
- 继续使用同一台 `started` VM、同一 guest Microsoft Edge 进程和当前标签页；不得启动、重启、切换浏览器进程或新开标签页。
- `.env` 中 Notion API 连接必须可用，`NOTION_ROOT_PAGE_ID` 指向当前宿主机页面，且其下存在唯一 `<应用名>-<vm_name>` 子页面。
- 继承当前 run 的原 `chat_id`；所有异常只允许发到这个会话，严禁发到日报专用群。
- 每次操作后等待至少 3 秒并读取最新截图；不得复用旧坐标或旧页面状态。

## 异常自动恢复和最后故障卡

下文“进入统一自动恢复流程”一律表示：先暂停后续副作用，保留同一 VM、guest Edge、标签页和已验证标记，然后执行本技能矩阵的自动诊断、自动修复和自动复验；不得一发现异常就发卡。页面、API、剪贴板和 SSH 类故障都完成三轮：每轮从最新截图或权威源重新确认当前 App/URL/阶段，能安全修复时用 `Escape`、`Back`、`Cancel`、连接/焦点修复回到最近验证锚点后只重做当前最小动作；不能安全重复副作用时，该轮只做独立只读复核。成功即记录恢复动作并继续正常主线；只有三轮恢复/复核穷尽才进入最后故障卡。

只有恢复预算穷尽，或三次实时 Notion 读取证明银行字段仍为空、CAPTCHA/账号锁定、权限冲突等外部状态确实无法由智能体修复时，才允许调用文件开头带完整恢复证据的 `notify-fault`，随后 `wait-decision`。卡片仍只接受 `stop`、`manual_continue`、`retry_skill`：继续决定必须返回同一精确阶段并再次先自动诊断；重复故障是新的事件，也必须重新穷尽恢复，不能因为以前发过卡而直接再发。故障卡不是条款、`Add`、2FA、短信验证或正常步骤的确认节点。

## 操作步骤

### 进入 Business 并读取身份卡片

1. 读取一次最新 guest Edge 截图并只读识别入口，不要求复跑时返回 Media Manager：
   - 若仍是继承的应用、Media Manager、`6.9" Display` 和同一 `N of 10 Screenshots` 页面：记录 `UTM_20_ENTRY=fresh`，不重新统计缩略图，进入步骤 2。
   - 若已是同一应用的 Business 顶部且身份卡片可见：记录 `UTM_20_ENTRY=resume_business`，直接进入步骤 5。
   - 若已是同一应用的 Business 银行流程，且当前 run 保留了步骤 5/7 已验证的 Business 字节数、SHA-256 和 `BUSINESS_CARD=verified`：记录 `UTM_20_ENTRY=resume_bank`，保持页面不动，使用该非敏感来源元数据进入步骤 6；不得为了重读卡片退出、刷新或重置银行流程。
   - 页面、应用、会话无法精确匹配，或银行流程中缺少已验证 Business 来源元数据：进入统一自动恢复流程，不继续点击。
2. 仅在 `UTM_20_ENTRY=fresh` 时，在当前 UTM 控制台中用 `sky.scroll(..., direction: "down")` 分次把网页移向顶部。每次滚动后等待至少 3 秒并重新截图，以网页滚动条移到顶部且 App Store Connect 全局导航出现为准；不得按方向名称猜测页面位置。
3. 从最新截图重新定位唯一明确的 `Business`。若第一次坐标点击只让 UTM 取得焦点、页面 URL 未变化，等待至少 3 秒并重新截图；只有 `Business` 本身处于悬停状态且底部状态栏明确显示目标为 `appstoreconnect.apple.com/business` 时，才再点击一次完成有效导航。
4. 等待至少 3 秒并重新读取页面。只有地址进入 `/business/atb/...`，且页面标题 `Business`、`Agreements` 标签或协议主体内容至少两项相互印证，并且没有登录、安全验证或错误提示，才算完成。
5. 只读取 `Business`/`Agreements` 顶部区域与下方 `Agreements` 表格之间唯一身份卡片的可见文本，按以下顺序保留原文：姓名、地址各行、数字编号、`Countries or Regions` 数量。排除银行提示、蓝色 `View`、`Agreements` 表格及其后内容；卡片缺失、重复或字段为空时进入统一自动恢复流程。核对后记录 `BUSINESS_CARD=verified` 及非敏感的字节数/SHA-256，供本技能中断恢复使用，不记录卡片原文。

### 保存商务信息到 Notion

6. 在宿主机执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，再通过 API 唯一解析 `<应用名>-<vm_name>`、`商务` 标题及其紧随的代码块。禁止启动或操作 Chrome Notion、插件、Playwright、CUA、坐标或浏览器剪贴板写入。鉴权、父页、匹配页、标题或代码块不唯一时进入统一自动恢复流程。
7. `UTM_20_ENTRY=fresh|resume_business` 时，将卡片文本按可见分组整理为姓名、地址块、编号/覆盖地区块，组间保留一个空行；不得添加字段名、`View` 或其他页面文字。只把该文本写入宿主原生剪贴板，使用字节数和 SHA-256 核对，不得展示内容。`UTM_20_ENTRY=resume_bank` 时不得重建或输出卡片原文，只复用当前 run 已验证的期望字节数/SHA-256，并记录 `HOST_CLIPBOARD=not_required_resume`。
8. 先用 `read-section --out '<mode-600 before 临时文件>'` 读取现有 `商务` 内容，以步骤 7 当前文本或本次 run 继承的已验证期望字节数/SHA-256 比较。before 文件必须是本轮随机路径、非符号链接普通文件、权限 `600`，并记录字节数/SHA-256；在“不写入”分支完成第二次独立回读，或“写入”分支完成成功回读/失败回滚之前不得删除，记录 `NOTION_BUSINESS_BEFORE=retained_until_verified`。只走一个分支：
   - 代码块仅含空白且步骤 7 持有当前卡片文本：记录 `NOTION_BUSINESS_EXISTING=blank`，进入步骤 9。若 `UTM_20_ENTRY=resume_bank` 时读到空白，则现场与已验证步骤矛盾，进入统一自动恢复流程，不得离开银行页重建内容。
   - 内容与当前 Business 身份卡片完全一致：重新执行 `verify-parent`，把第二次 `read-section` 写入另一个 mode-600 文件；两次内容和期望三方字节/hash 都相同后记录 `NOTION_BUSINESS_EXISTING=verified_equal`、`HOST_CLIPBOARD=verified` 和 `NOTION_BUSINESS_SAVED=verified`，不重复写入。随后安全删除两个临时文件并确认不存在。
   - 非空且字节数或 SHA-256 不一致：不得覆盖或拼接；记录 `FEISHU_FAULT_STAGE=utm-20-business-conflict`，进入统一自动恢复流程。
9. 仅当步骤 8 确认原代码块为空白时，从标准输入把卡片写入唯一 `商务` 代码块：

   ```bash
   pbpaste | python3 scripts/notion_api.py write-section \
     --title '<应用名>-<vm_name>' --heading '商务' --stdin
   ```

   不使用 `--replace-existing`。API 必须按 Notion 2,000 字符限制分片、PATCH 后立即重新读取，并报告与来源相同的字节数和 SHA-256。
   写入后重新执行 `verify-parent`，再用 `read-section` 将 `商务` 读入新的 mode-600 after 文件，比较其字节数/SHA-256 与步骤 7 完全一致；只有这样才标记 `NOTION_BUSINESS_SAVED=verified`。若写入返回失败或 after 不一致，保留 before，重新 `verify-parent` 后以 `write-section --replace-existing --file '<before 文件>'` 自动还原，再进行第三次独立回读并要求与 before 字节/hash 完全一致，记录 `NOTION_BUSINESS_ROLLBACK=verified` 后才进入统一恢复流程；回滚未验证不得继续或删除 before。成功写入或已验证回滚后，清空 Business 剪贴板和 shell 变量、确认 `pbpaste` 为空，再安全删除临时文件。

### 新增银行账户

10. **银行现场恢复检查**：返回同一 UTM guest Edge 的原 Business/银行标签页，不启动、重启 guest Edge 或新开标签页。等待至少 3 秒并用最新截图只读分类实时现场，只走一个分支：
    - 已出现银行更新处理中提示，或匹配应用账户唯一显示 `United States`、`USD`、`Processing`：记录 `BANK_RESUME_STATE=processing`、`BANK_FLOW=verified_by_processing`，直接进入步骤 30 完成检查；最终 `Processing` 是权威完成证据，绝不为了补中间标记再次执行任何银行动作。
    - 原 Business 页存在唯一 `Add Bank Account`，且没有匹配账户和未完成弹窗：记录 `BANK_RESUME_STATE=fresh`，进入步骤 11。
    - 明确停留在 `Add New Bank Account`、`Account Holder Details`、银行资料页、`Certification` 或当前 2FA 页面：记录对应 `BANK_RESUME_STATE`，从该页面对应的第一个未完成步骤继续。已填写、选择或勾选的字段只有在与本轮实时 Business/Notion 来源完全一致时才标记已验证并跳过；空字段才执行原动作；任何非空不一致状态进入统一自动恢复流程。
    - 页面、应用、URL、弹窗或银行账户状态无法唯一分类：记录 `FEISHU_FAULT_STAGE=utm-20-bank-state-ambiguous`，进入统一自动恢复流程。

    恢复路径不得刷新、返回重置或重新打开已完成弹窗；不得重复点击 `Add`，不得重复新增银行账户。
11. 仅当步骤 10 分类为 `BANK_RESUME_STATE=fresh` 时，从最新截图重新定位顶部提示内的 `Add Bank Account` 并点击。若第一次动作只让 UTM 取得焦点且页面未变化，等待至少 3 秒并重读；只有目标仍唯一明确时才执行一次有效点击。该链接只会滚动到 `Bank Accounts` 区域，不算进入新增流程。
12. 等待至少 3 秒并重新截图，确认 `Bank Accounts` 标题和区域中央唯一蓝色 `Add Bank Account` 按钮可见；只点击该按钮。确认 `Add New Bank Account` 弹窗出现，且包含 `Bank Country or Region`、`Cancel` 和禁用的 `Next`。
13. 打开 `Bank Country or Region` 下拉框。输入 `United States` 只用于原生下拉列表定位；重新截图确认 `United States` 本身蓝色高亮后按一次 `Return`。确认字段显示 `United States` 且 `Next` 变为可用。
14. 只点击一次 `Next`。等待至少 3 秒并确认 `Account Holder Details` 页面出现，`Country or Region` 已固定显示 `United States`，其他文本字段仍为空。
15. 先勾选 `Same as Legal Entity`。等待至少 3 秒并重新截图，确认复选框已选中、法人地址字段由页面自动带入且 `Account Holder Name` 仍为空；`Account Holder Details` 内的 `Country or Region` 可能随法人地址自动改为法人所在国家或地区，不得把它误改回前一步选择的银行国家。
16. `Account Holder Name` 必须使用步骤 5 已从 Business 身份卡片确认的姓名原文。将且仅将该姓名写入宿主原生剪贴板并用 `pbpaste` 逐字节核对；重新确认姓名输入框为空且获得焦点后，通过 guest 右键菜单中明确可见的原生 `Paste` 粘贴一次。等待至少 3 秒并回读，确认输入框与身份卡片姓名逐字节一致。
17. 打开唯一的 `Account Holder Type` 下拉框，只选择 `Individual`。重新截图确认复选框仍为已选中、姓名与身份卡片一致、字段显示 `Individual`、自动带入的法人地址仍存在且 `Next` 已可用；不得手动修改地址、州或邮编。
18. 只点击一次 `Next`。等待至少 3 秒并重新截图，确认进入新的 `Add New Bank Account` 页面，`Bank Country or Region` 为 `United States`、`Bank Account Currency` 为 `USD - US Dollar`，并且 `Account Type`、`Account Name (Optional)`、`ABA Routing Number`、`Account Number` 仍为空。

### 填写银行资料并认证

19. 打开 `Account Type` 下拉框，只选择 `Checking`。等待至少 3 秒并重新截图，确认字段显示 `Checking`。
20. `Account Name (Optional)` 必须使用已由 API 唯一匹配的 `<应用名>-<vm_name>` 标题中的应用名部分，不含连字符和 VM 名。将且仅将应用名写入宿主原生剪贴板并用 `pbpaste` 逐字节核对；重新确认该输入框为空且获得焦点后，通过 guest 右键菜单中明确可见的原生 `Paste` 粘贴一次。等待至少 3 秒并回读，确认内容与应用名逐字节一致，`ABA Routing Number` 和 `Account Number` 仍为空。
21. 先再次执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，再分别通过 `scripts/notion_api.py read-field --copy` 从当前唯一 `<应用名>-<vm_name>` 页的 `账号信息` 实时读取 `ABA Routing Number：` 和 `Account Number：`。API 必须确认每个标签只出现一次；安全元数据必须证明值非空且格式正常。初始飞书登记允许银行信息缺省，但此处进入银行操作时两项均为必填。任一值为空时不得立刻发卡：立即清空并验证宿主剪贴板，保持 Apple 银行页不动，在 5 秒和 10 秒后各重新执行一次 `verify-parent` 与两次 `read-field --copy`，共取得三轮实时结果；任一轮两项都唯一、非空且格式正常即自动继续。只有三轮均证明同一权威字段为空，才记录 `AUTO_RECOVERY_ATTEMPTS=3`、`AUTO_RECOVERY_ACTIONS=verify-parent+read-both-fields+clipboard-clear`、`AUTO_RECOVERY_RESULT=unrepairable` 和 `FEISHU_FAULT_STAGE=utm-20-bank-info-missing`，然后向原 `chat_id` 发送最后三按钮故障卡，明确提示“请把缺失的银行信息补充到当前匹配 Notion 页的 `账号信息`”，并执行 `wait-decision --timeout-seconds 3600`。不得填写 Apple 页面或从 Feishu、runtime、旧运行、对话或记忆回退。

    收到 `manual_continue` 或 `retry_skill` 后，必须保留同一 run、VM、guest Edge、当前银行页和 `<应用名>-<vm_name>`，重新从三轮自动读取开始，不得把卡片回复本身视为银行信息已补充的证据。三轮内两项均唯一、非空且格式正常才继续步骤 22；仍为空属于新的外部缺失事件，也必须重新保存三轮恢复证据后才能发送新卡。银行号码不得写入临时文件、命令参数、日志、卡片或回复。
22. 先处理 `ABA Routing Number`：重新执行 `verify-parent` 和精确标签的 `read-field --copy` 后，用字节数/SHA-256 核对而不输出完整值；重新确认 guest 空字段和焦点，通过右键菜单明确选择原生 `Paste` 一次。等待至少 3 秒并回读字段一致，同时确认页面出现唯一非空 `Bank Address`；随后立即执行 `pbcopy </dev/null`、确认 `pbpaste` 为空并清除路由号 shell 变量。任一核对失败进入统一自动恢复流程。
23. 再处理 `Account Number`：重新执行 `verify-parent` 和精确标签的 `read-field --copy`，以同样方式核对、聚焦并右键原生粘贴一次。等待至少 3 秒并逐位回读两项号码与 API 来源一致，同时确认 `United States`、`USD - US Dollar`、`Checking` 和应用名均未变化且 `Next` 已启用；随后立即执行 `pbcopy </dev/null`、确认 `pbpaste` 为空并清除账号变量，记录 `SENSITIVE_CLIPBOARD=cleared`。
24. 只有上述全部核对通过才点击一次 `Next`。等待至少 3 秒并重新截图，确认进入 `Certification` 页面，条款正文唯一、`I have read and agree to the terms and conditions above.` 复选框未选中且 `Add` 为禁用状态。
25. 步骤 19 至 24 全部核对通过后，本技能自动勾选条款并只点击一次 `Add`，无需用户确认或授权。勾选前必须已经核对银行资料、来源回读、`Certification` 页面、唯一条款正文、未选中的复选框和禁用的 `Add`；勾选后等待至少 3 秒并重新截图，只有复选框已选中且 `Add` 已启用时才准备提交。

    在首次可能点击 `Add` 之前，生成稳定 `BANK_ADD_ATTEMPT_ID`，在 `${PROJECT_ROOT}/runtime/utm-20-attempts/<current-run-id>/bank-add-<id>.json` 以 mode 600 原子落盘：保存 run/VM/App 数字 ID、当前 Business URL、银行国家/币种/类型、各敏感字段的 SHA-256（不保存值）、Certification 截图哈希、`state=prepared` 和时间。独立回读 ledger 完全一致后才把 state 原子更新为 `clicking` 并点击一次 `Add`；点击动作返回后只把状态更新为 `clicked_result_unknown`，最终 Processing 验证后更新为 `verified_processing`。若步骤 10 恢复到同一 Certification，必须先查该 ledger：不存在且页面资料完整时才创建；已有 `clicking/clicked_result_unknown` 时禁止再次点击，只进入步骤 26/30 只读分类；已有 `verified_processing` 时直接核对最终状态。任何路径都不允许第二个 `BANK_ADD_ATTEMPT_ID`。

### 短信验证和完成确认

26. 等待至少 3 秒并重新读取结果。若没有出现 `Two-Factor Authentication Required`，直接进入步骤 30；若出现则等待其加载完成。2FA 出现后自动继续短信验证，不停止等待用户、不猜选号码，也不取消弹窗。
27. 从本步骤起完整调用 `OP-APPLE-PHONE-OTP`。分别用 `read-field --copy` 从同一页 `账号信息` 实时读取 `电话：` 和 `电话短信接收平台：`；把电话尾号与所有可见掩码选项比较，只有恰好一个选项匹配时才自动点击它。等待至少 3 秒并确认页面出现六个空验证码框且显示同一尾号。
28. 再次执行 `verify-parent`，用 `read-field --copy` 读取实时 `电话短信接收平台：`，从已验证剪贴板赋给 `SMS_URL` 后立刻清空剪贴板，只在宿主终端执行以下请求；不得打印链接、为取码新开/切换/复用短信平台浏览器页面，也不得在 guest Terminal 请求：

   ```zsh
   body=$(curl -fsSL --max-time 15 "$SMS_URL") || exit 1
   code="$(BODY="$body" python3 - <<'PY'
   import os, re
   codes = re.findall(r"Apple Account Code is: ([0-9]{6})", os.environ["BODY"])
   if len(codes) != 1:
       raise SystemExit(f"OTP_MATCH_COUNT={len(codes)}")
   print(codes[0], end="")
   PY
   )" || exit 1
   [[ "$code" =~ ^[0-9]{6}$ ]] || exit 1
   printf '%s' "$code" | pbcopy
   test "$(pbpaste | wc -c | tr -d ' ')" -eq 6
   test "$(printf '%s' "$code" | shasum -a 256 | awk '{print $1}')" = \
        "$(pbpaste | shasum -a 256 | awk '{print $1}')"
   printf 'OTP_CLIPBOARD=verified\n'
   ```

29. 只有响应恰好得到一个属于当前 Apple 提示的新六位验证码时才继续；零个或多个匹配、输入框不是六个空框或验证码被拒绝时执行 `OP-APPLE-PHONE-OTP` 的三轮恢复/独立复核。重新截图确认 guest Edge 仍是六个空框后，按 `OP-NATIVE-PASTE` 只粘贴到第一个框；禁止逐字键入或快捷键兜底。输入后等待至少 3 秒并确认六格已填且页面自动推进。Apple 消费或拒绝验证码后立即执行 `pbcopy </dev/null`、确认 `pbpaste` 为空并 `unset code body SMS_URL`；记录 `OTP=verified_and_cleared`。错误码不得复用。
30. 持续只读等待银行账户添加完成。只有页面返回当前 App Store Connect `Business`，且出现银行更新正在处理的提示，或 `Bank Accounts` 中唯一匹配账户同时显示 `United States`、`USD` 和 `Processing`，才标记完成；只看到 Add 点击反馈、2FA 消失或返回 Business 不算成功。若本轮从 fresh 页面完成 Add，记录 `BANK_SUCCESS_STATE=fresh`；从明确的中间银行页恢复并完成，记录 `BANK_SUCCESS_STATE=recovered`；步骤 10 一开始就由最终 Processing 证明完成，记录 `BANK_SUCCESS_STATE=processing_resume`。有 `BANK_ADD_ATTEMPT_ID` 时把同一 ledger 原子更新为 `verified_processing`。等待后结果失败或不明确时进入统一自动恢复流程；不得刷新、重复点击 `Add` 或再次添加账户。

## 完成标准

```text
UTM_19=verified
UTM_20_ENTRY=fresh|resume_business|resume_bank
CURRENT_EDGE_SESSION=preserved
PAGE_TOP=verified
BUSINESS_CLICKED=verified
APP_STORE_CONNECT_BUSINESS=open
BUSINESS_CARD=verified
NOTION_PAGE=matched
NOTION_BUSINESS_CODE_BLOCK=api_unique
NOTION_BUSINESS_EXISTING=blank|verified_equal
NOTION_BUSINESS_BEFORE=retained_until_verified
HOST_CLIPBOARD=verified|not_required_resume
NOTION_BUSINESS_SAVED=verified
BANK_RESUME_STATE=fresh|add_bank|holder_details|bank_details|certification|two_factor|processing
BANK_SUCCESS_STATE=fresh|recovered|processing_resume
BANK_ADD_ATTEMPT_ID=<stable-id>|not_needed_processing_resume
SENSITIVE_CLIPBOARD=cleared
BANK_ACCOUNT=Processing
FEISHU_FAULT_CARD=not_needed|sent
FEISHU_FAULT_DECISION=not_needed|manual_continue|retry_skill
UTM_20=verified
```

`BANK_SUCCESS_STATE=fresh|recovered` 还必须有本轮适用的 `ADD_BANK_ACCOUNT=opened`、`BANK_COUNTRY=United_States`、`SAME_AS_LEGAL_ENTITY=checked`、`ACCOUNT_HOLDER_NAME=business_card_name`、`ACCOUNT_HOLDER_TYPE=Individual`、`BANK_DETAILS_PAGE=open`、`ACCOUNT_TYPE=Checking`、`ACCOUNT_NAME=app_name`、`ABA_ROUTING_NUMBER=verified`、`ACCOUNT_NUMBER=verified`、`CERTIFICATION_PAGE=open`、`CERTIFICATION_AGREED=verified`、`BANK_ADD=clicked_once`、`TWO_FACTOR=not_required|verified` 和 `OTP=not_required|verified_and_cleared`。`processing_resume` 只以当前最终 Processing 证据替代这些中间标记，绝不伪造或重做。全部适用标记有当前证据后立即继续 `utm-21`；`waiting`、`stop`、失败或结果不明都不是成功，不得交接。

## 异常故障条件

- VM、guest Edge、当前标签页、应用名或继承的 `N of 10 Screenshots` 页面状态与 `UTM_19=verified` 不匹配。
- 无法确认已到页面顶部，或 `Business` 不可见、不唯一、被遮挡或目标有歧义。
- 点击后进入非 Business 页面，或出现登录失效、安全验证、错误页面。
- 身份卡片不唯一、内容不完整，或读取范围跨入银行提示、`View`、协议表格。
- Notion API 鉴权失败、父页/匹配页不一致，`商务` 标题/代码块不唯一，现有内容与当前 Business 卡片不一致，或写后回读哈希不一致；完全一致的现有内容不是故障。
- Business 文本来源、剪贴板或 API 哈希核对失败。
- 返回后不是原 Business 标签页，顶部银行提示或 `Add Bank Account` 缺失、重复、被遮挡，或点击后未明确进入新增银行账户流程。
- `Bank Accounts` 区域按钮、任一 `Add New Bank Account` 页面、`United States`、`Same as Legal Entity`、`Account Holder Name`、`Individual`、`USD - US Dollar`、`Checking` 或 `Account Name (Optional)` 不唯一/不可见，复选框或字段回读不匹配，法人地址未自动带入，姓名与 Business 身份卡片不一致，应用名无法唯一确定或粘贴后不一致。
- 匹配 Notion 页面或其 `账号信息` 代码块无法唯一确认，`ABA Routing Number：` 或 `Account Number：` 标签缺失/重复、对应值为空/无法唯一映射/格式异常；空值使用专用 `utm-20-bank-info-missing` 最后故障卡并在卡片决定后重新读取同一 Notion 页。剪贴板核对失败、路由号码未返回唯一银行地址、号码回读不一致、敏感剪贴板无法清空，或页面要求其他未登记银行信息同样先进入统一自动恢复流程，恢复穷尽才发卡。
- 点击后未进入唯一 `Certification` 页面，条款正文不唯一，条款复选框预先选中，或勾选前 `Add` 异常可用。
- 双重认证页面为空、报错、实时 Notion 电话/短信链接缺失、号码尾号不能唯一匹配、宿主终端请求失败、响应没有唯一当前 Apple 六位码，或验证码被拒绝。
- 验证后未返回 Business、没有银行更新处理中提示，且匹配银行账户行未显示 `United States`、`USD`、`Processing`。

本节任一异常都必须先进入上文“异常自动恢复和最后故障卡”，不得只在对话中报告后结束，也不得跳过诊断直接发卡。`manual_continue` 与 `retry_skill` 都回到同一故障点并重新执行自动诊断；只有本轮恢复再次穷尽，才视为新的故障事件并只发送一张新卡。不得通过刷新、返回、重开页面或点击其他导航项猜测性修复；只允许矩阵列出的确定性回滚，正常主线不得发送确认卡。
