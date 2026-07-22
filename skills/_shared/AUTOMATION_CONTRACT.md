# 31 技能统一自动执行合同

本文件是项目 31 个技能共同引用的唯一恢复合同。技能自己的业务步骤仍是权威；本文件只统一“怎样确认目标、怎样执行、怎样发现误点、怎样恢复、何时才允许发飞书故障卡”。任何技能不得把“出现异常”直接等同于“发卡等待”。固定顺序是：

`自动诊断 → 自动修复 → 自动复验 → 最后才发故障卡`

## 共享重复操作记忆（31 个技能强制继承）

以下操作 ID 是整个项目唯一的重复操作方法。任一技能遇到对应场景时，必须直接调用该 ID 的完整步骤和成功判定，不得临时改成键盘盲输、快捷键盲贴、旧剪贴板复用、重新拼接 URL 或询问用户固定密码。执行记录必须写出操作 ID 和对应成功标记；没有成功标记就回到该操作的第 1 步。

### `OP-NATIVE-PASTE`：权威值原生粘贴

1. 重新确认当前 run、同一 VM/guest、应用、窗口、字段父区域和唯一目标输入框；旧截图、旧坐标和旧菜单立即作废。
2. 重新从技能规定的权威来源取值。敏感值只能经 `scripts/notion_api.py read-field --copy`、当前进程内存或项目明确固定值进入宿主原生剪贴板，不得出现在 argv、终端输出、日志、卡片或临时明文文件中。
3. 先清空剪贴板并写入本轮随机哨兵，回读哨兵的字节数和 SHA-256；再执行本轮权威 Copy，回读必须非空、与哨兵不同，并与来源的字节数/SHA-256 完全一致。不得打印正文。
4. 重新聚焦唯一目标输入框，右键打开 guest 原生菜单；等待至少 3 秒并读取新画面。只有当前菜单中可见、可用且蓝色高亮的 `Paste` 才能激活。坐标点击不可靠时，只能在已经看见同一 `Paste` 蓝色高亮后用 `Down` 加 `Return` 激活；禁止 `Command+V`、`type_text`、`set_value` 或猜菜单位置兜底。
5. 粘贴一次，等待至少 3 秒，重新读取目标字段的可见值、字节/哈希、掩码或圆点数，并确认邻近字段没有变化。菜单消失不算成功。
6. 敏感值被页面消费或拒绝后立即 `pbcopy </dev/null`，要求 `pbpaste` 为空，并清除当前 shell/进程变量。成功标记为 `OP_NATIVE_PASTE=verified`；敏感值还必须有 `SENSITIVE_CLIPBOARD=cleared`。

### `OP-BROWSER-URL-NO-SCHEME`：浏览器地址栏无协议粘贴

1. URL 只能来自当前技能明确允许的实时 API 字段或正文写死的裸地址常量；重新确认来源唯一、单行、非空，不得从历史剪贴板、聊天、记忆或另一个 run 取值。
2. API URL 必须把当前剪贴板直接送入统一执行器：

   ```bash
   pbpaste | python3 scripts/shared_operations.py browser-url
   ```

   执行器只删除最前面的一个 `https://` 或 `http://`，也就是只把第一个 `//` 后面的全部内容写回剪贴板；从 `//` 后第一个字符开始，host、path、query、token、大小写和每个字节必须原样保留。不得删除中间字符、截断、解码、重新拼接或补回协议。其他 scheme、空 host、嵌套 scheme、空白和多行输入一律拒绝。
3. 技能正文已经批准的裸地址常量使用：

   ```bash
   printf '%s' '<approved-bare-address>' | python3 scripts/shared_operations.py browser-url --allow-bare
   ```

   `--allow-bare` 只允许正文已有的常量，不能把未知来源伪装成裸地址。
