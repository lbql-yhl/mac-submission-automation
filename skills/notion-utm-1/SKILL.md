---
name: notion-utm-1
description: "Use when an existing UTM Notion page needs 应用信息 written by Notion API for a target 应用名 from the Feishu 金鳞产品表格 view."
---

# Notion UTM 1

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
  --stage 'notion-utm-1:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'notion-utm-1' \
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
| 飞书表格读取失败 | 对同一 wiki/table/view/app 做 5/15/30 秒 GET 重试；每轮重新取 token 并做一次 GET/POST 精确查询，重新去重并验证唯一行 | 三轮后仍无唯一结果才 `exhausted` |
| 可见表格上下文与 API 结果矛盾 | 可见证据只用于核对文档/view/记录上下文；重新解析固定 wiki/table/view/app 并执行同一 API 查询，禁止抄取可见字段值 | 确认配置不一致时记录 `FEISHU_TABLE_CONTEXT_MISMATCH=verified`，停止 Notion 写入并先修复项目技能或脚本 |
| Notion 现有内容冲突 | 重新读取同一唯一飞书行，重建完整区块，保存 before 后一次 `--replace-existing`，独立回读；失败则还原 before | 自动覆盖/还原仍不能闭环才发卡 |
| URL/类别格式异常 | 重新获取原始单元格，做固定规范化并复验，不自行补 URL 或猜类别 | 同一权威行仍为空/非法为 `unrepairable` |
| 瞬时 API 限流/网络 | 遵守 `Retry-After`，同一请求最多三轮，不创建第二页面 | 恢复耗尽才发卡 |

## Purpose

After `notion-utm` creates the UTM Notion page, fetch the target `应用名` from the Feishu Bitable app `26财年巨风做包表`, view `金鳞产品表格`, by API only. Build the fixed `应用信息` template, verify it, then write it through `scripts/notion_api.py` to the existing matching page under `应用信息`.

## Required Inputs

- `notion-utm` has recorded `NOTION_UTM=verified` for this same current run and page.
- Target application name from the same current Feishu submission run.
- Current VM name, used to confirm the matching Notion page title `应用名-虚拟机名称`.
- Local `.env` with `FEISHU_APP_ID` and `FEISHU_APP_SECRET`.
- Local `.env` with `NOTION_TOKEN` and `NOTION_ROOT_PAGE_ID` pointing directly to the current host-machine page.
- Feishu Bitable identifiers:
  - Wiki node title: `26财年巨风做包表`
  - View name: `金鳞产品表格`
  - `FEISHU_PACKAGE_WIKI_NODE_TOKEN=BvyIww0GIi1EankyFiCcZyJyn9Y`
  - `FEISHU_PACKAGE_TABLE_ID=tblywCNVLJlTcOH9`
  - `FEISHU_PACKAGE_VIEW_ID=vewKUW4q4W`

## Hard Rules

- Read the `金鳞产品表格` view in `26财年巨风做包表` by Feishu API only. Do not click, filter, open, scrape, or edit the Feishu web table. If API results contradict user-visible evidence from an already open Feishu table, use that evidence only to confirm the visible document/view/record context and then re-query the API against the matching fixed wiki/table/view; never copy field values from the web table.
- Use the Wiki node API to resolve the real bitable `app_token`, then use bitable `records/search` with `应用名` exact match.
- The current project data contract guarantees one matching row. Still verify that the API result is exactly one row; any unexpected zero-row or multiple-row result is a defensive Feishu data fault and must use the fault-card recovery below. Never select the first, latest, or any other row as a fallback.
- Do not edit Feishu data.
- Do not invent missing values. `金币表格`, the exact same-named `研发金币图链接`, and source field `美女截图链接-UI` (written as `截图链接`) are required. Any 空值或不包含有效完整的 `http://` 或 `https://` URL is a Feishu data fault and must use the same fault-card recovery below; never write the invalid value to Notion.
- The current project data contract guarantees that `应用类型` is covered by the category map below. Normalize and self-check it automatically; do not create a user-confirmation or data-repair branch for category selection.
- Before writing to Notion, use `verify-parent` for the current `宿主机名称` and require the exact page title `应用名-虚拟机名称` to resolve once.
- Only write under the Notion `应用信息` section unless the user explicitly asks otherwise.
- Use only `scripts/notion_api.py` for Notion reads and writes. Do not open or write Notion through Chrome, a plugin, Playwright, CUA, or browser clipboard APIs.
- The API must find the unique `应用信息` heading and the immediately following code block. If that block contains different existing content, first 重新实时读取同一应用的唯一飞书记录, regenerate and fully verify the template, then 自动覆盖现有 `应用信息` with `--replace-existing` and re-read exact persistence. This conflict recovery is automatic: 无需用户确认，也不发送故障卡.

