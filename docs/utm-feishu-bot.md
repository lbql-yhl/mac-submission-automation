# UTM 飞书机器人说明

本项目从 `飞书机器人配置导出-20260710` 迁移了飞书机器人服务，但运行环境改为本机 macOS + UTM macOS VM。

保留能力：

- 飞书事件订阅 URL 验证。
- 接收群消息并解析提审登记数据。
- 创建运行时立即生成四位小写虚拟机名称，并和 `${SUBMISSION_VM_IMAGES_DIR}/*.utm` 及历史 run 去重。
- `/提审 状态`、`/提审 日志`、`/提审 继续`、`/提审 停止`。
- 生成 `runtime/feishu-runs.json` 和 `runtime/prompts/<run-id>.md`。
- 故障记录、恢复证据门禁和三按钮最后故障卡；`utm-24` 以五图/15 项自动自检授权并自动提交，正常主线不发提审确认卡；`utm-25` 先通过 Notion API 登记唯一 Active Key/P8，再发送无按钮成功通知卡。旧运行的提审确认回调仅保留兼容能力。

飞书用户提交格式以 [README.md 的“飞书登记格式”](../README.md#飞书登记格式) 为唯一版本；宿主机、应用、代理、代码链接和开发者账号信息仍为初始必填。解析器兼容开发者账号字段写成 `国家：`、`电话：`、`短信接收链接：`、`邮箱：`、`初始密码：` 标签形式，且短信链接 token 内含 `@` 时不得把该行误判为邮箱行。银行区块可整体省略，`ABA Routing Number：` 和 `Account Number：` 也可留空；解析器仍创建 run，`notion-utm` 在匹配 Notion 页 `账号信息` 中保留两条空标签。到 `utm-20` 时只通过 `scripts/notion_api.py` 实时读取；空值会在立即、5 秒、10 秒三轮 `verify-parent` + 双字段重读后复验，三轮仍为空才以权威数据缺失发送 `utm-20-bank-info-missing` 最后故障卡。

每台机器必须在自己的 `.env` 配置唯一 `SUBMISSION_HOST_MACHINE`：只有完整登记模板中的 `使用的宿主机` 精确匹配时才启动提审，其他宿主机登记静默忽略；普通 Codex 对话不受限制。所有卡片和兼容回调在修改 run 前都重新校验 run 宿主机与本机配置，缺失或不匹配时不得执行。

固定技能顺序：

```text
Feishu 提审信息
→ 生成 run.vm_name
→ notion-utm
→ notion-utm-1
→ utm-clone-macos
→ utm-1
→ utm-2
→ utm-3
→ vm-down
→ utm-4
→ utm-5
→ files
→ utm-clash
→ utm-6
→ utm-7
→ utm-8
→ utm-9
→ utm-10
→ utm-11
→ utm-12
→ utm-13
→ utm-14
→ utm-15
→ utm-16
→ utm-17
→ utm-18
→ utm-19
→ utm-20
→ utm-21
→ utm-22
→ utm-23
→ utm-24
→ utm-25
```

`utm-clone-macos` 不负责生成名称，只使用 `run.vm_name` 和 `${SUBMISSION_VM_IMAGES_DIR}` 克隆出精确 `<vm_name>.utm`。

UTM 后续交接规则：

- 全部 31 个技能直接继承共享合同中的 `OP-NATIVE-PASTE`、`OP-BROWSER-URL-NO-SCHEME`、`OP-APPLE-PHONE-OTP`、`OP-FIXED-PASSWORD-1234` 和 `OP-USER-CONFIRMATION`。URL 统一经 `scripts/shared_operations.py browser-url`，剪贴板只允许保留最前面一个 `http(s)://` 的 `//` 后全部原文；禁止补协议、截断、重组或验证码 `type_text` 兜底。
- 全部 31 个技能发生问题时，当前技能先暂停新的副作用。可安全修复的故障做满三轮“自动诊断 → 实际修复 → 独立复验”；不可逆、不能安全重复写入或外部不可修复状态，做满三轮独立只读复核，不重复副作用。只有三轮穷尽后才向原 `chat_id` 发送最后故障卡。`notify-fault` 强制要求 `recovery_attempts>=3`、非空 `recovery_actions`、`recovery_result=exhausted|unrepairable`；少于三轮或缺失证据时运行时直接拒绝。三个故障按钮及决定值继续保留；`manual_continue`/`retry_skill` 返回后仍先重读并执行自动恢复，不把人工回应当完成证据。
- 同一故障事件只发送一次故障卡。当前 pending fault 仍处于 `waiting` 时复用原 pending、稳定 `decision_id` 和飞书消息 `uuid`；任何其他 waiting 决定都不得覆盖 pending 或产生第二张卡。确认送达后不再调用发送接口。卡片发送结果不明时只允许用同一 `uuid` 完成底层投递，不产生第二张卡；新卡回调必须匹配当前 `decision_id`、非空操作人、本机宿主和 run 原非日报 `chat_id`，旧卡不能决定新故障。用户决定处理完成后再次检测到故障，属于新的故障事件，只发送一张新卡。
- 只有飞书返回非空 `message_id` 才算首次确认送达，写入 `first_notified_at` 并开始固定 3600 秒等待；故障卡发送后当前执行器原地等待，等待期间不发送提醒卡。一小时无回复时记录 `decision_timeout_stop`，只向原 `chat_id` 发送一次无按钮超时卡片。超时卡片发送后停止整个流程；不再重发、不再轮询、不再恢复、不再执行任何后续技能，迟到、旧卡或旧 `decision_id` 回调无效。
- 飞书机器人保留四类卡片能力：最后故障卡、用户确认 API 失败时的通用确认兜底卡、旧运行兼容提审确认卡、成功通知卡。四类卡在修改 runtime 或发送前均校验本机 host 所有权和 run 内原始非日报 `chat_id`。只有技能正文明确要求用户作业务决定时才调用 `notify-confirmation`；它先请求 `USER_CONFIRM_API_URL`，批准即记录 `confirm_continue` 和 `operator_id=user-api` 并立即执行已审批动作，不发送确认卡；API 不可达或不可判定时才回退卡片，`cancel_operation` 停止，回调后仍重验现场。新 run 的 `utm-24` 不创建任何 waiting 确认：自检通过后自动授权并提交一次。旧 review-card/callback 仍可完成旧 run但不能进入新主线。`utm-25` 只有在唯一 Active Key/P8 与 Notion 独立回读全部验证后才调用 `notify-review-success`，用户可见成功卡最多一张。
- `notion-utm-1` 的项目数据约定在有序回退中唯一匹配。金鳞产品表格完成三轮精确查询仍为 0 条后，才查询祥云产品表格：先以 `金鳞产品表格`（`view_id=vewKUW4q4W`）在 5/15/30 秒三轮 `is` 精确读取并核对应用唯一键；三轮均为零才以 `contains` 查询同表 `祥云产品表格`（`view_id=vew1k7hwhJ`）。祥云回退查询只接受应用名字段包含目标应用名的候选，祥云产品表格也必须恰好 1 条才继续，包含匹配候选必须恰好 1 条；金鳞一旦唯一命中就绝不查询祥云，并记录 `FEISHU_PRODUCT_VIEW=<view-name>` 为 `FEISHU_PRODUCT_VIEW=金鳞产品表格` 或 `FEISHU_PRODUCT_VIEW=祥云产品表格`。任一已查询视图多条、有序回退后仍零条、空值或 URL 无效才进入最后故障卡。若已打开表格的可见上下文与 API 结果矛盾，可见证据只用于核对文档/view/记录上下文，禁止抄取字段值。确认 API 上下文不一致时记录 `FEISHU_TABLE_CONTEXT_MISMATCH=verified`、停止写 Notion，并先把修复沉淀到项目技能或脚本；恢复仍不唯一/无数据才发最后故障卡。Notion `应用信息` 冲突则自动重读唯一飞书记录、重建校验、覆盖并精确回读。`应用类型` 使用固定映射自动规范化，不设人工选择分支。

- 固定密码/SSH 全自动硬规则：`demo` 与所有 `<vm_name>` 用户的项目固定登录/提权密码始终为 `1234`，不存在用户或 run 覆盖分支；完整调用 `OP-FIXED-PASSWORD-1234`，VM 登录逐键输入、已识别 GUI 授权弹窗走原生粘贴、PTY 提示只交互输入且绝不进入 argv/管道/日志。`utm-2` 保留或自动创建宿主私钥，缺失 `.pub` 时从现有私钥导出，安装给 `demo` 后核对权限、指纹和 BatchMode；`utm-3` 自动配置最终用户。连接失效时锁定同一精确 VM，最多三轮刷新 IP、检查 Remote Login/端口、恢复同一公钥并复验身份；三轮仍失败才记录恢复证据并发送最后故障卡，不向用户索取信息或切换 VM。
- `utm-1` 完成后必须停在目标 VM 的 macOS 桌面。
- `utm-2` 在宿主机通过目标配置 MAC/ARP 找到 VM IP，最多自动修复 Remote Login 三轮，验证 Apple `MachineIdentifier` 和 guest 三码；随后用宿主 PTY/`ssh-copy-id` 自动为 `demo` 安装并验证宿主公钥，记录 `SSH_SERVICE=verified` 和 `SSH_DEMO_KEY=verified`。
- `utm-3` 只通过宿主机 SSH 执行 `sudo sysadminctl` 创建 `<vm_name>` 管理员、开启 Secure Token，并验证 `admin` 组；随后自动安装同一宿主公钥并核对权限/指纹。首次发现同名或部分账号时先做三轮独立只读所有权、admin、token、home 和 key 检查；可证明属于同一中断 run 时从首个缺失项恢复，外部冲突或无法证明所有权时才发送 `utm-3-user-exists` 最后故障卡，绝不删除或猜测复用。
- `vm-down` 只通过 SSH 在 guest macOS 内执行 `/sbin/shutdown`；禁止 `utmctl stop`、`utmctl start` 和 UTM GUI 电源控制。停机后只完成共享配置与持久设置校验；后续需要运行态时仅接管外部已启动的同一 VM。
- `utm-4` 只通过宿主机 SSH 关闭软件更新自动开关，删除 `demo` 用户和 `/Users/demo`，并用命令验证；不再修改“点按墙纸以显示桌面”。
- `utm-5` 只在宿主机生成并覆盖 `${SUBMISSION_SHARED_DIR}/socks5.yml`，代理数据来自当前 Feishu 提交；不 SSH、不改 UTM、不打开 Clash。
- `files` 在克隆 VM 内通过 SSH 把 `/Volumes/My Shared Files/共享文件` 内容复制到当前用户的 `$HOME/Downloads`，保留隐藏文件和子目录，并逐项校验路径、类型、链接目标和 SHA-256 内容；源目录不删除。
- `utm-clash` 在克隆 VM 内配置固定开关并导入 `$HOME/Downloads/socks5.yml`。Profile/Proxy 点击每次使用最新截图；五次延迟未变为数字后，自动核对配置、端口、进程和公网出口，确定性修复并重启 Clash Verge 一次，再完整复验。仍失败才发最后故障卡。匹配当前 UTM/Computer Use 的 Automation 权限弹窗自动 `Allow` 并确认关闭；来源不明时先独立重读进程/窗口归属三轮，仍不明才发最后卡。
- `utm-6` 必须在 `utm-clash` 后执行；在 guest 终端用当前 Feishu 运行的代理 IP 与公共出口 IPv4 做精确比较，只有一致才算代理成功。随后按 `utm-6` 设置并检查 guest `~/.zshrc` 的 Ruby/Flutter PATH、Pub 镜像和 Flutter 存储镜像变量；不一致或检查失败时不得继续。
- `utm-7` 在 `utm-6` 后执行，只通过 `scripts/utm_7_login.py` 调用同一 Notion API 读取匹配页的邮箱、当前密码、电话和短信链接，再经 SSH-stdin JSON 将值交给项目登录 helper；helper 在 guest 内无视觉完成 Apple Account 登录、电话/SMS 验证、固定 `1234` Mac Password、随机安全弹窗和邮箱关闭/重开复核；验证码按时间字段取当前最新、无时间字段按页面顺序取最后一条。账号、号码、无法判定最新验证码或挑战异常先执行同一 VM/Notion/SSH 的自动恢复；只有 CAPTCHA、锁号或未知挑战被证明为外部不可修复时才进入最后故障卡。
- `utm-8` 在 `utm-7` 后执行，仅操作同一目标 UTM guest；通过字段级 Notion API 读写并核对最终控件。全部自检通过后自动点击一次 `Change`/`Continue`；复杂度拒绝时最多自动生成三个互不相同且符合规则的候选，每次重新填写、复验后再提交一次，接受后才更新 `修改后的密码：`。已知短信/2FA 自动处理；账号锁定或未知安全弹窗经只读分类后才进入最后故障卡。
- `utm-9` 在 `utm-8` 后执行：通过 Notion API 读取 `邮箱：`，通过 SSH 打开 guest Keychain Access，用 Computer Use 进入 Certificate Assistant，创建并保存证书请求到 guest Desktop，验证文件已生成。
- `utm-10` 在 `utm-9` 后执行：继续使用同一个 guest Edge 会话打开 Apple Developer 并确认账户页；需要登录或短信验证时只通过 Notion API 读取当前字段。
- `utm-11` 在 `utm-10` 后执行：先在同一 guest Edge 自动确认/接受最新 Paid Applications Agreement，再进入 Small Business Program，第一题选 Yes，后四题选 No，慢速确认声明复选框后自动提交；成功页保存、校验当前 run 的 `05-small-business.png`，成功页已存在时只恢复截图、不重复提交。协议/安全状态异常先回到账号和页面锚点独立重读三轮；只有三轮后外部 schema/安全状态仍不能归类时才发最后故障卡。
- `utm-12` 在 `utm-11` 后执行：自动处理协议、慢速读取 Membership details，通过 Notion API 写入并回读 Team ID/Renewal date；注册 App ID，填写并创建 iOS App，验证 `iOS App Version 1.0`。全程自检，不等待用户确认。
- `utm-13` 在 `utm-12` 后执行：切回已有的 `Certificates, Identifiers & Profiles` 标签页，创建/导入 Apple Distribution 证书；进入 Profiles 选择 App Store Connect、唯一 App ID 和 Distribution 证书，通过 Notion API 读取 `应用名: ` 后粘贴生成 Provisioning Profile，并验证 `Download and Install` 页面。
- `utm-14` 在 `utm-13` 后执行：继续使用同一 guest Edge 进入 Business；按页面条件完成 DSA 合规与 Paid Apps Agreement，回答 U.S. Tax Questionnaire 两题 `No`（`Next` 后 `Save`），准备 U.S. Certificate of Foreign Status of Beneficial Owner 与 W-8BEN。两份表单各自完成账号、字段、声明和唯一按钮自检后自动点击一次最终 `Submit`，每次都验证返回 Business；未知安全、来源歧义或提交结果不明先回锚、重读权威来源并只读核对同一提交 attempt，恢复穷尽后才发最后故障卡。最后将 `Directive on Administrative Cooperation - 7th Amendment` 保存为 `No`。
- `utm-15` 在 `utm-14` 完成并确认 `DAC7_INFO=No_saved` 后执行：继续使用同一 guest Edge，从 Business 进入 `Apps`，从详情页 URL 读取数字 App ID；通过字段级 Notion API 只更新 `APP_ID：` 并写后回读，不点击 `Add Apps`，不新增 `app_id:`。
- `utm-16` 在 `utm-15` 后执行：先用 `scripts/notion_api.py verify-parent` 校验当前父页面，再运行 `python3 -m scripts.utm_16_generate_env --parent-title '<宿主机名称>' --page-title '<应用名>-<vm_name>'`。生成器复用 API 客户端，只发 GET 请求读取唯一 `账号信息` 和 `应用信息` code block，按精确标签解析并生成固定 `${SUBMISSION_SHARED_DIR}/.env`；Notion 字段值不进入 JSON/命令参数或终端输出。`PRIMARY_CATEGORY` 由脚本把受支持的 `应用类型：` 展示值转换为固定 App Store Connect 枚举，也接受已规范化枚举；未知分类先重新验证父页/字段三轮，仍不属于固定映射才作为权威配置缺失进入最后故障卡。不展示完整 `.env`、不等待用户确认。验证字段、权限和哈希，直接继承 `utm-15` 的当前 VM/IP/SSH 身份并做一次轻量身份检查，通过 guest 共享挂载 SSH `cp` 到 `/Users/<vm_name>/Downloads/Fire_One_en1.2/.env`，设为 `600`，并用新 SSH 连接验证宿主、共享源、guest 目标的 SHA-256 完全一致；最后 SSH `cat` 完整目标文件做第二重自动检查，不转发联系人信息，不运行发布命令。
- `utm-17` 在 `utm-16` 后执行：通过 Notion API 只读取唯一非空的 `研发金币图链接：` 和 `金币表格: `，禁止回退 `截图链接: `；字段为空、缺失、重复或非 URL 时先重新 `verify-parent` 并重读三轮，仍无权威唯一值才发最后故障卡。在同一 guest 已有浏览器进程中下载后，通过 SSH 校验精确文件名及其与 `Fire_One_en1.2` 同级。
- `utm-18` 在 `utm-17` 后执行：通过分开的 BatchMode 宿主 SSH 命令重启 guest Edge 并验证 9222 CDP 和 Apple Developer 登录；必要登录复用 `utm-10` 的 Notion API-only 路径。不打开 guest Terminal，改用前台 SSH `/bin/zsh -lic` 加载环境并执行 `npm run fill:description`。远端 `tee` 将完整输出实时回传并持久化为权限 `600` 的唯一日志，zsh `pipestatus` 和 `.status` 分别保存 npm/tee 退出码与运行状态；新 SSH 完整核验日志、字节数和 SHA-256。SSH/IP/Remote Login/公钥恢复始终自动完成；业务失败卡返回 `manual_continue` 或 `retry_skill` 时由当前执行器立即恢复，但必须先完成歧义状态检查、跳过已验证步骤并为新尝试创建唯一日志，不用于修 SSH，也不要求用户提供 SSH 信息。
- `utm-19` 在 `utm-18` 后执行：通过 Notion API 唯一读取 `截图链接: `，只删除字符串最前面的 `https://` 或 `http://` 协议头，`://` 后所有字符逐字完整保留，再在同一 guest Edge 下载 ZIP。通过宿主 SSH 安全校验并解压，统计本轮唯一 JPEG 集合为 `N` 张，不得预设数量。进入匹配应用的 `View All Sizes in Media Manager`，选择 `6.9" Display` 的 `Choose File`；文件选择器先点第一张建立焦点，再从 `Edit` 菜单逐项 `Down` 到 `Select All` 蓝色高亮后按 `Return`，确认全部 `N` 张同时选中再只点一次 `Open`。必须验证与 SSH 统计一致的 `N of 10 Screenshots`；禁止坐标直点或未高亮确认 `Select All`、逐张上传和点击保存/送审控件。
- `utm-20` 在 `utm-19` 后执行：保持同一现场；Notion `商务` 冲突先独立重读 Business/Notion 三轮，真实所有权冲突才发最后故障卡。银行流程从精确未完成步骤自动续跑，条款、唯一 `Add` 和 2FA 自动完成。银行号码为空时立即、5 秒、10 秒三轮重读当前 Notion 页，仍为空才以权威数据缺失发送最后故障卡。任何卡片都不是正常确认节点。
- `utm-21` 在 `utm-20` 后执行：由 `scripts/utm_21_clone.py` 在脚本内读取 Notion 代码链接，Codeup 凭据仅从本机 `.env` 进内存并经 SSH stdin 使用。已有目标先分类 pristine/resumable/conflict；前两类自动验证/续跑，真实所有权冲突才发卡。四项占位符总命中为零时先检查实际声明是否已等于目标值，已完成则继续；模板合同冲突才发最后故障卡。随后执行依赖安装并完整复验。
- `utm-22` 接着 `utm-21` 复用同一 guest：重新确认 IP/SSH/workspace 和实际运行的 Xcode bundle/version，通过 SSH 打开 `Runner.xcworkspace`，在 Xcode GUI 中确认 Profile/Team/Apple Distribution 证书后点击 `Product` → `Archive`，并只选择元数据唯一匹配的新 Organizer Archive。此后不点击 Xcode `Distribute App`，改用 `scripts/utm_22_distribute.mjs prepare/distribute` 只读校验、封装并通过 Apple Build Uploads API 上传、提交 `uploaded=true`，要求 Build Upload 为 `COMPLETE` 且关联 Build 为 `VALID`；Game Center 精确恢复同样只用 Xcode GUI 添加 capability、构建号加一并重新 Archive。成功后记录 `UTM_22=verified`，结束 `utm-22`，保留同一 VM、当前构建上下文和既有 guest Edge，立即继续 `utm-23`，不等待用户确认。
- `utm-23` 在 `utm-22` 后执行：以有序状态账本分类并从首个未完成项自动续跑；`Add Build` 暂不可见只做 15/30/60/120 秒页面/API只读查询，严禁再次上传。App Information 删除使用 before/after 证据，结果不明不重复删除。恢复穷尽才发最后故障卡。完成两图后记录 `SUBMIT_FOR_REVIEW=not_clicked` 并立即继续。
- `utm-24` 紧接 `utm-23`：只采集 `01`、`04`，验证五图、版本/构建、14 个 IAP 和 15 项范围后调用 `record-auto-review-approval`，写入完整 `automatic_self_check` 授权并自动点击一次 `Submit for Review`，不发确认卡、不等待回复。提交与加急各有稳定一次性 attempt；结果不明只读查询，禁止第二次点击。成功后立即移交 `utm-25`。
- `utm-25` 紧接 `utm-24`：Team Keys/P8 先完整扫描、去重、重读复验；仍非唯一才发最后故障卡。Notion 写入失败使用 before 自动还原并独立回读，`NOTION_ROLLBACK=verified` 后才报告原故障。只有 `NOTION_REFUND_CALLBACK_P8=verified` 和完整自动 approved 快照都成立才发送一次成功通知；结果未知复用同一 UUID。
- SSH 修复始终自动执行并锁定同一精确 VM；后续技能自身的业务 attempt 边界优先。三轮自动恢复和身份复验仍无法建立公钥连接时，记录 `SSH_AUTO_RECOVERY=blocked` 与恢复证据，才由当前技能发送最后三按钮故障卡；继续决定仍重跑同一 VM 恢复，不向用户索取信息。
- `utm-3` 不改用系统设置 GUI；中断先自动修复 SSH，再按账号所有权/admin/token/home/key 账本恢复。同一 run 的部分完成自动续跑，外部同名冲突才进最后故障卡。
- 非 SSH 的业务/数据现场有明确恢复方法且风险可控时自动重试；无法安全判断时按对应技能的故障卡边界处理。该规则不得用于要求用户修复 SSH 或提供 SSH 信息。
- `utm-18` 每次 `npm run fill:description` 都有唯一日志/status attempt。失败先自动分类：仍运行或部分副作用只读恢复同一 attempt；可证明零副作用且错误有确定修复时自动修复并创建一个新 attempt。只有部分/歧义结果或安全恢复穷尽时才发最后故障卡。`SSH_EXIT=255` 先修复同一 VM 连接，再只读检查本轮 attempt，绝不盲目重跑。

默认配置：

- `FEISHU_WS_ENABLED=1`，使用飞书长连接接收消息回调。
- `FEISHU_TUNNEL_ENABLED=0`，不再使用会变地址的 Cloudflare quick tunnel。
- `SUBMISSION_RUNNER_COMMAND=`，匹配完整登记后只生成 Codex App 会话交接，禁止从飞书入口后台启动连续主线。

卡片回调约束：

- 故障卡片使用 JSON 2.0（`schema: "2.0"`、`body.elements`）。
- 按钮使用 `behaviors: [{"type": "callback", "value": {...}}]`，且 `value` 必须是对象。
- 长连接收到 `card.action.trigger` 时，先在原始 CARD 帧边界把历史客户端可能传回的 JSON 字符串 `event.action.value` 归一化为对象，再交给 SDK；否则 SDK 严格 Dict 反序列化会返回 500，客户端显示 -101。HTTP 回调继续使用同一业务解析器。
- 三个故障按钮必须保持固定顺序和决定值；回调处理完成后更新原卡，`stop` 不派生第二张停止卡。
- 通用用户确认先调用用户 API `USER_CONFIRM_API_URL`（默认 `http://127.0.0.1:8000/confirm`），只发送 `宿主机名`、`应用名`、`要确认的动作`；返回批准时直接记录 `confirm_continue` 和 `operator_id=user-api`，不发送卡片。API 不可达或返回不可判定时才回退使用 `submission_confirmation_decision` callback、当前 `decision_id` 和决定值 `confirm_continue|cancel_operation`；点击回调就是用户对该单一问题的回复，不需要额外聊天消息或第二次触发。只有宿主机/原群聊、同一 `decision_id`、非空操作人、`answered/confirm_continue`、`wait-decision` 退出 0 和回调后现场证据全部复验通过才记录 `USER_CONFIRMATION=verified`；Toast 或卡片变色不算。
- 旧运行兼容提审确认卡使用 `submission_review_decision` callback 和 `decision_id`；新运行正常主线不创建该卡。成功通知卡不含按钮或 callback。故障卡仍使用独立三按钮 callback，三种决定不能互相替代。
- 不使用旧版 JSON 1.0 的 `tag: "action"` 容器；旧版卡片回调不支持飞书长连接。
- 回调协议测试使用隔离测试运行号或 mock transport，不覆盖已完成记录；生产流程不因修复自动发送额外测试卡。

飞书登记入口必须交给 Codex App 前台会话接手，不配置后台 runner：

```env
SUBMISSION_RUNNER_COMMAND=
```

如果要启用群消息历史轮询兜底，把允许问答的同一个非日报群 `chat_id` 填到：

```env
FEISHU_POLL_CHAT_IDS=oc_xxx
```

长连接与轮询会按飞书 `message_id` 原子去重。使用 ChatGPT 登录的 Codex CLI 0.144.6+ 时，问答模型配置为：

日报专用群只允许接收提审日报。日报发送前必须先基于本地项目证据生成预览，第一行写当天日期，等待用户明确确认同一份文本后再发送；命令回复、状态、帮助、测试消息、故障卡、成功卡和普通助手回复都必须静默拒绝，不能发送到日报专用群。日报证据只取本地项目文件、`SKILL.md` 创建/修改时间、repo-local docs、运行时日志、`/health`、cloudflared/tunnel 状态和真实发送回执；除非用户明确要求，不使用 Git 状态或提交历史。

```env
FEISHU_ASSISTANT_PROVIDER=codex
FEISHU_CODEX_COMMAND=codex
FEISHU_CODEX_MODEL=gpt-5.6-sol
```