4. 执行器输出只能包含 `BROWSER_URL_CLIPBOARD=verified`、字节数和 SHA-256。随后用 `pbpaste` 的字节数/SHA-256复核，明确证明剪贴板不含 `https://`、`http://`、前后空白或其他内容；不得输出链接正文。
5. 重新确认仍是同一 guest Edge 进程和目标新标签页地址栏。右键后等待至少 3 秒；只有原生 `Paste and Go` 可见、可用且蓝色高亮时才激活一次。禁止逐字键入、快捷键盲贴、启动新浏览器或向值前面加协议。
6. 等待至少 3 秒，从地址栏结构、目标 host/path 和页面锚点验证导航正确；立即清空剪贴板和 URL 变量。成功必须同时记录 `BROWSER_URL_CLIPBOARD=verified`、`BROWSER_PASTE_AND_GO=verified` 和 `SENSITIVE_CLIPBOARD=cleared`（即使链接本身非敏感也执行清空）。

### `OP-APPLE-PHONE-OTP`：电话尾号与 Apple 六位验证码

1. 保持当前 Apple 提示页不动，重新执行 `verify-parent`，再用 `scripts/notion_api.py read-field --copy` 分别实时读取 `电话：` 和 `电话短信接收平台：`；不得复用旧值。
2. 只比较实时电话的尾号与页面所有掩码选项；恰好一个匹配时点击一次。零个或多个匹配不得猜选，进入本操作的三轮恢复。
3. 点击取码前再次实时读取短信平台字段，把值留在当前进程内存后立即清空剪贴板。只能从宿主 Terminal 请求当前响应；不得新开短信网站、使用宿主 Chrome、guest Edge 或 guest Terminal 取码。
4. 响应必须属于当前请求，并且正则 `Apple Account Code is: ([0-9]{6})` 恰好得到一个新六位码。零个、多个、旧码、过期码或与当前提示无法归属的码都不得输入。
5. 按 `OP-NATIVE-PASTE` 把且仅把六位码粘贴到第一个空验证码框；不允许 `type_text` 兜底。等待至少 3 秒，确认六格均已填且页面自动推进或明确拒绝。
6. Apple 消费或拒绝验证码后立即清空剪贴板并清除 `code`、`body`、`SMS_URL` 等变量；错误码不得复用。成功记录 `PHONE_OPTION=verified_unique`、`OTP_SOURCE=verified_fresh_unique`、`OTP_PASTE=verified_six_boxes`、`SENSITIVE_CLIPBOARD=cleared`。
7. 瞬态失败执行三轮：每轮都重新核对当前提示、重新读取电话/短信平台、重新请求并只接受当前唯一新码。CAPTCHA、账号锁定、账号不匹配、未知挑战或持续零/多码不能安全修复时，也必须完成三轮独立只读复核并记录后，才允许调用最后故障卡。

### `OP-FIXED-PASSWORD-1234`：项目固定 VM 密码

固定密码只有 `1234`，无用户、run 或账号覆盖分支，也不得向用户询问。先按当前提示类型选择唯一子流程：

- **VM 登录界面**：确认精确 VM、用户和密码框后，分别发送 `1`、`2`、`3`、`4` 四个按键；回读四个圆点，再激活唯一登录按钮。不得通过剪贴板粘贴。
- **已识别的 macOS/Keychain 授权弹窗或 `Enter Mac Password`**：先确认弹窗所属 guest、应用、当前 attempt 和账号，再把固定值作为本轮项目常量按 `OP-NATIVE-PASTE` 粘贴；回读四个圆点，只点击唯一蓝色 `Allow`、`OK`、`Continue` 或 `Trust`。未知/归属不明弹窗禁止输入。
- **宿主 PTY 中的远端 `sudo`、`ssh-copy-id`、`User password` 提示**：只有提示文本、目标 VM/IP/用户和当前命令全部匹配时才交互输入一次；密码不得进入 argv、管道、剪贴板、脚本、输出或日志。随后用新的 BatchMode/身份/权限只读命令验证结果，提示消失本身不算成功。