## Feishu API Read

1. Get `tenant_access_token` with `FEISHU_APP_ID` and `FEISHU_APP_SECRET`.
2. Resolve the Wiki node:

```text
GET /open-apis/wiki/v2/spaces/get_node?token=<wiki_node_token>&obj_type=wiki
```

3. Confirm `data.node.obj_type` is `bitable`.
4. Use `data.node.obj_token` as the bitable `app_token`.
5. Search only the `金鳞产品表格` view (`view_id=vewKUW4q4W`):

```text
POST /open-apis/bitable/v1/apps/<app_token>/tables/<table_id>/records/search
```

with:

```json
{
  "view_id": "<view_id>",
  "page_size": 20,
  "filter": {
    "conjunction": "and",
    "conditions": [
      { "field_name": "应用名", "operator": "is", "value": ["<应用名>"] }
    ]
  }
}
```

6. Continue only if exactly one item is returned. If the result count is `0` or greater than `1`, enter the automatic recovery below; do not send a card yet.

## Feishu Data Fault Recovery

1. Inherit the current run's exact `run_id` and original `chat_id`. Never send these cards to the daily-report-only group.
2. Classify the current fault without exposing row data or protected field values:
   - `0` exact-match rows: stage `notion-utm-1 应用记录`, fault `没有找到该应用记录`, evidence `FEISHU_MATCH_COUNT=0`.
   - More than `1` exact-match row: stage `notion-utm-1 应用记录`, fault `该应用存在多条记录，无法唯一确定`, evidence `FEISHU_MATCH_COUNT=<实际条数>`; never select the first, latest, or any other row.
   - The unique row's `金币表格` is blank: stage `notion-utm-1 金币表格`, fault `金币表格为空`, evidence `COIN_TABLE_URL=blank`.
   - The unique row's `金币表格` does not contain a valid complete HTTP(S) URL: use the same stage, fault `金币表格 URL 无效`, evidence `COIN_TABLE_URL=invalid`.
   - The unique row's exact same-named `研发金币图链接` is blank: stage `notion-utm-1 研发金币图链接`, fault `研发金币图链接为空`, evidence `RND_COIN_IMAGE_URL=blank`.
   - The unique row's exact same-named `研发金币图链接` does not contain a valid complete HTTP(S) URL: use the same stage, fault `研发金币图链接 URL 无效`, evidence `RND_COIN_IMAGE_URL=invalid`.
   - The unique row's `美女截图链接-UI` (target `截图链接`) is blank: stage `notion-utm-1 截图链接`, fault `截图链接为空`, evidence `SCREENSHOT_URL=blank`.
   - The unique row's `美女截图链接-UI` does not contain a valid complete HTTP(S) URL: use the same stage, fault `截图链接 URL 无效`, evidence `SCREENSHOT_URL=invalid`.
3. 先自动恢复：重新取得 Feishu tenant token，重新核对固定 app/table/view identity，并在 5/15/30 秒各重新执行一次相同精确过滤；每轮都重新验证返回条数、目标字段名和 URL 语法，禁止使用旧响应、其他 view、第一条或最新一条。若用户已提供截图、浏览器调试上下文或已经打开的飞书表格证明“页面可见有值但 API 读空”，只能把该证据用于只读核对当前打开的是不是 `26财年巨风做包表` / `金鳞产品表格` / 目标应用行所在上下文；字段正文、URL、账号或 token 仍必须来自同一固定表/view 的 API 重新查询。发现 API 配置与可见上下文不一致时，记录 `FEISHU_TABLE_CONTEXT_MISMATCH=verified`，停止写 Notion，并把修复沉淀回本技能或对应脚本后再继续。任一轮得到唯一完整行即记录 `DATA_RECOVERY=verified` 并继续。
4. 三轮仍为零/多行、字段空白或 URL 无效时，这些值只能由外部权威表格补齐，记录 `AUTO_RECOVERY_ATTEMPTS=3`、具体 `AUTO_RECOVERY_ACTIONS`、`AUTO_RECOVERY_RESULT=unrepairable`；此时才使用文件开头的统一 `notify-fault` 命令向原 `chat_id` 发送最后故障卡并等待 fresh decision。不得发送到日报群。
5. 收到卡片反馈后由当前等待中的执行上下文立即处理，不需要人工再次触发：
   - `stop`：原故障卡更新为已停止，立即停止整个流程并结束当前 run，不再发送独立停止通知。
   - `manual_continue`：立即重新读取同一应用的 Feishu API 精确匹配结果，复核人工修正后的现场并从阻断点继续。
   - `retry_skill`：立即重跑当前技能 `notion-utm-1`，继承同一 run、应用名和页面，只跳过已验证成功的步骤；未通过最新完成检查的步骤必须重新执行。
