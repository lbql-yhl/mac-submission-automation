# mac 提审自动化

这个项目已接入飞书机器人入口。机器人负责接收群里的提审登记信息，生成运行记录、去重后的虚拟机名称和 Codex 提示。任何异常先完成至少三轮确定性诊断、安全修复和独立复验；外部不可修复状态也做三轮只读复核。少于三轮时运行时禁止发送故障卡。

## 现行执行权威

项目内 [`skills/`](skills) 是当前 31 个技能的唯一源；运行时只以本文件、`AGENTS.md`、匹配的 `skills/<当前技能>/SKILL.md` 和对应 `docs/utm-*.md` 为执行合同。`scripts/install_project_skills.sh` 只在 `~/.codex/skills` 建立指向项目源的发现链接，那里不再保存第二份技能。历史 plans/specs 已移除，不能作为执行输入。最终阶段的唯一边界是：`utm-24` 完成系统自检授权、提审与加急并记录通知未发送，`utm-25` 完成唯一 Active Key/P8 登记和 Notion 独立回读后才发送绿色成功卡。

所有技能统一执行 [`skills/_shared/AUTOMATION_CONTRACT.md`](skills/_shared/AUTOMATION_CONTRACT.md)：异常先自动诊断、自动修复、自动复验；GUI 每次动作后至少等待 3 秒并读取最新状态，误点先用 `Escape`/`Back`/`Cancel` 回到最近验证锚点再重做。只有三轮恢复/只读复核穷尽后，才允许发送飞书故障卡。下文任何“发故障卡”均以此门禁为前置，不表示首次失败就发卡。

## 共享重复操作记忆

31 个技能都直接继承共享合同中的五个稳定操作 ID，不再复制简化版本：

- `OP-NATIVE-PASTE`：随机哨兵证明本轮 Copy 覆盖旧值，右键菜单必须在新截图中可见、可用并蓝色高亮，粘贴后回读；敏感值立即清空。
- `OP-BROWSER-URL-NO-SCHEME`：API URL 必须执行 `pbpaste | python3 scripts/shared_operations.py browser-url`；只复制最前面一个 `http(s)://` 的 `//` 后全部原文，不添加协议、不截断、不重组。正文批准的裸常量才可用 `--allow-bare`。
- `OP-APPLE-PHONE-OTP`：实时读取电话/短信平台，唯一尾号、唯一当前六位码、原生粘贴、消费后清空；禁止 `type_text` 验证码兜底。
- `OP-FIXED-PASSWORD-1234`：按 VM 登录、已识别 GUI 授权弹窗、PTY 密码提示三种上下文执行，固定值无覆盖分支且永不询问用户。
- `OP-USER-CONFIRMATION`：只有技能正文明确要求用户作业务决定时才发通用确认卡；用户点击就是该单一问题的回复。仅当本机/原群聊、同一 `decision_id`、非空操作人、`answered/confirm_continue`、`wait-decision` 退出 0 和回调后现场证据全部复验通过时，才记录 `USER_CONFIRMATION=verified` 并继续。正常技能交接和 `utm-24` 自动提审不使用确认卡。

## 自动化主线