成功记录 `FIXED_VM_PASSWORD_CONTEXT=login|gui_auth|pty_prompt` 和 `FIXED_VM_PASSWORD_RESULT=verified`。失败时只恢复同一提示和同一目标；三轮仍失败才允许最后故障卡，绝不改用 Apple Account 密码或让用户代输。

### `OP-USER-CONFIRMATION`：必须由用户决定的流程步骤

只有某个技能正文明确写出“该业务决定必须由用户确认”时才能调用；正常技能交接、可自动验证的字段、自动恢复和当前 `utm-24` 自检提审都不得借此暂停。先完成目标、范围、风险、当前证据和确认后唯一动作的只读准备，再执行：

```bash
python3 services/feishu_bot.py notify-confirmation \
  --run-id '<current-run-id>' \
  --chat-id '<original-chat-id>' \
  --stage '<skill:confirmation-stage>' \
  --current-skill '<current-skill>' \
  --confirmation-question '<one-specific-question>' \
  --confirmation-action '<one-action-after-approval>' \
  --evidence '<non-sensitive-current-evidence>'
python3 services/feishu_bot.py wait-decision \
  --run-id '<current-run-id>' --decision-kind confirmation --timeout-seconds 3600
```

卡片只发到该 run 原非日报 `chat_id`，并在每次发送/回调前重验本机宿主机所有权。`stage`、`current_skill`、单一问题、确认后唯一动作和非敏感当前证据全部必填；任一缺失则运行时拒绝发卡。相同 waiting 确认只在这五项逐字符一致时复用同一 `decision_id` 和稳定 `message_uuid`；证据已变更时拒绝静默复用旧卡。非空 `message_id` 才开始计时，不提醒、不重复发送。

用户点击 `确认并继续` 就是对这一个问题的回复，但“确认成功”必须同时满足：回调 run 属于本机宿主且仍是原非日报群聊；回调携带的 `run_id`/`decision_id` 与当前 waiting 记录完全一致；`operator_id` 非空；运行时已持久化 `kind=confirmation`、`status=answered`、`decision=confirm_continue`、`answered_at`和同一操作人；`wait-decision` 标准输出为 `confirm_continue` 且退出码为 `0`；执行器再次读取同一现场后，目标和卡中证据仍一致。全部满足才记录 `USER_CONFIRMATION=verified`并执行卡中那一个动作；Toast、卡片变绿、按钮消失或聊天文字都不能单独算成功。

点击 `取消并停止` 必须持久化 `decision=cancel_operation`，`wait-decision` 输出 `cancel_operation` 且退出码为 `2`，记录 `USER_CONFIRMATION=cancelled`并禁止执行待确认动作。回调后仍必须重新读取同一现场；卡片不能替代不可逆动作两阶段门禁。超时只发一张无按钮超时卡并永久停止该 run。

## 技能正文的详细步骤验收

每个 `skills/<skill>/SKILL.md` 必须自带可直接执行的业务正文，不得只写“打开页面”“完成设置”“验证成功”等摘要。一个技能只有同时满足以下六项才算写清楚：

1. **输入来源**：写明继承的 run/VM/会话、权威文件或 API、唯一性与格式条件，以及不得使用的回退来源。
2. **精确动作**：按实际执行顺序编号，给出完整命令、路径、页面锚点、控件原文、选项值、当次允许的副作用和明确停点；不得把关键操作留给临场猜测。
3. **动作后复验**：每个副作用后写明等待/轮询、重新读取方式、预期值、不应变化的值和不能当作成功的表象。
4. **分支与恢复**：写明未开始、已完成、部分完成、冲突、结果不明时各走哪个分支，以及有界恢复次数、最近验证锚点和不可重复的动作。
5. **成功标记**：必须列出所有当前证据和唯一 `<SKILL>=verified` 标记；点击过、命令启动、弹窗消失、旧截图或无错误文字均不算成功。
6. **连续交接**：写明下一技能、必须原样继承的上下文和禁止交接的状态；最终技能则明确唯一流程终点。

