---
name: notion-utm
description: Use when the user asks to create a UTM Notion registration page from the Notion template by API and fill 账号信息 from Feishu bot registration data. Leave 应用信息 blank for notion-utm-1.
---

# notion-utm

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
  --stage 'notion-utm:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'notion-utm' \
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
| Feishu run/API 暂时不可读 | 锁定同一 `run_id`，按 2/5/10 秒重读三次；核对登记模板字段，不转向最新消息 | 三轮仍不可读才 `exhausted` |
| 目标页已存在或创建中断 | 只读比较页面标题、run/`vm_name`、`账号信息` 哈希；完全一致即幂等完成，当前 run 明确拥有的空/部分页从第一个缺项续写并回读 | 所有权不明或非空冲突为 `unrepairable` |
| Notion 写入/回读失败 | 保留 before，重新读取一次；部分写入时只修复缺项，回读仍不一致则自动还原 before 并再次回读 | 还原后仍不能得到唯一状态才发卡 |
| 权威登记字段缺失 | 重读同一 run 三次并输出缺失标签名，不从对话、记忆或其他 run 猜值 | 仍缺失是外部数据故障，`--unrepairable` |

## Overview

Use the project Feishu bot runtime/API plus `scripts/notion_api.py`. The same current Feishu submission run already contains the deduplicated `虚拟机名称` / `vm_name` and `宿主机名称`. `虚拟机集合` is the workflow homepage; its direct children are host-machine pages. `NOTION_ROOT_PAGE_ID` must point directly to the current run's exact `<宿主机名称>` page, never to `虚拟机集合`. Create `<应用名>-<虚拟机名称>` from that page's unique `模板` child and fill `账号信息` only. Leave `应用信息` blank for `notion-utm-1`.

## Inputs

- `应用名`: from the current Feishu submission run.
- `虚拟机名称`: from the Feishu submission run `vm_name`, generated before any UTM clone.
- `宿主机名称`: from the same current Feishu submission run; never substitute another host page or a remembered value.
- Registration values: from the same current Feishu submission run; never select a latest, old, or different run.
- `.env`: `NOTION_TOKEN`, `NOTION_ROOT_PAGE_ID`, and optional `NOTION_TEMPLATE_TITLE` (default `模板`). The connection needs read, update, and insert-content access to that parent page.

Registration data must come from the project Feishu bot runtime/API. Do not use the Feishu desktop app as a data source. Do not touch the Feishu desktop app. The bank section is optional during initial registration: 银行区块可省略，两项银行号码也可留空. Missing `ABA Routing Number：` or `Account Number：` must not trigger a fault card or block this skill; keep both labels in `账号信息` and write any absent value as blank. If any other canonical Feishu field is missing or empty, do not edit Notion or invent data: lock the same `run_id`, reload its runtime/API record at 2/5/10 seconds, revalidate the complete fixed template and host ownership, and only after all three reads prove the authoritative value absent mark `notion-utm-submission-data` unrepairable and use the last global fault-card exit. Other fields intentionally populated by later workflow steps—`用户名：`, `修改后的密码：`, `生日：`, `team ID:`, `APP_ID：`, and `Renewal date：`—also remain blank during initial registration.

## Notion Page Hierarchy

```text
虚拟机集合（流程主页）
└── <宿主机名称>（当前 Feishu run 对应的宿主机页）
    ├── 模板
    └── <应用名>-<vm_name>（虚拟机登记页）
```

- 宿主机名称只使用同一当前飞书登记中的精确值，不按“最新”、历史记录或本机记忆切换。
- `虚拟机集合` 只用于说明流程层级；不得把它当作登记写入根页。
- `NOTION_ROOT_PAGE_ID` 必须直接指向当前 `<宿主机名称>` 页面，并在每次 Notion 操作前通过 `verify-parent --title '<宿主机名称>'`。

## Canonical Feishu Submission Template

Future user submissions use this exact template; do not use the old shortened format:

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

Omitting the entire bank section and leaving either or both bank values empty are equivalent. `format_account_block` must still emit the fixed blank `ABA Routing Number：` and `Account Number：` lines for later Notion completion.

The parser also accepts the same account fields when they are written with labels (`国家：`, `邮箱：`, `初始密码：`, `电话：`, `短信接收链接：`) or when the SMS URL token itself contains `@`; it must still normalize them into the same 33-line `账号信息` block and must not treat the SMS URL line as the Apple ID email.

For an explicit user-requested test run with supplied or generated test data, still use the project parser/formatter (`services.feishu_bot.parse_submission_data`, `scripts.notion_utm_prepare.format_account_block`, and `validate_account_block`) to produce the same 33-line `账号信息` block. Create a uniquely named template copy through the API, write and read it back exactly, then move only that test page to Notion trash. Re-read the page and record `TEST_PAGE_IN_TRASH=verified` only when `in_trash=true`; the test page remains recoverable. Do not use the Feishu desktop app or a browser write path.

## Workflow

The Feishu bot-created `run_id`, original `chat_id`, `vm_name`, app name, and host-page title are mandatory immutable context, not optional values. Re-read only that exact run when a transient runtime/API read fails. Recovery-exhausted fault stages are: missing/invalid run data = `notion-utm-submission-data`; `verify-parent` mismatch = `notion-utm-parent`; missing/duplicate `模板` child = `notion-utm-template`; conflicting existing section = `notion-utm-account-conflict`; API write/readback mismatch = `notion-utm-readback`. After the matching matrix is exhausted and recovery evidence is complete, this skill owns the corresponding last card and wait itself; 不得静默结束.

1. Read the same current Feishu submission run and require exactly one non-empty `应用名`, `虚拟机名称`, and `宿主机名称`; do not select a latest, old, or different run. Empty or absent initial bank data is valid and must remain blank in the generated account block.
2. Verify that the configured API parent is exactly that run's `<宿主机名称>` page:

```bash
python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
```

3. Generate and validate the fixed 33-line account block without copying it to the clipboard:

```bash
account_file="$(mktemp "${TMPDIR:-/tmp}/notion-utm-account.XXXXXX")"
chmod 600 "$account_file"
python3 scripts/notion_utm_prepare.py \
  --run-id '<current-run-id>' \
  --vm-name '<虚拟机名称>' \
  --out "$account_file"
```

4. Require the generated mode-600 `$account_file` to report `lines=33`, then independently call `validate_account_block` against its bytes. Immediately before the Notion mutation, rerun `verify-parent`; only then create or resume the unique registration page from the unique `模板` child and write `账号信息`:

```text
<应用名>-<虚拟机名称>
```

```bash
python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
python3 scripts/notion_api.py create-registration \
  --title '<应用名>-<虚拟机名称>' \
  --account-file "$account_file"
```

5. The API layer must re-read `账号信息` after the update and require exact equality. Before this independent read, rerun `verify-parent`, then read to a second mode-600 file and compare byte-for-byte without printing values:

   ```bash
   account_after="$(mktemp "${TMPDIR:-/tmp}/notion-utm-after.XXXXXX")"
   chmod 600 "$account_after"
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   python3 scripts/notion_api.py read-section \
     --title '<应用名>-<虚拟机名称>' --heading '账号信息' \
     --out "$account_after"
   cmp -s "$account_file" "$account_after"
   ```

6. Before the next read, rerun `verify-parent`; read `应用信息` into its own mode-600 file and require every byte to be whitespace. Do not fill it in this skill:

   ```bash
   application_after="$(mktemp "${TMPDIR:-/tmp}/notion-utm-application.XXXXXX")"
   chmod 600 "$application_after"
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   python3 scripts/notion_api.py read-section \
     --title '<应用名>-<虚拟机名称>' --heading '应用信息' \
     --out "$application_after"
   python3 - "$application_after" <<'PY'
   from pathlib import Path
   import sys
   value = Path(sys.argv[1]).read_text(encoding="utf-8")
   if value.strip():
       raise SystemExit("APPLICATION_INFO=nonblank")
   print("APPLICATION_INFO=blank")
   PY
   ```

   Delete `account_file`, `account_after` and `application_after` only after both independent checks pass, then use `test ! -e` on all three paths. On failure, retain them only inside the current fault recovery attempt and remove them before final `stop`/timeout.
7. If the exact page title already exists, reuse only that page. The API layer may accept identical content. A current-run page that was created but only partially filled is resumed and independently re-read; creation is not falsely described as rolled back to non-existence. A conflicting non-empty section enters `notion-utm-account-conflict`; never create a second page, delete the page, or move it to trash to bypass the conflict.

## Completion State

Record completion only after all API checks pass:

```text
PARENT_PAGE=verified
PARENT_TITLE=<宿主机名称>
ACCOUNT_INFO=33_lines_exact
APPLICATION_INFO=blank
NOTION_UTM=verified
```

## 账号信息 Template

```text
用户名：

邮箱：

初始密码：

修改后的密码：

电话：

电话短信接收平台：

生日：

team ID:

APP_ID：

Renewal date：

代理ip:

代理端口:

代理用户名：

代理用户密码：

代码链接：

ABA Routing Number：

Account Number：
```

Rules:

- Preserve this exact template spacing: there is one blank line between each field line.
- `电话：` must start with `+1`.
- `生日：` format is `年/月/日`.
- Use the single `APP_ID：` field for the app ID.
- Split proxy into IP only, port only, username only, and password only.
- If `ABA Routing Number：` or `Account Number：` exists in the same Feishu submission run, copy it without exposing it in logs or reports; otherwise preserve the label with a blank value for `utm-20` to read later from Notion.
- `修改后的密码：` stays blank until the changed password is known.

## API Write Safety

- `scripts/notion_api.py` must find the registration page, headings, fields, and code blocks by exact unique match. Zero or multiple matches first reload the same host configuration, repeat exact API lookup three times, reconcile only the same run-owned page, and independently reverify through the matching recovery matrix; only an exhausted or proven external ownership conflict enters the last global fault-card stage.
- The code block must be immediately after its heading. Do not search by coordinates or write through Chrome.
- Rich text is split into Notion's 2,000-character chunks while preserving the original text byte-for-byte.
- A code block containing only whitespace is treated as the blank template. Any other non-empty conflicting section is not overwritten unless the calling skill explicitly allows replacement.
- Every write is followed by an API re-read and exact equality check. Command output contains only IDs, byte/line counts, and SHA-256; it must not print the account block.

## Guardrails

- Get registration data only from the project Feishu bot runtime/API; the Feishu bot is the workflow's information provider and trigger.
- Use the `vm_name` generated by the Feishu run. Do not wait for UTM cloning to create a VM name.
- Use only the official Notion API through `scripts/notion_api.py`; do not open or write Notion through Chrome, a plugin, Playwright, CUA, or clipboard paste.
- Treat `虚拟机集合` only as the process homepage. Never create a registration page directly under it.
- Do not edit the original template.
- Do not delete or move Notion pages.
- Do not overwrite unrelated saved content.
- If `verify-parent` does not match `宿主机名称`, pause all Notion mutation, reload the current host `.env`, same run host title and root-page metadata, then repeat read-only `verify-parent` at 2/5/10 seconds. Only a persistent external page/ownership conflict after `notion-utm-parent` recovery exhaustion may use the last global fault-card exit.

## 连续交接

仅当本技能全部完成检查通过时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `notion-utm-1`；不得等待用户确认。阻断、失败或未完成状态不得交接。