```text
飞书收到用户提审信息
→ 解析登记数据并创建 submission run
→ 生成四位小写虚拟机名称，并和已有 .utm / 历史 run 去重
→ notion-utm：通过 Notion API 从模板创建 <应用名>-<虚拟机名称> 并登记账号信息；初始银行区块/号码允许缺省并保留空标签，其他异常先重读 run/父页/模板、按 before 回滚并独立复验，只有恢复穷尽或外部数据冲突才发最后故障卡
→ notion-utm-1：通过 Notion API 补填应用信息
→ utm-clone-macos：用同一个虚拟机名称和 `${SUBMISSION_VM_TEMPLATE}` 克隆到 `${SUBMISSION_VM_IMAGES_DIR}`；模板或克隆异常先对同一路径、复制 attempt、plist/身份和目标所有权自动恢复，穷尽后才发最后故障卡
→ utm-1：配置并启动这个 VM；克隆交接缺失时先自动重跑同一 run 的克隆步骤
→ utm-2：自动启用 SSH、确保宿主 Key 存在、安装给 demo、核对 authorized_keys 权限/指纹和 BatchMode，再记录 guest 三码；三轮同 VM 修复与复验仍失败后才发送最后故障卡
→ utm-3：通过 SSH 创建与 demo 同权限的管理员用户，并一次性配置同一宿主机 Key
→ vm-down：SSH 正常关机，停机态检查 UTM 共享设置，再开机并登录虚拟机同名管理员用户
→ utm-4：关闭自动更新开关并删除 demo 用户
→ utm-5：在宿主机生成并覆盖 `${SUBMISSION_SHARED_DIR}/socks5.yml`
→ files：通过 SSH 把 guest 共享目录内容复制到当前用户的 Downloads 并校验
→ utm-clash：配置 VM 内 Clash Verge 固定开关，并导入、选中 Downloads/socks5.yml
→ utm-6：验证 guest 出口 IP 等于当前代理 IP，并设置、校验 guest ~/.zshrc 环境变量
→ utm-7：通过 Notion API 读取已登记账号，在目标 UTM guest 的系统设置中登录 Apple Account
→ utm-8：读取 Apple Account Personal Information，回写 Notion 用户名/生日，修改密码并登记修改后的密码
→ utm-9：通过 Notion API 读取邮箱，在同一 UTM guest 的钥匙串访问中请求证书并保存到 guest Desktop
→ utm-10：必要时通过 Notion API 读取登录/短信字段，在同一 guest Edge 中打开 Apple Developer 并确认账号页
→ utm-11：先自动确认/接受最新 Paid Applications Agreement，再进入 App Store Small Business Program，第一题选 Yes、后四题选 No，确认声明后提交，并在成功页保存当前 run 的 `05-small-business.png`
→ utm-12：自动处理协议、登记 Team ID/Renewal date、注册 App ID，并创建 App Store Connect 应用
→ utm-13：切回 Certificates, Identifiers & Profiles，创建/导入 Apple Distribution 证书，通过 Notion API 读取应用名并生成 App Store Connect Provisioning Profile
→ utm-14：继续使用同一 guest Edge，进入 Business，完成 DSA/付费协议、税务问卷、受益所有人证明表和 W-8BEN；生日通过 Notion API 读取，返回 Business 后处理 Directive on Administrative Cooperation - 7th Amendment，选择 No 并保存
→ utm-15：确认 utm-14 已保存 DAC7 信息后，打开匹配应用，读取 URL 中的数字 App ID，并登记到匹配 Notion 的 APP_ID：
→ utm-16：通过 Notion API 只读并校验匹配页面的账号/应用区块，直接生成 `.env`，继承 `utm-15` 的当前 VM/IP/SSH 后通过 SSH `cp` 到同一 guest，并校验三端哈希和完整内容
→ utm-17：通过 Notion API 读取研发金币图和金币表格链接，在同一 guest 已有浏览器的新 tab 中下载，再用 SSH 校验精确文件名及其与 Fire_One_en1.2 同级
→ utm-18：通过全自动 BatchMode SSH 重启 guest Edge 并启用 9222 CDP；必要登录复用 Notion API-only 的 utm-10 路径，确认 Apple Developer 已登录后以前台 SSH 的 `zsh -lic` 环境执行 `npm run fill:description`；SSH/IP/Key 恢复不需要用户，stdout/stderr 由远端 `tee` 完整实时回传并写入权限 600 的唯一日志。失败先按唯一 attempt 的日志/status/业务结果自动分类并修复；只有部分副作用无法对账时才发最后故障卡
→ utm-19：通过 Notion API 读取截图链接，在同一 guest Edge 下载并安全解压截图包；用 SSH 统计本轮 JPEG 数量 `N`，核对当前数字 App ID、已有截图与剩余容量，只允许 `empty|complete` 二选一：`empty` 一次上传全部 `N` 张，`complete` 独立复核后幂等跳过；任意部分上传或无法对账状态都停止新上传并先恢复，成功必须验证 `N of 10 Screenshots`
→ utm-20：首次接着 utm-19 的当前 Media Manager 页面进入 `Business`；复跑则保留同一标签页的 Business/银行现场，商务内容完全一致时跳过写入并从精确未完成点恢复。银行信息为空时先三次实时重读同一 Notion 页；三轮仍为空才作为外部权威数据缺失发最后故障卡。双重认证按实时 Notion 电话和短信链接自动取码，最后确认银行更新为 `Processing`
→ utm-21：继承 utm-20，通过 Notion API 实时读取代码链接、正式包名和 APP_ID；Codeup 凭据仅从本机 `.env` 读取并经 SSH stdin 内存通道使用。目标仓库已存在时先自动分类为同一 pristine、同 run 可恢复或外部冲突；占位符零命中时先对账最终值和声明位置。只有无法安全归属/映射才发最后故障卡；随后完成替换、flutter pub get 和 ios/pod install 并交给 utm-22
→ utm-22：复用同一 guest，在 Xcode GUI 中确认签名/Profile并以稳定 Archive attempt 点击 Product > Archive；Organizer 出现唯一匹配的新 Archive 后，不点 Distribute App。API 上传先持久化 `UPLOAD_ATTEMPT_ID` 并查询同版本/构建号，只创建零候选的唯一上传，结果不明只恢复同一 attempt，直到 COMPLETE/VALID；Game Center 精确恢复也只通过 Xcode 点击重新 Archive
→ utm-23：返回同一 UTM guest 的既有 Edge；完整终态直接移交，明确初始态执行正常路径，部分准备建立逐项状态账本并确定性恢复到第一个未完成步骤。只有多草稿、归属冲突或不可逆结果经三轮独立只读复核仍不明确才发最后故障卡；最终保存并验证 `02-iap-drafts.png`、`03-app-information.png`
→ utm-24：紧接 utm-23 立即执行，只保存最终状态下的 `01-media-manager.png`，并通过 Notion API 读取隐私协议后保存 `04-privacy-agreement.png`；五图、版本/构建、14 个 IAP 和最终 15 项范围全部通过后，运行时写入 `source=automatic_self_check` 的授权快照并自动点击一次 `Submit for Review`，不发送提审交互卡、不等待回复；明确成功后完成一次幂等加急审核并移交
→ utm-25：在同一 guest Edge 打开 App Store Connect API 页面，只接受唯一 Active Key；安全取得已下载 P8，通过 Notion API 写入并独立回读 `退款回调及p8`，验证成功后才按 runtime 稳定 UUID 防重发送绿色成功卡
```

