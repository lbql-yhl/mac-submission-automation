# UTM Feishu Bot 部署与运行

Bot 负责 Feishu 消息、日报、普通 assistant 对话和已有 run 的状态/卡片能力。Feishu 数据只通过 Bot/OpenAPI 访问，不读 Feishu 桌面客户端、浏览器 DOM 或剪贴板。

## 当前功能边界

Feishu 支持两类精确项目群命令：带明确技能清单的结构化提审，以及批量创建空闲虚拟机。旧版完整登记消息和 `/提审 开始` 仍然禁用，不创建 run、VM、prompt 或后台 runner。

结构化提审必须使用以下格式；技能可从当前允许的主线技能中选择一个或多个，并保持主线相对顺序：

```text
@机器人 /提审 FallLine
执行技能
utm-notion
utm-clash-ip
utm-login
```

同一宿主同时只允许一个未结束的应用提审。检查与登记在同一原子锁内完成；已有应用运行时，新应用不会发送开始卡或启动 runner。`utm-21`、`utm-22`、`utm-23`、`utm-24` 暂不允许从 Feishu 启动。

批量创建虚拟机使用精确命令：

```text
@机器人 /创建虚拟机 5台
```

数量必须为 1 到 10 的 ASCII 整数。Bot 确认开始卡送达后，在独立后台进程中按数量串行直接调用现有 `utm-vm-clone` 公开入口；每次只接受技能自身唯一的 `UTM_CLONE_AND_INITIALIZE=verified;VM_NAME=<四位小写名称>` 结果，并将本批次全部新建名称写入结束卡。全部创建成功后，结束卡复用只读库存查询显示当前可用 VM 总数，不列出现有 VM 名称，也不把库存查询作为创建前门禁或差分复验。任何一次失败都会停止余下任务，并在结束卡显示安全故障码；完整可用 VM 名单仍通过 `/提审 可用VM` 查询。

## Feishu Open Platform 配置

1. 创建当前宿主专用的自建应用并启用 Bot。
2. 从开放平台取得当前应用的 App ID/App Secret，只写入本机 `.env`。
3. 申请并发布以下最小权限：

   - `im:message:send_as_bot`
   - `im:message.group_at_msg:readonly`
   - `im:message.p2p_msg:readonly`
   - `im:message:readonly`
   - `im:resource`
   - `bitable:app`
   - `drive:drive:readonly`
   - `wiki:wiki:readonly`

4. 订阅事件 `im.message.receive_v1` 和卡片动作 `card.action.trigger`。
5. 将 Bot 添加到当前宿主明确授权的会话。Bot 应用、会话路由、Feishu Base/Wiki 与 Notion 根页必须都属于同一宿主配置，不按“最新”或模糊名称路由。

## 23 个 `FEISHU_*` 宿主键

值只能存在当前宿主的 `.env`。完整 47 键清单、必需性与互斥路由见 [配置参考](configuration.md)。

| 键名 | 来源 | 用途 |
|---|---|---|
| `FEISHU_APP_ID` | Feishu Open Platform 自建应用 | Bot/OpenAPI 应用身份 |
| `FEISHU_APP_SECRET` | Feishu Open Platform 自建应用 | 换取 tenant access token |
| `FEISHU_VERIFICATION_TOKEN` | Feishu 事件订阅 | URL verification 检查和 WS 事件分发器 |
| `FEISHU_ENCRYPT_KEY` | Feishu 事件订阅 | WS 事件安全参数和 HTTP 原始请求签名校验开关 |
| `FEISHU_DAILY_REPORT_CHAT_ID` | 旧版独立日报会话 | 可空的 deny-only 兼容键；不参与日报发送，同项目群值会归一化为空 |
| `FEISHU_BOT_HOST` | 本机服务网络配置 | HTTP/health 监听地址 |
| `FEISHU_BOT_PORT` | 本机服务网络配置 | HTTP/health 监听端口 |
| `FEISHU_SEND_RETRIES` | 当前宿主运维策略 | OpenAPI 发送的有界重试次数 |
| `FEISHU_SEND_TIMEOUT_SECONDS` | 当前宿主运维策略 | 单次 OpenAPI 发送超时 |
| `FEISHU_VERIFY_DELIVERY` | 当前宿主运维策略 | 是否通过 OpenAPI 回读验证送达 |
| `FEISHU_ALLOWED_CHAT_ID` | 当前宿主管理的项目群 | 生命周期卡片、确定性查询、普通回复、轮询和用户确认日报的统一精确路由 |
| `FEISHU_POLL_INTERVAL_SECONDS` | 当前宿主运维策略 | 轮询间隔 |
| `FEISHU_WS_ENABLED` | 部署策略 | 启用推荐的 WebSocket 长连接 |
| `FEISHU_TUNNEL_ENABLED` | 部署策略 | HTTP 模式下启用 tunnel |
| `FEISHU_PUBLIC_HEALTH_CHECK` | 部署策略 | 是否允许 supervisor 探测公网 health URL |
| `FEISHU_ASSISTANT_PROVIDER` | assistant 策略 | 选择普通对话 provider |
| `FEISHU_ASSISTANT_ENABLED` | assistant 策略 | 启用或禁用普通 assistant 回复 |
| `FEISHU_ASSISTANT_REQUIRE_MENTION` | 群聊策略 | 群聊中仅在 @bot 时回复 |
| `FEISHU_ASSISTANT_MAX_OUTPUT_TOKENS` | assistant 策略 | 限制单次回复长度 |
| `FEISHU_CODEX_COMMAND` | 当前宿主 PATH | 从 PATH 解析 Codex CLI，不使用他人绝对路径 |
| `FEISHU_CODEX_MODEL` | assistant 策略 | Codex provider 的模型名 |
| `FEISHU_CODEX_TIMEOUT_SECONDS` | 当前宿主运维策略 | 单次 Codex 调用超时 |

