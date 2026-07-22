# UTM-20：登记商务信息并新增银行账户

## 前置检查

- [ ] `utm-19` 已完成，当前仍是同一 VM、同一 guest Edge 进程和同一标签页；首次进入时该页是 Media Manager，复跑时允许它已导航到同一 Business/银行流程。
- [ ] 直接继承 `UTM_19=verified` 的截图数量 `N` 和上传状态；首次进入只用一张最新截图确认同一 `N of 10 Screenshots` 文本。复跑已在银行流程时使用当前 run 的已验证证据并保留现场，不强制返回 Media Manager；两种路径都不重新统计缩略图或重跑 SSH 计数。
- [ ] `.env` 的 Notion API 连接可用，`NOTION_ROOT_PAGE_ID` 指向当前宿主机页面，且唯一匹配 `<应用名>-<vm_name>`。
- [ ] 继承当前 run 的原 `chat_id`；异常故障卡只发到该会话，不发到日报群。
- [ ] 每次 GUI 操作后等待至少 3 秒并读取最新截图，不复用旧坐标。

## 异常恢复规则

- [ ] 任一异常先保留同一 VM、guest Edge、标签页和已验证步骤，暂停新的副作用，按本技能矩阵完成只读分类、自动修复和独立复验；页面导航/误点回到最近验证锚点，字段问题从实时 Notion 来源重读，不重复新增账户或重复点击 `Add`。
- [ ] 只有恢复预算穷尽，或实时权威数据仍缺失、身份冲突、不可逆结果仍不明确等智能体确实无法修复的状态，才携带 `recovery_attempts`、`recovery_actions` 和 `recovery_result` 向原 `chat_id` 发送最后三按钮故障卡并等待 3600 秒。运行时拒绝无恢复证据的发卡请求。
- [ ] `manual_continue` 与 `retry_skill` 都先重新读取同一故障点并再次执行自动恢复，保留仍有当前证据的步骤；正常条款、唯一 `Add`、2FA 和短信验证保持全自动，不把卡片作为确认节点。

## 操作 Checklist

### 进入 Business 并读取身份卡片

- [ ] 首次进入时确认继承的 Media Manager 页面；复跑若已在同一 Business/银行流程，则保留当前页并使用当前 run 已验证的 Business 文本字节数/SHA-256，不强制返回 Media Manager，也不重置银行流程。
- [ ] 从当前 Media Manager 页面滚动到顶部，确认全局导航可见。
- [ ] 从最新截图定位唯一 `Business`；只有悬停状态栏显示 `appstoreconnect.apple.com/business` 时才点击。
- [ ] 验证 URL 进入 `/business/atb/...`，且 `Business`、`Agreements` 与协议内容至少两项相互印证。
- [ ] 只读取 Agreements 表格上方唯一身份卡片的姓名、地址各行、数字编号和 `Countries or Regions` 数量；排除银行提示、`View` 和协议表格。

### 保存商务信息到 Notion

- [ ] 运行 `scripts/notion_api.py verify-parent`，通过 API 确认匹配页、`商务` 标题及紧随代码块唯一。
- [ ] 按姓名、地址块、编号/覆盖地区块整理原文，组间保留一个空行，不添加字段名。
- [ ] 先用 `read-section` 将现有内容读入 mode-600 before 文件并比较字节数/SHA-256；记录 `NOTION_BUSINESS_BEFORE=retained_until_verified`，在 equal 第二次独立回读、写后精确回读或失败回滚验证前不得删除。空白才写；完全一致须再次 `verify-parent/read-section` 三方复核后跳过；非空不同不覆盖。
- [ ] 仅在空白分支用宿主原生剪贴板按字节数/SHA-256 核对，通过 `pbpaste | scripts/notion_api.py write-section --heading '商务' --stdin` 写入一次，不使用 `--replace-existing`。
- [ ] 写后重新 `verify-parent/read-section` 回读；不一致用 before 执行 `write-section --replace-existing` 还原并第三次独立回读，只有 `NOTION_BUSINESS_ROLLBACK=verified` 或成功写入后才删除临时文件。

### 新增银行账户

- [ ] 先做**银行现场恢复检查**：只读区分已完成 `Processing`、初始 `Add Bank Account`、`Account Holder Details`、银行资料、`Certification` 或 2FA；从第一个未完成步骤继续。已有字段仅在与实时 Business/Notion 来源完全一致时跳过；不一致先对同一页、同一来源重读并执行可逆字段修复，无法分类或不可逆结果不明时才进入最后故障卡。
- [ ] 已显示匹配账户 `United States`、`USD`、`Processing` 时直接以最终状态完成；不得为补标记重复打开流程、重复点击 `Add` 或重复新增账户。
- [ ] 返回同一 guest Edge Business 标签页；点击顶部提示中的 `Add Bank Account` 滚动到 `Bank Accounts`。
- [ ] 点击区域中央蓝色 `Add Bank Account`，选择 `United States` 并进入 `Account Holder Details`。
- [ ] 先勾选 `Same as Legal Entity`，确认法人地址自动带入且姓名仍为空。
- [ ] 将 Business 身份卡片姓名原文粘贴到 `Account Holder Name`，选择 `Individual`；不得手动修改法人地址。