`utm-8` 测试前置、输入状态和验收标记见 [docs/utm-8.md](docs/utm-8.md)。
`utm-9` 测试前置、操作顺序和验收标记见 [docs/utm-9.md](docs/utm-9.md)。
`utm-12` 会员信息、App ID 和 App Store Connect 创建步骤见 [docs/utm-12.md](docs/utm-12.md)。
`utm-13` 证书导入和 Provisioning Profile 生成步骤见 [docs/utm-13.md](docs/utm-13.md)。
`utm-14` App Store Connect Business 页面操作步骤见 [docs/utm-14.md](docs/utm-14.md)。
`utm-15` 获取 App ID 并登记 Notion 的操作步骤见 [docs/utm-15.md](docs/utm-15.md)。
`utm-16` 从 Notion 读取、生成、SSH 写入并核验 `.env` 的操作步骤见 [docs/utm-16.md](docs/utm-16.md)。
`utm-17` 下载研发金币图和金币表格、规范文件名及同级校验的操作步骤见 [docs/utm-17.md](docs/utm-17.md)。
`utm-18` 重启 guest Edge、确认 Apple Developer 登录并填写应用描述的操作步骤见 [docs/utm-18.md](docs/utm-18.md)。
`utm-19` 下载、解压截图包并在 Media Manager 一次性上传 6.9" 截图的操作步骤见 [docs/utm-19.md](docs/utm-19.md)。
`utm-20` 登记 Business 商务信息、新增银行账户并完成宿主终端短信验证的操作步骤见 [docs/utm-20.md](docs/utm-20.md)。
`utm-21` 拉取 Codeup Flutter 项目、替换正式标识并安装 Flutter/CocoaPods 依赖的操作步骤见 [docs/utm-21.md](docs/utm-21.md)。
`utm-22` 的 Xcode GUI Archive、命令/API 上传和 Game Center 恢复路径见 [docs/utm-22.md](docs/utm-22.md)。
`utm-23` 的 Add Build 有界只读可见性恢复、部分现场状态账本、构建与合规处理、14 项内购和 App Version 唯一草稿、App Information 清理及移交步骤见 [docs/utm-23.md](docs/utm-23.md)。
`utm-24` 紧接 `utm-23` 的五图校验、系统自检授权、自动一次性提交和加急审核步骤见 [docs/utm-24.md](docs/utm-24.md)。
`utm-25` 的唯一 Active Key/P8 登记、Notion API 哈希回读及成功通知防重步骤见 [docs/utm-25.md](docs/utm-25.md)。

虚拟机名称只在 Feishu 创建运行时生成一次。后续技能必须复用 run 里的 `vm_name`，不要在 `utm-clone-macos` 里重新生成。

连续正常路径中，后一技能直接继承前一技能已验证的 run、VM/IP、浏览器会话和工作目录，只做当前目标的一次轻量存活/身份检查；不得按“最新”重新选择 run 或 VM。只有继承连接失效或任务中断时，才进入该目标的精确恢复检查。

## 飞书异常故障卡

- 全部 31 个技能统一执行：发生问题先暂停新的副作用。可安全修复的故障必须做满三轮“自动诊断 → 实际修复 → 独立复验”；不可逆动作、不能安全重复写入或外部不可修复状态，则不重复副作用，改做三轮独立只读复核。只有三轮穷尽后才允许调用 `notify-fault`。运行时强制要求 `recovery_attempts>=3`、非空 `recovery_actions` 和 `recovery_result=exhausted|unrepairable`；少于三轮或缺少证据的请求直接拒绝。
- 同一故障事件只发送一次故障卡。当前 pending fault 仍处于 `waiting` 时，重复调用 `notify-fault` 复用原 pending、稳定 `decision_id` 和消息 `uuid`；其他 waiting 决定不得覆盖它或触发第二张卡。确认送达后不再调用发送接口，也不发送提醒卡。回调必须匹配当前 `decision_id`、非空操作人、本机宿主和原非日报群聊，旧卡不能决定新故障。
- 卡片服务先自动修复/重试并确认交互卡已送达；发送结果不明时只复用同一飞书 `uuid` 完成底层投递，不产生第二张卡。只有飞书返回非空 `message_id` 才算首次确认送达，记录 `first_notified_at` 并开始固定 3600 秒计时。故障卡发送后当前执行器立即原地等待，等待期间不发送提醒卡。
- 满一小时仍无回复时，机器人记录 `decision_timeout_stop`，只向当前 run 原 `chat_id` 发送一次无按钮超时卡片。超时卡片发送后停止整个流程；不再重发、不再轮询、不再恢复、不再执行任何后续技能，迟到、旧卡或旧 `decision_id` 回调均无效。
- 故障卡固定三个按钮：`停止流程`、`已人工处理，继续流程`、`重试技能，跳过已处理成功的步骤`，对应决定值 `stop`、`manual_continue`、`retry_skill`。当前执行器收到回调后立即执行，不需要第二次人工触发；每个继续分支都先重新执行自动恢复，仍不可修复才形成新的故障事件和新卡。
- 停止结果只更新原故障卡，不另发停止通知。
- 飞书运行时保留四类卡片能力：最后故障卡、通用用户确认卡、兼容旧运行的提审确认卡、`utm-25` 成功通知卡。通用确认使用 `notify-confirmation` 和 `wait-decision --decision-kind confirmation`；相同 waiting 决定复用稳定 UUID，`confirm_continue` 等价于用户确认并继续，`cancel_operation` 停止。当前 31 步正常主线没有必须确认节点，因此不发送通用确认卡或提审确认卡；`utm-24` 自检通过后自动授权并提交一次。每个卡片副作用前仍重新核对 run 宿主机与原群聊；`utm-25` 只有在唯一 Active Key/P8 已写入并独立回读后，才以稳定 UUID 最多发送一张无按钮成功卡。