6. If the same or another data fault remains, repeat the three automatic API reads before a new card is allowed; never reuse an old decision. A transient card-send/callback fault preserves the same run and retries the same stable card UUID. If the delivered card receives no reply for 3600 seconds, the bot sends the no-button timeout card, records `decision_timeout_stop`, and stops the whole workflow without writing or handoff; stale or ambiguous callbacks never resume it.

## Template Mapping

Fill this exact template:

```text
应用名: 
团队: 
顶级域名: 
正式包名: 
正式域名:
隐私协议: 
用户协议: 
支持链接: 
code:
金币表格: 
应用类型：
应用描述：
关键词: 
研发金币图链接：
截图链接: 
```

Field mapping:

- `应用名` <- Feishu `应用名`
- `团队` <- Feishu `团队`
- `顶级域名` <- Feishu `顶级域名`
- `正式包名` <- Feishu `正式包名`
- `正式域名` <- Feishu `正式域名(app/h5/im/log)`
- `隐私协议` <- Feishu `隐私协议`
- `用户协议` <- Feishu `用户协议`
- `支持链接` <- Feishu `支持协议`; if blank, copy Feishu `隐私协议`.
- `code` <- Feishu `code`
- `金币表格` <- Feishu `金币表格`
- `研发金币图链接` <- Feishu `研发金币图链接`
- `应用类型` <- Feishu `应用类型`, normalized by the category map below.
- `应用描述` <- Feishu `应用描述`
- `关键词` <- Feishu `关键词`
- `截图链接` <- Feishu `美女截图链接-UI`

Preserve source text, punctuation, spacing, line breaks, and trailing text such as `复制链接到浏览器打开` when it is part of the field value.

Feishu `金币表格`, exact same-named `研发金币图链接`, and `美女截图链接-UI` are mandatory URL sources. If any one is blank or its URL is invalid, immediately begin **Feishu Data Fault Recovery** (three fresh reads and unique-key validation, not a card) and do not generate or write the Notion template until a fresh query returns exactly one row with all three valid URLs. Only exhausted external-data absence uses the last fault card. Do not substitute `研发截图`, `金币截图`, `截图链接`, or another similarly named source field for `研发金币图链接`.

## Category Map

`应用类型` must be an App Store Connect category code:

- 报刊杂志 -> `MAGAZINES_AND_NEWSPAPERS`
- 财务 -> `FINANCE`
- 参考资料 -> `REFERENCE`
- 导航 -> `NAVIGATION`
- 工具 -> `UTILITIES`
- 购物 -> `SHOPPING`
- 健康健美 -> `HEALTH_AND_FITNESS`
- 教育 -> `EDUCATION`
- 旅游 -> `TRAVEL`
- 美食佳饮 -> `FOOD_AND_DRINK`
- 软件开发工具 -> `DEVELOPER_TOOLS`
- 商务 -> `BUSINESS`
- 社交 -> `SOCIAL_NETWORKING`
- 摄影与录像 -> `PHOTO_AND_VIDEO`
- 生活 -> `LIFESTYLE`
- 体育 -> `SPORTS`
- 天气 -> `WEATHER`
- 贴纸 -> `STICKERS`
- 图书 -> `BOOKS`
- 图形和设计 -> `GRAPHICS_AND_DESIGN`
- 图形与设计 -> `GRAPHICS_AND_DESIGN`
- 效率 -> `PRODUCTIVITY`
- 新闻 -> `NEWS`
- 医疗 -> `MEDICAL`
- 音乐 -> `MUSIC`
- 游戏 -> `GAMES`
- 娱乐 -> `ENTERTAINMENT`

If the Feishu value contains `中文-英文展示名`, normalize from the Chinese part. Example: `图形与设计-Graphics & Design` -> `GRAPHICS_AND_DESIGN`.

The current project guarantees that the Feishu value belongs to this map. Perform normalization and the code-membership self-check automatically; there is no user-confirmation or fault-card branch for choosing an application type.

## Self-Verify Template

Before the Notion API write, verify:

- Exactly one Feishu row matched the target `应用名`.
- The API query used the `金鳞产品表格` view ID `vewKUW4q4W`.
- `支持链接` equals `隐私协议` when `支持协议` is blank.
- `应用类型` is one of the category codes above, not an English display name such as `Graphics & Design`.
- `金币表格`, `研发金币图链接`, and `截图链接` must each be a non-empty full URL; read `研发金币图链接` only from the exact same-named Feishu field, not from an attachment or another similarly named field.
- `应用名`, `支持链接`, `研发金币图链接`, and `截图链接` each appear exactly once in the final template.
- The final template line count and character count are known before copying.

## Save To Notion