### 填写银行资料并认证

- [ ] 确认银行国家为 `United States`、币种为 `USD - US Dollar`，将 `Account Type` 选为 `Checking`。
- [ ] 将匹配 Notion 标题中的应用名粘贴到 `Account Name (Optional)`，不包含 VM 名。
- [ ] 初始飞书登记允许银行信息为空。进入银行资料步骤时先重新执行 `verify-parent`，再分别用 `read-field --copy` 从唯一匹配页 `账号信息` 实时读取 `ABA Routing Number：` 和 `Account Number：`；标签必须唯一、值非空且格式正常。不得打印、落盘或从 Feishu/runtime/旧运行/对话/记忆回退。
- [ ] 任一银行值为空时清空宿主剪贴板并保持银行页不动；立即、5 秒后、10 秒后共三轮重新执行 `verify-parent` 和两次 `read-field --copy`。任一轮两项唯一、非空、格式正常即自动继续。三轮均为空才记录 `utm-20-bank-info-missing`、`AUTO_RECOVERY_ATTEMPTS=3` 和只读动作证据，作为权威数据缺失发送最后故障卡。收到 `manual_continue` 或 `retry_skill` 后仍须再次实时重读；卡片回复不是补充证据。
- [ ] 分别粘贴并逐位回读两项号码；路由号码必须返回唯一银行地址，其他字段不得变化。
- [ ] 确认进入唯一 `Certification`，银行资料、条款正文、未选中的复选框和禁用的 `Add` 全部核对通过。勾选后、首次可能点击前持久化稳定 `BANK_ADD_ATTEMPT_ID`（敏感字段只保存 hash）并独立回读；状态按 `prepared → clicking → clicked_result_unknown → verified_processing` 推进。已有 clicking/unknown 时只读分类，绝不第二次 Add。

### 短信验证和完成确认

- [ ] 2FA 出现后完整调用 `OP-APPLE-PHONE-OTP`，不停止等待用户；分别用 `read-field --copy` 重新读取实时 `电话：` 和 `电话短信接收平台：`。
- [ ] 只有一个掩码手机号尾号与实时 Notion 电话匹配时才选择。
- [ ] 只在宿主终端用 `curl -fsSL --max-time 15` 请求实时短信链接；不打开短信平台浏览器页面。
- [ ] 只接受当前响应中恰好一个 `Apple Account Code is: 六位数字`；零个或多个匹配均进入三按钮故障卡流程。
- [ ] 用唯一正则提取当前新六位码，按 `OP-NATIVE-PASTE` 只粘贴到第一个空框；禁止 `type_text` 或快捷键兜底。Apple 消费或拒绝后立即清空剪贴板和 `code/body/SMS_URL`；被拒绝码不得复用。
- [ ] 只有返回 Business 并出现银行更新处理中提示，或匹配账户显示 `United States`、`USD`、`Processing`，才算完成。

## 完成标准

```text
UTM_19=verified
SCREENSHOT_UPLOAD=verified_N_of_10
APP_STORE_CONNECT_BUSINESS=open
BUSINESS_CARD=verified
NOTION_BUSINESS_EXISTING=blank|verified_equal
NOTION_BUSINESS_SAVED=verified
BANK_RESUME_STATE=fresh|add_bank|holder_details|bank_details|certification|two_factor|processing
BANK_SUCCESS_STATE=fresh|recovered|processing_resume
BANK_ADD_ATTEMPT_ID=<stable-id>|not_needed_processing_resume
BANK_COUNTRY=United_States
SAME_AS_LEGAL_ENTITY=checked
ACCOUNT_HOLDER_TYPE=Individual
ACCOUNT_TYPE=Checking
ABA_ROUTING_NUMBER=verified
ACCOUNT_NUMBER=verified
CERTIFICATION_AGREED=verified
TWO_FACTOR=not_required|verified
TWO_FACTOR_PHONE=not_required|matched_from_live_notion
SMS_TERMINAL=not_required|verified
OTP=not_required|verified_and_cleared
BANK_ACCOUNT=Processing
UTM_20=verified
```

全部适用完成标记均有当前证据后，立即继续 `utm-21`，不设置人工确认或技能交接确认；故障卡等待状态不得交接。

## 风险点

- 不启动、重启或切换浏览器进程，不新开 guest Edge 标签页，不刷新或重复新增银行账户。
- Business 身份卡片、Notion API 页/`商务` 代码块、银行字段或掩码手机号不唯一时保留现场，先按恢复矩阵重读、回到锚点并复验；只有无法形成唯一证据时才进入最后三按钮故障卡。
- 银行号码不得写入技能、项目文件、日志或回复；验证码不得来自旧请求、旧页面或 Notion 静态内容。
- 短信取码只走实时 Notion 链接和宿主终端，禁止使用宿主 Chrome、guest Edge 或 guest Terminal 打开短信平台。
- 每一步都以最新截图、字段回读或页面结果为准；点击本身不代表成功。