## SSH 全自动硬规则

- `demo` 和所有 `<vm_name>` 用户的 macOS 登录/`sudo` 固定密码始终为 `1234`，没有用户或 run 覆盖分支。
- 宿主机固定复用 `${SUBMISSION_SSH_PRIVATE_KEY}` 和 `${SUBMISSION_SSH_PUBLIC_KEY}`。`utm-2` 自动确保 Key 存在并配置给 `demo`；`utm-3` 创建最终用户后自动配置同一公钥，只有 `BatchMode=yes`、用户/home、权限和指纹全部通过才记录 `SSH_KEY_AUTH=verified`。
- 从 `vm-down` 开始，所有技能只继承同一精确 VM/IP/SSH 身份并做一次轻量 BatchMode 检查，不重复配置。失败时自动按该 VM 的配置 MAC 刷新 IP、检查 Remote Login/端口并用固定 `1234` 恢复同一宿主公钥。
- 不得向用户索取密码、SSH Key、IP 或其他 SSH 信息，不得让用户配置 SSH。同一 VM 的三轮 IP/Remote Login/端口/公钥恢复与身份复验仍失败时，记录完整恢复证据和 `SSH_AUTO_RECOVERY=blocked`，再发送最后三按钮故障卡；继续决定仍重跑同一自动恢复，禁止改选其他 VM。

## 固定技能职责