1. 创建三个随机 mode-600 临时文件；`desired_file` 只保存本轮从唯一飞书行生成并通过全部字段检查的目标内容，`before_file` 保存写入前快照，`after_file` 保存独立回读。不得把内容打印到终端：

   ```bash
   desired_file="$(mktemp "${TMPDIR:-/tmp}/notion-utm-1-desired.XXXXXX")"
   before_file="$(mktemp "${TMPDIR:-/tmp}/notion-utm-1-before.XXXXXX")"
   after_file="$(mktemp "${TMPDIR:-/tmp}/notion-utm-1-after.XXXXXX")"
   chmod 600 "$desired_file" "$before_file" "$after_file"
   ```

2. 将已验证模板原样写入 `desired_file`，然后用 `wc -l`、`wc -c` 和 `shasum -a 256` 记录非敏感计数/哈希；再次解析该文件并要求 15 个标签各出现一次，三个 URL 可由 `urllib.parse.urlsplit` 解析为 `http|https` 且有非空 host，类别值属于固定枚举。
3. 每一次 Notion 操作前都重新验证当前宿主机父页。先读写前快照：

   ```bash
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   python3 scripts/notion_api.py read-section \
     --title '<应用名>-<虚拟机名称>' \
     --heading '应用信息' \
     --out "$before_file"
   ```

4. 比较 `before_file` 与 `desired_file`，不输出正文：
   - If it is empty or already byte-for-byte equal to the intended template, continue directly.
   - If it is non-empty and different, 重新实时读取同一应用的唯一飞书记录 through the same view and exact-match query, require exactly one row, re-run every URL/category/template check, and regenerate the temporary template. Then 自动覆盖现有 `应用信息`; this is deterministic refresh, so 无需用户确认，也不发送故障卡. If the fresh Feishu query itself finds a data fault, use **Feishu Data Fault Recovery**.
5. 仅当新生成的 `desired_file` 再次通过验证后，重新执行 `verify-parent`，再写唯一 `应用信息` code block：

   ```bash
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   python3 scripts/notion_api.py write-section \
     --title '<应用名>-<虚拟机名称>' \
     --heading '应用信息' \
     --file "$desired_file" \
     --replace-existing
   ```

6. API output must report `changed=true` or idempotent `changed=false`. 等待 API 返回后，再次 `verify-parent` 并独立回读；只有 `cmp` 成功才可通过：

   ```bash
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   python3 scripts/notion_api.py read-section \
     --title '<应用名>-<虚拟机名称>' \
     --heading '应用信息' \
     --out "$after_file"
   cmp -s "$desired_file" "$after_file"
   ```

7. 若写入返回失败或 `cmp` 不等，先停掉新的写入；再次 `verify-parent` 和 `read-section` 判定服务端是否其实已经等于 `desired_file`。若仍不等，且 `before_file` 是本次写入前的唯一完整快照，则执行以下唯一 rollback；还原状态不唯一时不得继续写：

   ```bash
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   python3 scripts/notion_api.py write-section \
     --title '<应用名>-<虚拟机名称>' --heading '应用信息' \
     --file "$before_file" --replace-existing
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   python3 scripts/notion_api.py read-section \
     --title '<应用名>-<虚拟机名称>' --heading '应用信息' \
     --out "$after_file"
   cmp -s "$before_file" "$after_file"
   ```

   只有最后 `cmp` 成功才记录 `NOTION_ROLLBACK=verified`。
8. 成功时记录 `APPLICATION_INFO_READBACK=exact`，删除三个临时文件并用 `test ! -e` 逐个确认。失败恢复期间只保留到当前 attempt 结束；`stop` 或超时前也必须删除。Do not modify `账号信息` or any other section.

## Completion Checklist

- Feishu `金鳞产品表格` view was read by API only.
- No Feishu web table click, filter, scrape, edit, or row detail operation was used.
- Any user-visible table evidence was used only to verify document/view/record context; no field value was copied from it, and no unresolved `FEISHU_TABLE_CONTEXT_MISMATCH` remains.
- Exactly one target row matched.
- No Feishu data fault is pending; any unexpected `0`/multiple-row result or blank/invalid `金币表格`, `研发金币图链接`, or `截图链接` URL was resolved by the bounded 5/15/30-second live rereads or, after a delivered last-card decision, by a new successful exact API query.
- The fixed template was generated with the category-code normalization.
- The current host parent and exact registration page were uniquely matched by API.
- Any conflicting existing `应用信息` was refreshed from the same unique Feishu record, automatically overwritten, and re-read exactly through `scripts/notion_api.py`.
- `APPLICATION_INFO_READBACK=exact` is recorded from the independent byte-for-byte readback.
- Temporary files were mode `600` and removed after comparison.
- 验证全部通过后，记录 `NOTION_UTM_1=verified`，立即继续 `utm-clone-macos`；不得等待用户确认。阻断、失败或未完成状态不得交接。