共享合同只提供通用执行/恢复规则，不能代替任一技能的业务操作正文。技能正文与本合同冲突时，严格的安全边界优先，但不得因此跳过该技能的精确动作和成功判定。

## 1. 不可变运行上下文

一次 run 创建后，`run_id`、原 `chat_id`、登记宿主机、`vm_name`、应用名、App ID、Bundle ID、VM 包、VM/IP/SSH 身份、guest 浏览器进程、工作目录和当前非幂等 attempt ID 均不可被“最新”“最近”“第一个”候选替换。

- 正常交接只做一次轻量存活/身份检查。
- 连接失效只恢复同一精确对象；恢复后再次核对身份。
- 页面、文件或命令结果不明确时，先只读分类；不得用再次执行副作用来探测状态。
- 动态路径从项目配置解析：`PROJECT_ROOT`、`SUBMISSION_VM_IMAGES_DIR`、`SUBMISSION_SHARED_DIR`、`SUBMISSION_SSH_PRIVATE_KEY` 和 `PROJECT_SKILLS_DIR`。技能不得写死宿主用户目录或插件版本目录。

## 2. 每个步骤的五段式执行

每个业务步骤都必须按以下顺序执行，缺一项就不算完成：

1. **前置状态**：读取最新页面、文件或命令状态；确认 run、目标对象和已完成标记。
2. **唯一目标**：目标文字、角色、父区域、URL/路径、当前值和可用状态必须同时匹配；零个或多个候选都不得点击或写入。
3. **最小动作**：只执行当前步骤的一次最小动作，不夹带后续操作。
4. **结果观察**：等待目标系统稳定；GUI 至少等待 3 秒，长任务按技能规定的有界轮询窗口读取。
5. **完成证据**：重新读取全新状态，验证预期结果和不变量，并记录可复查的非敏感证据；旧截图、点击反馈、退出按钮消失或命令已启动都不是完成证据。

## 3. 每次 GUI 动作后的固定闭环

GUI 动作包括窗口切换、点击、双击、右键、菜单移动、按键、滚动、粘贴、下拉选择、文件选择和提交。每次都执行：

1. 读取最新截图/AX 状态，确认宿主 UTM 窗口、精确 guest、应用、标签页、URL、目标父区域和目标控件。
2. 目标必须唯一且处于预期启用/高亮状态；记录动作前页面锚点和关键字段。
3. 只执行一次动作。
4. 等待至少 3 秒；页面仍加载时只读等待，不连点。
5. 重新读取最新截图/AX 状态，验证预期变化，并同时核对应用、URL、父区域和不应变化的字段。
6. 只有验证成功才记录当前步骤 `verified` 并继续。

窗口尺寸、焦点、菜单或页面布局变化，滚动、弹窗出现/消失、标签切换和页面导航都会使旧坐标、旧高亮、旧菜单序号和旧截图立即失效。下一动作必须从新状态重新定位。

## 4. 误点检测

满足任一项即判定为误点或动作未生效，不得假装成功：

- URL、标题、父区域、按钮文字、选中值或弹窗身份与预期不一致；
- 菜单关闭但目标状态没有变化；
- 只取得窗口焦点、悬停或选中行，实际页面/字段没有变化；
- 邻近控件变化、非目标字段变化、目标字段仍为旧值；
- 粘贴后字节数/哈希/掩码/圆点数不匹配；
- 文件选择器目录、文件数、扩展名、`N items` 或目标 App ID 不匹配；
- 结果页面仍在加载、网络错误、空白、重复记录或出现无法归属的系统弹窗。

## 5. 可逆误点恢复

可逆动作不得立即发卡。按最小恢复点自动处理，最多执行技能矩阵规定的次数：