1. `notion-utm`：从 Feishu bot runtime/API 读取登记数据，用 `scripts/notion_api.py` 从当前宿主机页面的唯一 `模板` 创建 `<应用名>-<vm_name>`，只填写并回读验证 `账号信息`。初始银行区块可省略、两项号码可留空。其他异常先重新解析同一 run、三轮读取父页/模板、使用 before 恢复可逆写入并独立回读；仍不唯一、冲突或回滚失败才向原 `chat_id` 发最后故障卡。
2. `notion-utm-1`：通过 Feishu API 精确读取多维表格 `26财年巨风做包表` 的 `金鳞产品表格` 视图（`view_id=vewKUW4q4W`），再通过 Notion API 补填并回读已有页面的 `应用信息`。0 条/多条、URL 空白或无效时先重取 token、核对固定表/view 并在 5/15/30 秒三次实时重读；仍缺失才作为外部权威数据故障发最后卡。若 Notion `应用信息` 已有冲突内容，则重新实时读取同一条唯一飞书记录、重建并校验模板，使用 `--replace-existing` 自动覆盖并精确回读，不发确认卡。`应用类型` 按项目固定映射自动规范化，不设人工选择分支。
3. `utm-clone-macos`：模板从 `${SUBMISSION_VM_TEMPLATE}` 解析，目标固定为 `${SUBMISSION_VM_IMAGES_DIR}/<vm_name>.utm`；复制后更新名称、UUID、MAC 和 Apple `MachineIdentifier`。模板、目标或 plist 异常先核对同一 run 所有权、清理仅由本 attempt 创建的不完整目标并重试一次；仍失败才发最后故障卡，不搜索替代模板。
4. `utm-1`：继承不可变 run/`vm_name`；克隆标记或 VM 包缺失时自动重跑同一 run 的 `utm-clone-macos` 并复查，仍异常才发送 `utm-1-handoff-recovery` 故障卡。随后配置只读共享目录、随机化网络 MAC，启动 VM 并登录 `demo` 桌面。
5. `utm-2`：确认 Apple `MachineIdentifier` 不重复，获取 VM IP，自动启用 Remote Login；确保固定私钥存在、缺失公钥时从私钥导出，安装给 `demo`，核对 `authorized_keys` 权限、宿主/guest SHA-256 指纹和 BatchMode，再读取 guest `IOPlatformSerialNumber`/`IOPlatformUUID`。同一 VM 三轮修复耗尽并复验后才发送最后故障卡，不向用户索取 SSH 信息。
6. `utm-3`：只通过 SSH 使用 `sudo sysadminctl` 和固定 `1234` 创建 `<vm_name>` 管理员、开启 Secure Token，随后把同一宿主公钥自动安装到最终用户并记录 `SSH_KEY_AUTH=verified`。预检发现同名用户时先用两条只读 SSH 对账 run marker、UID/home/admin/Secure Token/Key 指纹；同一中断 run 自动补完，外部账号冲突才进入 `utm-3-user-exists` 最后故障卡，绝不自动删除用户。
7. `vm-down`：只通过 SSH 在 guest macOS 内执行 `/sbin/shutdown` 正常关机；禁止 `utmctl stop` 和 UTM GUI 电源控制。停机后、开机前必须在 UTM 的目标 VM 编辑/设置窗口 `共享` 页确认 `${SUBMISSION_SHARED_DIR}` 已添加且 `只读?` 已启用；如果缺失就勾选 `添加只读` 后添加该目录并保存，若已有但非只读则移除后按只读重加。复查通过后再用 `utmctl start` 开机，登录 `<vm_name>`，完成首次登录固定选择，并验证 SSH/admin、guest 共享目录挂载和只读写入失败。`socks5.yml` 由后续 `utm-5` 生成，不是 `vm-down` 前置条件。
8. `utm-4`：只通过 SSH 关闭软件更新自动开关，删除 `demo` 用户和 `/Users/demo`，并用命令验证。
9. `utm-5`：只在宿主机生成并覆盖 `${SUBMISSION_SHARED_DIR}/socks5.yml`，代理数据来自当前 Feishu 提交；不 SSH、不改 UTM、不打开 Clash。
10. `files`：在 guest 内通过 SSH 将 `/Volumes/My Shared Files/共享文件` 的内容复制到 `$HOME/Downloads`，保留隐藏文件和目录，并逐项校验。
11. `utm-clash`：在克隆 VM 内配置 Clash Verge，导入并选中 `$HOME/Downloads/socks5.yml`；Profile 选择复用当前 Computer Use GUI 驱动器。延迟检查五次仍不显示数字时自动核对配置/端口/公网出口并重启 Clash Verge 一次，修复后复验；仍失败才发最后故障卡。最终状态为 Tun Mode on、System Proxy off、Auto Launch on、Silent Start on、IPv6 off、Unified Delay on。
12. `utm-6`：在 guest 内通过终端验证公共出口 IPv4 与当前 Feishu 代理 IP 完全一致；成功后设置并检查 `~/.zshrc` 中 Ruby、Flutter、Pub 镜像环境变量和 PATH。出口不一致时不得报告成功。
13. `utm-7`：先用 `scripts/notion_api.py` 校验父页面并实时读取匹配页账号字段，再在目标 UTM guest 的 macOS 系统设置登录 Apple Account；已知电话/SMS 双重认证自动重新读取实时电话尾号/短信链接并在宿主终端取码，Mac Password 提示自动使用固定 `1234`。账号、号码、验证码或挑战异常先执行实时来源重读、页面/账号只读分类和可逆 GUI 恢复；只有 CAPTCHA、锁号、持续零/多当前验证码、所有权冲突或未知外部挑战才发最后故障卡；不修改 Notion 或 UTM 设置。
14. `utm-8`：在 `utm-7` 成功后的同一 UTM guest 中读取 Apple Account Name/Birthday，并通过字段级 Notion API 更新 `用户名：`、`生日：`；核对当前账号、两处新密码、相同圆点数和已启用的唯一最终控件。Apple 因复杂度拒绝时按拒绝类别最多自动生成三组互不重复的新候选，每次完整自检后自动提交；三次策略拒绝、限流、账号锁定或未知挑战才发最后故障卡。接受后只通过 API 更新 `修改后的密码：`，不覆盖 `初始密码：`。
15. `utm-9`：先用 `scripts/notion_api.py read-field --copy` 读取 `邮箱：`，再只通过 SSH 执行 `open -a "Keychain Access"`，之后使用 Computer Use。用菜单键盘导航确认并高亮 `Certificate Assistant` -> `Request a Certificate From a Certificate Authority...` 后按确认键；在证书信息页保持 Common Name 当前值、CA 邮箱为空、选择 Saved to disk、不要勾选密钥对信息；邮箱输入框必须右键并确认 `Paste` 高亮后粘贴；保存位置必须是 guest Desktop。完成页显示证书请求已创建并存储到磁盘后才算成功。
16. `utm-10`：继续使用同一 guest Microsoft Edge 会话，打开 Apple Developer Small Business 页面并确认账号页；需要登录或短信验证时只用 `scripts/notion_api.py` 读取当前字段，不得启动新浏览器进程。
17. `utm-11`：先在同一 guest Edge 的 App Store Connect Business 自动确认最新 Paid Applications Agreement 已接受，未接受则核对账号/协议后自动接受；再进入 Small Business enrollment，第一道协议问题选 `Yes, I have accepted.`，后续四题全部选 `No`，确认声明后自动提交。成功页稳定后保存、校验当前 run 的 `05-small-business.png`；未知协议/安全状态先回到账号/页面锚点独立重读三轮，仍属外部 schema/安全异常才发最后故障卡；已存在成功页只恢复截图、不重复提交。
18. `utm-12`：继续使用同一 guest Edge，自动处理协议、读取 Membership details，并通过 Notion API 更新/回读 Team ID 和 Renewal date；随后注册 App ID、创建 App Store Connect iOS App，并验证 `iOS App Version 1.0`。
19. `utm-13`：继续使用同一 guest Edge，切回 `Certificates, Identifiers & Profiles`，创建/导入 Apple Distribution 证书，进入 Profiles 选择 App Store Connect、App ID 和 Distribution 证书，通过 Notion API 读取 `应用名: ` 后粘贴生成 Provisioning Profile，并验证 Download and Install 页面。
20. `utm-14`：继续使用同一 guest Edge，进入已有 App Store Connect 的 `Business` 页面；按页面条件处理 DSA 合规、Paid Apps Agreement、U.S. Tax Questionnaire（两题 `No`，分别 `Next`/`Save`）和两份税务表。受益所有人证明表与 W-8BEN 各自完成账号、字段、声明和唯一按钮自检后，都自动点击一次最终 `Submit`，每次提交后验证返回 Business；未知安全、来源歧义或提交结果不明先回到表单锚点、重读权威来源并只读核对同一提交 attempt，恢复穷尽后才发最后故障卡。最后处理 `Directive on Administrative Cooperation - 7th Amendment`，选择 `No` 并验证保存。
21. `utm-15`：确认 `utm-14` 已完成且 `DAC7_INFO=No_saved` 后，继续使用同一 guest Edge，从 Business 进入 `Apps`，从详情 URL 读取数字 App ID，并用字段级 Notion API 只更新 `APP_ID：`、写后回读验证；不点击 `Add Apps`，不新增 `app_id:`。
22. `utm-16`：接着 `utm-15`，先执行 `scripts/notion_api.py verify-parent`，再运行 `python3 -m scripts.utm_16_generate_env --parent-title '<宿主机名称>' --page-title '<应用名>-<vm_name>'`。生成器复用同一 Notion API 客户端，只发 GET 请求读取唯一 `账号信息`/`应用信息` code block，校验精确标签后生成固定文件 `${SUBMISSION_SHARED_DIR}/.env`；字段值不进入 JSON/命令参数，也不打印。脚本把受支持的 `应用类型：` 展示值转换为 `PRIMARY_CATEGORY` 枚举，也接受已规范化枚举；未知分类先重新验证父页/页面/字段三轮，仍不在固定映射内才作为外部权威配置缺失发最后故障卡。不展示完整 `.env`、不等待用户确认。验证权限和 SHA-256，直接继承 `utm-15` 的当前 VM/IP/SSH 身份并做一次轻量身份检查后，从 guest 共享挂载 SSH `cp` 到 `/Users/<vm_name>/Downloads/Fire_One_en1.2/.env`，设置权限 `600`，再用新 SSH 连接核验宿主、共享源和 guest 目标哈希完全一致，最后 SSH `cat` 完整文件做第二重自动核对；不转发 `cat` 中的联系人信息，不运行发布命令。
23. `utm-17`：接着 `utm-16`，通过 `scripts/notion_api.py` 唯一读取非空的 `研发金币图链接：` 和 `金币表格: `，禁止回退 `截图链接: `；字段异常先重新验证父页并有界重读同一页面，仍是权威数据缺失才发最后故障卡。在同一 guest 已有浏览器进程中为每条无协议链接新开 tab 并下载，再通过 SSH 校验精确文件名及其与 `Fire_One_en1.2` 同级。
24. `utm-18`：接着 `utm-17`，从宿主 Terminal 通过分开的 BatchMode SSH 命令关闭 guest Microsoft Edge、以 `9222` CDP 和 `/tmp/edge-debug-profile` 后台重启；每条 Edge 命令检查报错并等待至少 5 秒。必要登录完整复用 `utm-10` 的 Notion API-only 路径；确认 `developer.apple.com/account/` 已登录后，不打开 guest Terminal，改用一个前台 SSH 调用通过 `/bin/zsh -lic` 加载 guest 登录/交互环境；先核对 SSH 身份、`Fire_One_en1.2`、Node/npm 路径和版本，以及 `.env` 的固定 `CDP_ENDPOINT`，再执行唯一业务命令 `npm run fill:description`。远端 `tee` 将 stdout/stderr 完整实时回传并写入每次新建、权限 `600` 的唯一日志；用 zsh `pipestatus` 分别保存 npm/tee 退出码，并以 `.status` 持久化 `RUN_STATE`。结束后通过新只读 SSH 完整 `cat` 日志并核对权限、字节数、SHA-256、`REMOTE_NPM_EXIT=0`、`REMOTE_TEE_EXIT=0` 和两条固定成功原文。`SSH_EXIT=255` 时先自动恢复同一 VM 的连接，再只检查本轮日志/状态/进程，绝不自动重跑业务命令。SSH/IP/Remote Login/公钥恢复不索取用户信息；自动恢复仍失败时记录 `SSH_AUTO_RECOVERY=blocked` 并发送 `utm-18-ssh-auto-recovery` 三按钮故障卡。任何 `manual_continue` 或 `retry_skill` 都先只读判定本轮业务状态，状态不唯一时不得重复运行非幂等业务命令；已查清的业务失败同样向原 `chat_id` 发新故障卡。不得显示 `.env`/敏感值、修改项目或运行发布/提审命令。
25. `utm-19`：接着 `utm-18`，通过 `scripts/notion_api.py` 唯一读取 `截图链接: `，只删除字符串最前面的 `https://` 或 `http://` 协议头，`://` 后所有字符逐字完整保留，再在同一 guest Edge 新 tab 下载 ZIP。用宿主 SSH 校验 ZIP 成员并解压到 `/Users/<vm_name>/Downloads` 的新目录，统计唯一上传集合为 `N` 张 JPEG，不得预设数量。进入 App Store Connect 匹配应用后，点击 `View All Sizes in Media Manager`，选择 `6.9" Display` 并点击其 `Choose File`；在文件选择器先点第一张建立列表焦点，再打开 `Edit`，每次一个 `Down` 并重读，直到 `Select All` 本身蓝色高亮才按 `Return`。确认全部 `N` 张同时选中和 `N items` 后只点一次 `Open`；只有 `N` 张完整缩略图和与 SSH 统计一致的 `N of 10 Screenshots` 稳定显示才成功。禁止坐标直点或未高亮确认 `Select All`、逐张上传、覆盖 Downloads 文件，以及点击 `Save`/`Add for Review`。
26. `utm-20`：保持同一 VM/Edge/银行现场，商务内容空白才写、完全一致幂等继续、冲突时先三轮 API/页面复核且不覆盖。银行号码只从同一 Notion 页读取；为空时在 5/10 秒后连同首次共三轮重读，三轮仍为空才发 `utm-20-bank-info-missing` 最后故障卡。条款、唯一一次 `Add` 和 2FA 全自动，最终必须确认 `United States`、`USD`、`Processing`。
27. `utm-21`：通过安全入口从本机 `.env` 读取 Codeup 凭据并经 SSH stdin 内存通道克隆。已有目标先对账 origin/HEAD/diff：同一 pristine 或同 run 部分现场自动恢复，外部冲突才发最后卡。四项占位符零命中时先查最终值和真实声明位置，不能安全映射才发卡。随后完成 Git 跟踪文本替换、干净环境 `flutter pub get`、精确 `ios` 的 `pod install` 与全量复验；不提交、推送或发布。
28. `utm-22`：为 Xcode GUI Archive 持久化稳定 attempt，误点回到 Runner workspace 重做；Organizer 只选元数据和时间窗唯一匹配的新 Archive。API `distribute` 要求 mode-600 attempt 文件，创建前先查询同版本/构建号，结果不明只恢复同一 `BUILD_UPLOAD_ID` 并有界轮询，禁止第二上传。唯一 Game Center 分支构建号加一并通过 GUI 新 Archive。
29. `utm-23`：完整终态直接移交，明确初始态进入正常路径，部分准备建立固定状态账本并恢复到第一个未完成步骤；只有多草稿/归属冲突/不可逆歧义经三轮独立只读复核后才发最后卡。最终保存两图、核对唯一草稿和两个空区域，记录 `SUBMIT_FOR_REVIEW=not_clicked` 并立即移交。
30. `utm-24`：验证五图、版本/构建、14 个 IAP 和 `Items Ready to Submit (15)` 后调用 `record-auto-review-approval` 写入完整 `automatic_self_check` 授权；现场不变时自动点击一次 `Submit for Review`，不发提审确认卡、不等待回复。结果不明只读轮询同一 attempt，禁止第二次点击；明确成功后幂等完成加急并移交。
31. `utm-25`：最终技能，继承同一 run、VM/IP/SSH 和 guest Edge。新标签打开 App Store Connect `Team Keys`；0/多 Active 与 P8 归属都必须独立重读三轮，仍不唯一才发最后故障卡，绝不按 `NAME`、第一条或“最新”猜测。Notion API 写入失败自动用 before 恢复并独立验证 `NOTION_ROLLBACK=verified`。只有新内容完整回读为 `NOTION_REFUND_CALLBACK_P8=verified` 后才进入稳定 UUID 成功通知状态机，用户可见成功卡最多一张。