## 传输模式：二选一

### WebSocket 长连接（推荐）

WebSocket 不需要公网 callback URL，降低了入站暴露面。在 `.env` 启用 `FEISHU_WS_ENABLED`，关闭 `FEISHU_TUNNEL_ENABLED`，然后启动：

```bash
python3 -u services/feishu_supervisor.py
curl --fail http://127.0.0.1:8787/health
```

WebSocket 启动要求 `lark-oapi`，并使用 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_VERIFICATION_TOKEN` 与 `FEISHU_ENCRYPT_KEY` 创建事件分发器。

### HTTP callback

只有在宿主已有 TLS 公网入口和来源认证策略时才选用 HTTP。在 Feishu 开放平台配置的唯一回调路径是：

```text
https://<public-host>/feishu/events
```

禁止将本地端口直接裸露到公网。可使用自管理反向代理，或在经过安全评审后启用 supervisor 的 tunnel 选项。本地 health 端点仍为 `/health`。

## HTTP 回调安全边界

当前 HTTP handler 的实际边界如下：

- `FEISHU_ENCRYPT_KEY` 非空时，handler 对原始 POST body 与 `x-lark-request-timestamp`、`x-lark-request-nonce`、`x-lark-signature` 执行签名比较。
- URL verification 请求在 `FEISHU_VERIFICATION_TOKEN` 非空时比较 token。普通明文事件不会再独立比较该 token。
- 当前 HTTP handler **不解密**带 `encrypt` 字段的回调，会返回 `encrypted_callbacks_not_enabled`。不得将“配置 Encrypt Key”误当成已支持加密 payload。
- 如果因 Feishu 配置而无法同时得到可验签的明文事件，不得绕过验签。改用推荐的 WebSocket，或先在受信网关实现完整的来源认证、时间窗/重放防护、请求大小与速率限制，再转发到本地 handler。
- TLS 只保护传输，不等于 Feishu 来源认证。在上述边界未满足时，不得对公网开放 HTTP 回调。

## 宿主统一路由与旧配置兼容

- 每台宿主在自己的 `.env` 中配置唯一宿主身份、Feishu 应用、Notion 根页和 Feishu Base/Wiki 路由。
- `FEISHU_ALLOWED_CHAT_ID` 是生命周期卡片、资源查询、普通回复、轮询和用户确认日报的唯一精确项目群路由，不按群名、“最新”或第一个会话选择。该值缺失时，轮询拒绝启动。run 必须同时匹配该项目群和 `SUBMISSION_HOST_MACHINE`；不得使用其他宿主的 VM 绑定、凭据、页面或运行历史。
- `FEISHU_DAILY_REPORT_CHAT_ID` 是可空的旧配置兼容键，日报发送不会读取或使用它。若旧值与项目群相同，Bot 配置将其归一化为空，避免把项目群误判为 report-only；若旧值不同，只保留为 deny-only 路由兼容，不会成为发送目标。

## 项目群生命周期与查询

前台执行器在首次技能副作用之前调用 `run-start`，且只有开始卡返回消息 ID 并确认送达后才能继续。每次实际技能尝试依次记录 `skill-start`，独立复验成功时记录 `skill-success`，失败时先记录 `skill-failure`。只有自动诊断、实际修复和独立复验恢复穷尽后，才允许 `notify-fault` 后接 `wait-decision`；请求范围尾端或终止失败/停止后调用一次 `run-finish`。

卡片只显示必要的脱敏运行事实：

- 开始卡：应用、宿主、开始时间。
- 结束卡：应用、宿主、结果、实际执行技能、`流程故障次数`、耗时；无按钮。
- 最后故障卡：严格只有故障技能、技能故障步骤、应用、宿主四项事实。
- VM 批次开始卡：执行技能、计划数量、宿主。
- VM 批次结束卡：结果、完成数量、本批次全部已验证的新建 VM 名称、成功后的当前可用 VM 总数、失败时的安全故障码、总耗时；当前可用 VM 只显示数量，不列出现有 VM 名称；无按钮。

最后故障卡严格保留三个动作：停止；人工处理完成后继续（继续前重新核验现场）；重试失败技能（重新核验已完成检查点，只跳过仍然通过的步骤）。卡片和查询回复不得包含 run/chat ID、路径、凭据、原始登记数据或诊断原文。

Bot 会先去除 Feishu `<at ...>` 或普通 `@Bot` mention，再在普通 assistant fallback 之前确定性处理以下项目群查询：

- `正在提审的应用` 或 `/提审 应用列表`
- `可用的虚拟机` 或 `/提审 可用VM`
- `/提审 资源`

查询只在 `FEISHU_ALLOWED_CHAT_ID` 精确匹配时响应。活动应用必须属于当前精确宿主，具有 `lifecycle.started_at` 且没有 `lifecycle.finished_at`；VM 清单只读本地 SQLite 并使用分配器的精确可认领条件。运行登记或 VM 数据缺失、不安全、损坏或不兼容时返回 `查询失败`，不得伪装成空列表。

只有上述结构化 `/提审 <应用名>` 加技能清单格式可以创建新 run；完整登记消息与 `/提审 开始` 仍然禁用。项目资源查询不会创建 run 或 VM。

## 用户确认日报

日报只接受用户为本次报告明确提供的业务行。系统仅生成 `Asia/Shanghai` 当天日期以及固定的 `日期：`、`今天提审准备：`、`查审情况：` 标题；空 payload 不得构建或发送。系统不得推断 `无`、应用名、审核状态或天数，空分区保持空白。

日报只能投递到 `FEISHU_ALLOWED_CHAT_ID` 指定的同一项目群，并要求用户确认精确预览及其摘要。`FEISHU_DAILY_REPORT_CHAT_ID` 的任何 legacy 值都不得改变发送目标。VM inventory 扫描结果只允许留在本地，不能调用或复用日报投递入口。

## 真实验收边界

真实卡片验收只通过 Feishu OpenAPI 发送到 `FEISHU_ALLOWED_CHAT_ID` 指定的精确项目群。开始、结束和故障验收都必须取得返回的 message ID 并完成送达验证；终端只输出脱敏验证标记，不输出 message/chat ID、配置值或 API 原文。回调语义使用隔离的测试 run registry 验证，不修改真实提审记录。

本文只描述 Bot 配置、路由和共享生命周期边界。各技能的具体动作、恢复检查点与交接仍只以项目内对应 `skills/<name>/SKILL.md` 为准，不在本文重复 runbook。

## Health 与无敏排障

先从宿主本地检查：

```bash
curl --fail http://127.0.0.1:8787/health
```

排障只记录键名和非敏状态：

1. health 失败：检查 supervisor/Bot 进程是否运行、监听端口是否冲突，不粘贴 `.env` 或 runtime 文件。
2. WS 不收事件：检查应用已发布、Bot 已加入授权会话、权限/事件名存在，只报告“已配置/缺失”。
3. HTTP 返回 `invalid_signature`：核对开放平台与本机的签名配置来源，不打印 header、body 或 key。
4. HTTP 返回 `encrypted_callbacks_not_enabled`：当前 handler 不支持加密 body，不关闭安全校验强行继续；转用 WS 或完成受信网关适配。
5. 发送失败：只核对所需 scope、Bot 成员关系、目标是否为授权会话和非敏 HTTP 错误类型，不输出 chat ID 或 API 响应原文。
6. Base/Wiki 读取失败：检查 Wiki URL 或 Base 三元组二选一、不混用，只报告缺失键名。

禁止把 token、secret、key、chat ID、Base/Wiki/Notion ID、回调 URL、消息原文、runtime 记录或主机路径粘贴到 issue、聊天、日志或卡片。

## 主线技能范围

下列名称仅用于确认 Bot 交接范围，操作真值仍是各自 `SKILL.md`：

→ utm-vm-clone
→ utm-notion
→ utm-clash-ip
→ utm-login
→ utm-edit
→ utm-key
→ utm-apps
→ utm-business
→ utm-env
→ utm-script
→ utm-image
→ utm-p8
→ utm-21
→ utm-22
→ utm-23
→ utm-24