- **菜单/下拉误点**：按 `Escape` 关闭当前菜单，等待至少 3 秒，确认回到动作前锚点；重新打开并只选择唯一正确且高亮的项目。
- **错误页面/标签**：使用明确的 `Back`、`Cancel`、关闭本轮新标签或回到已验证标签；不得关闭前序保留的成功页。回到锚点后重新核对 URL、应用和 run。
- **字段误填**：只清空目标字段；重新从权威来源读取，先清空剪贴板并设置随机哨兵，再复制/粘贴；回读完全一致后清空敏感剪贴板。不得改动邻近字段。
- **复选框/单选项误选**：仅在页面明确显示当前值且切换可逆时恢复到期望值；每次切换后重新读取。归属或结果不明时不得猜。
- **文件选择器误入目录/误选文件**：点击 `Cancel`，确认未上传、未覆盖，再从已验证入口重新打开；按目录、父路径、数量、扩展名和哈希重新选择。
- **窗口焦点或尺寸变化**：重新聚焦精确窗口、等待至少 3 秒、取得新截图，作废全部旧坐标后重做当前最小动作。
- **网络/页面瞬态失败**：只读等待 5、10、20 秒三轮；在动作可证明未执行时才允许刷新或重新导航一次。动作是否执行不明时进入不可逆分类，不刷新探测。

每次恢复必须重新执行该步骤的完整五段式闭环。恢复成功后记录 `GUI_RECOVERY=verified` 或对应命令恢复标记，并继续，不发卡。

## 6. 命令、API、SSH 与文件自动恢复

- 先保存退出码、attempt ID、目标路径、字节数、哈希、权限和非敏感输出。
- SSH 失败只对同一 VM 自动刷新精确 MAC 对应 IP、检查 Remote Login/端口、恢复同一宿主公钥并重新验证用户/home。
- GET/只读 API 的瞬态错误按 2、5、10 秒重试三次；写入前必须有 before 快照，写后必须独立回读。
- 可幂等复制/生成在目标可证明由当前 run 所有且内容不匹配时，重新执行一次并再次比较；已有完全相同内容直接视为已完成。
- 写入回读失败时，若动作可逆，使用 before 快照自动还原并独立回读；还原成功后才允许发卡报告原写入失败。
- 非幂等命令必须创建稳定 attempt ID、日志和状态文件。传输中断后只检查同一 attempt 的进程、日志和远端状态，不得创建第二个 attempt。

## 7. 不可逆动作的两阶段门禁

提交、上传、删除、覆盖、创建账号、创建银行账户、`Add`、Archive、App Review、加急 `Send` 等不可逆或难回滚动作使用两阶段门禁：

1. **准备阶段**：验证精确 run/对象、所有输入、目标按钮、范围、已有状态、幂等键/attempt ID 和禁止重复标记；保存删除前证据或写入 before 快照。
2. **执行阶段**：只点击/调用一次，立即持久化 attempt 标记，然后只读观察结果。

结果只允许三类：

- `succeeded`：有权威成功标记，继续；
- `not_executed`：有直接证据证明动作没有发生，才可按技能上限重试；
- `ambiguous`：无法证明成功或未执行，只读恢复和查询；不得再次点击、上传、删除、提交或 `Send`。

所谓“回滚”只适用于真正可逆的导航、字段和有 before 快照的写入。Apple/银行/上传等外部不可逆动作不得伪造回滚；其安全恢复是查询同一 attempt 的最终状态并避免重复。

## 8. 有界恢复预算

每个精确故障点在最后故障卡前固定完成至少三轮有编号的“诊断 → 安全修复 → 独立复验”。技能另有更严格的副作用上限时，三轮仍不能省略：不能安全重复写入或点击的轮次改为只读状态恢复/复核，绝不为了凑次数重复不可逆动作。