如果 guest 三码与模板或已拒绝克隆重复，先暂停后续业务步骤，用 SSH 在 guest macOS 内正常关机，再只对当前 run 的目标克隆执行 `utm-clone-macos` 重建；自动重建仍不能得到唯一身份时发送当前技能三按钮故障卡。SSH 修复必须锁定同一精确 VM 并全自动执行，用户不提供任何信息；后续技能只继承 `SSH_KEY_AUTH=verified` 并轻量检查。后续技能自身的恢复边界优先，但不得把 SSH 配置转交用户。`utm-18` 的 `SSH_EXIT=255` 会自动恢复连接并只读核查同一轮状态，但不得因此自动重跑非幂等业务命令。SSH 自动恢复仍失败时记录 `SSH_AUTO_RECOVERY=blocked`、发送当前技能三按钮故障卡并等待回调，不能自行结束执行器。`vm-down` 禁止使用 `utmctl stop`，`utm-3` 和 `utm-4` 不使用系统设置 GUI。

## 跨机器迁移与启动

1. 把整个项目目录复制到新机器；不要复制 `runtime/` 运行历史、`.env`、已有技能副本或 VM clone。固定 UTM 模板/VM 是独立资产，复制到新机后用 `SUBMISSION_VM_IMAGES_DIR`、`SUBMISSION_VM_TEMPLATE` 指向实际位置。
2. 在新机器项目根目录执行 `cp .env.example .env`，填写该机器自己的 Feishu/Notion/Codeup 凭据和唯一 `SUBMISSION_HOST_MACHINE`。路径项留空会按当前项目位置与 `$HOME` 自动推导；不得复制旧机器绝对路径或宿主机身份。
3. 先执行只读项目预检：

   ```bash
   python3 scripts/preflight.py --project-only
   ```

4. 安装 31 个技能发现链接和一个非技能 `_shared` 恢复合同链接并复核；安装器先验证全部源，再把旧目标移入安全临时备份，全部链接成功才清除备份，失败会自动回滚：

   ```bash
   zsh scripts/install_project_skills.sh --install
   zsh scripts/install_project_skills.sh --check
   ```

5. UTM 模板、共享目录、SSH 目录和全部凭据就位后执行完整预检。输出只包含布尔状态，不输出任何凭据：

   ```bash
   python3 scripts/preflight.py --json
   ```

6. 所有项为 `true` 后启动：

```bash
python3 -u services/feishu_supervisor.py
```

健康检查：

```bash
curl http://127.0.0.1:8787/health
```

默认使用飞书 SDK 长连接接收消息和卡片回调，不需要公网回调地址、Cloudflare 隧道或内网穿透。故障卡片必须使用 JSON 2.0，并通过按钮的 `behaviors` callback object 回传；不要改回 JSON 1.0 的 `action` 容器，否则卡片会走旧版回调，长连接无法接收。

## 必填配置

在 `.env` 填入：

```env
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_VERIFICATION_TOKEN=
SUBMISSION_HOST_MACHINE=<本机宿主机名称>
NOTION_TOKEN=
NOTION_ROOT_PAGE_ID=
NOTION_TEMPLATE_TITLE=模板
CODEUP_USERNAME=
CODEUP_PASSWORD=
SUBMISSION_RUNNER_COMMAND=python3 services/submission_runner.py
```