- GUI 可逆误点：最多三轮，每轮都作废旧坐标、回到最近验证锚点并只重做当前最小动作；
- 只读页面/网络：5、10、20 秒三轮；
- SSH/API 瞬态错误：最多三轮，每轮独立复验身份/响应；
- 文件/API 可逆写：原动作最多 1 次、自动还原最多 1 次，其余轮次只读比较 before/after/权威源；
- 不可逆动作：最多执行 1 次，之后三轮只查询同一 attempt 的状态，绝不再次执行；
- CAPTCHA、账号锁定、权限/所有权冲突、权威数据缺失等外部不可修复状态：不伪造修复，改做三轮独立只读复核，确认分类稳定且仍不可安全处理。

重试计数只属于当前精确故障点；不得通过重启技能把计数清零。恢复过程中发现新的、独立的故障点才使用新的计数。少于三轮时禁止调用 `notify-fault`；运行时会直接拒绝发送。

## 9. 飞书卡片是最后出口

故障卡功能必须保留，但只有以下两类情况可发送：

1. 已按本合同和本技能矩阵完成至少三轮自动诊断、安全修复、独立复验，恢复预算已经穷尽；
2. 三轮独立只读复核均证明属于智能体不能安全修复的外部状态，例如 CAPTCHA、账号锁定、未知安全挑战、权威数据缺失、权限缺失、所有权冲突、多候选且无唯一证据、不可逆动作最终状态仍不明确。

发卡前必须记录并传入：

```text
AUTO_RECOVERY_ATTEMPTS=<大于等于3的整数>
AUTO_RECOVERY_ACTIONS=<逗号分隔的非敏感动作>
AUTO_RECOVERY_RESULT=exhausted|unrepairable
LAST_VERIFIED_CHECKPOINT=<最后验证步骤>
```

运行时会拒绝没有恢复证据的 `notify-fault`。恢复穷尽使用：

```bash
python3 services/feishu_bot.py notify-fault \
  --run-id '<current-run-id>' \
  --chat-id '<original-chat-id>' \
  --stage '<skill:fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --completed-steps '<verified-completed-steps>' \
  --evidence '<non-sensitive-evidence>' \
  --recovery-skill '<current-skill>' \
  --recovery-attempts '3' \
  --recovery-actions '<non-sensitive-actions>' \
  --recovery-result exhausted
python3 services/feishu_bot.py wait-decision \
  --run-id '<current-run-id>' --decision-kind fault --timeout-seconds 3600
```

外部不可修复状态同样必须用 `--recovery-attempts 3 --recovery-result unrepairable --unrepairable`，并在 `--recovery-actions` 分别写明三轮独立只读复核；不存在 `0` 次直接发卡例外，也不能用 `unrepairable` 绕过可执行的自动恢复。

同一故障事件只发送一张卡，复用稳定 `decision_id` 和 `message_uuid`；任何其他 waiting 决定存在时禁止覆盖 pending 或发第二张卡。只有取得非空 `message_id` 后才开始 3600 秒计时。新卡回调必须携带当前 `decision_id` 且 `operator_id` 非空；旧卡、缺操作人、非本机或原 `chat_id` 无效的回调只审计并拒绝，不修改 run。回调只解除等待，不降低检查标准。`manual_continue` 和 `retry_skill` 都先重读同一现场并跳过仍有当前证据的完成步骤。已投递且历史上不含 `decision_id` 的旧故障卡仅保留兼容，但仍必须有非空操作人且只能决定当前同一 legacy pending；一旦已创建新 `decision_id`，旧卡立即失效。

## 10. 完成与交接

- 所有适用步骤均有当前 run 的直接证据；
- 自动恢复成功项有恢复后复验证据；
- 没有 waiting fault、ambiguous 不可逆 attempt 或未清理的敏感剪贴板/临时文件；
- 后一技能继承同一上下文并立即执行，不等待用户确认或普通聊天回复；
- 只有最后技能完成，或用户在最后出口卡片选择 `stop`，流程才终止。