可选：

```env
FEISHU_ALLOWED_CHAT_ID=
FEISHU_POLL_CHAT_IDS=  # 填与允许问答相同的非日报群 chat_id，补偿长连接漏收
OPENAI_API_KEY=
FEISHU_ASSISTANT_PROVIDER=codex
FEISHU_CODEX_COMMAND=codex
FEISHU_CODEX_MODEL=gpt-5.6-sol
```

问答机器人同时使用飞书长连接与历史轮询；两条通道按 `message_id` 原子去重，只会回复一次。日报专用群不得配置为问答轮询目标。

每台机器人必须设置唯一的 `SUBMISSION_HOST_MACHINE`。只有完整固定飞书登记中的 `使用的宿主机` 与该值精确一致时，本机才会创建 run、生成 `vm_name`、回复并启动流程；不一致或配置为空时静默忽略，普通 Codex 对话不受限制。故障卡、通用用户确认卡和超时卡都显示所属宿主机；所有交互卡回调只有在 run 宿主机与本机配置精确一致时才会执行。其他宿主机配置见 [飞书机器人宿主机设置说明](docs/feishu-host-routing.md)。

## 飞书登记格式

```text
@机器人

使用的宿主机：<宿主机名称>
应用名：<应用名称>
代理信息：<IP>:<端口>:<代理用户名>:<代理密码>
代码链接：<代码仓库链接>

开发者账号信息：
<国家>
<Apple ID 邮箱>
<Apple ID 初始密码>
<手机号> <短信接收链接>

银行信息（可选，可整体省略）：
ABA Routing Number：<ABA 路由号码，可留空>
Account Number：<银行账户号码，可留空>
```

银行区块可省略，两项银行号码也可留空；这不会阻止创建 run。若到 `utm-20` 时仍为空，流程在立即、5 秒、10 秒三轮重新验证父页并读取两项；三轮仍为空才发最后故障卡提示补充，卡片回复后仍以同一 Notion 页实时重读为准。

标准配置会自动执行生成的流程；`SUBMISSION_RUNNER_COMMAND` 必须保持：

```env
SUBMISSION_RUNNER_COMMAND=python3 services/submission_runner.py
```
