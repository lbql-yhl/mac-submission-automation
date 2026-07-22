---
name: utm-17
description: Use when the matching UTM macOS guest, after utm-16, must download the development coin image and coin spreadsheet from links stored on its matching Notion page.
---

# UTM-17：下载研发金币图和金币表格

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
  --stage 'utm-17:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-17' \
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
| 链接/API 瞬态失败 | 同一字段按 2/5/10 秒重读，不使用截图链接回退 | 仍为空/非法为 `unrepairable` |
| 新标签/下载控件误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图；关闭仅本轮错误 tab 或 `Back` 到链接页，重新定位，记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立定位后仍无唯一控件才发卡 |
| 下载未完成 | 只读等待 5/10/20 秒并核对 Edge 记录/SSH 文件；证明未开始才点一次下载 | 结果仍不明不重复下载 |
| 文件名冲突 | 以下载记录、时间、类型和哈希对账；当前 run 文件完全一致即幂等完成 | 不同文件/多候选为 `unrepairable` |

## 定位

`utm-17` 接在 `utm-16` 后。它只从匹配的 Notion 页面精确读取 `研发金币图链接` 和 `金币表格`，再回到同一台 UTM guest 的已有浏览器进程，为每条链接新开一个 tab 后依次下载。下载完成后通过 SSH 检查 guest 的 `/Users/<vm_name>/Downloads/`，确保最终文件名严格为 `<应用名>.png` 和 `<应用名>.xlsx`。不得用 `截图链接` 或其他字段替代研发金币图，不得修改 Notion、启动新浏览器进程或用命令行下载。

## SSH 全自动约束

- 直接继承 `utm-16` 的同一精确 VM/IP、`<vm_name>` 和 `SSH_KEY_AUTH=verified`；本技能的每条宿主 SSH 调用都必须带 `-o BatchMode=yes -o ConnectTimeout=5`，不重复配置 SSH。
- SSH 检查失败时自动按同一 VM 的精确 MAC 刷新 IP、检查 Remote Login/端口，并用固定 `1234` 恢复 `${SUBMISSION_SSH_PUBLIC_KEY}`；不得向用户索取密码、SSH Key 或 IP。
- 恢复后重新验证 `id -un` 和 `$HOME`；仍失败时记录 `SSH_AUTO_RECOVERY=blocked`，先按 `utm-17-ssh-auto-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；禁止猜测下载文件或改选 VM。

## 前置条件

- `utm-16=verified`，目标 VM、`vm_name` 和 `<应用名>-<vm_name>` Notion 页面已确定。
- `${PROJECT_ROOT}/.env` 已配置 `NOTION_TOKEN` 与指向当前宿主机页面的 `NOTION_ROOT_PAGE_ID`。
- Notion 只通过项目 `scripts/notion_api.py` 读取；下载只使用同一 guest 中已经打开的浏览器进程和标签页。
- 当前 guest 是 `utm-16` 使用的目标 VM；无法确认 guest、用户或浏览器会话匹配时先按 `utm-17-session-identity` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。

## 硬性规则

- 匹配 Notion 页面的 API 实时值是链接唯一来源；不得用宿主 Chrome、Notion 插件、Playwright、CUA、坐标或浏览器剪贴板读取 Notion，也不从 Feishu 桌面端、旧截图、缓存文本或猜测值取链接。
- 每次切换窗口、点击、右键、粘贴、导航、下载或滚动后等待至少 3 秒，再读取最新截图/状态并重新定位目标。
- 不启动、重启或切换新浏览器进程；必须在同一已打开 guest 浏览器进程中分别新开一个 tab 处理每条链接。
- 粘贴前必须把当前链接写入宿主原生剪贴板，并用 `pbpaste` 逐字节核对；粘贴后必须从最新地址栏/页面状态核对链接未截断，随后立即执行 `pbcopy </dev/null`、确认 `pbpaste` 为空并记录 `LINK_CLIPBOARD=cleared`。
- 浏览器地址栏粘贴值不得带 `http://` 或 `https://`；只移除源值开头的协议，保留 host、path、query、token 和其余字符原样；不要自行补回协议。
- 只点击当前页面明确对应的 `下载`、`Download`、`Export` 或图片下载控件；不点击登录、分享、权限、账单、提交或删除控件。
- 不覆盖或删除已有下载文件；下载结果不明确时先按 `utm-17-download-result` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
- 文件名中的应用名必须与匹配 Notion 页面中的 `<应用名>` 大小写完全一致，目标名固定为 `<应用名>.png`、`<应用名>.xlsx`。
- 重命名前必须通过 SSH 先检查实际文件名、文件类型、时间和目标文件是否存在。文件名已经正确时不执行 `mv`；只有下载来源唯一明确、名称错误且精确目标名不存在时才重命名。
- 只允许用 SSH 在 `/Users/<vm_name>/Downloads/` 内重命名下载文件；不得覆盖同名目标、猜测多个候选文件、移动到其他目录或用 SSH 下载文件。

## 操作步骤

### 一、从匹配 Notion 页面读取两条链接

1. 在 `${PROJECT_ROOT}` 执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`；父页面不匹配时先按 `utm-17-notion-parent` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
2. 在精确标题 `<应用名>-<vm_name>` 的 `应用信息` 中执行以下两条固定命令；每条命令前都重新执行一次 `verify-parent`，不得合并标签、改标点或把值放进 argv：

```bash
python3 scripts/notion_api.py read-field --heading '应用信息' --label '研发金币图链接：' --copy \
  --title '<应用名>-<vm_name>'
python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
python3 scripts/notion_api.py read-field --heading '应用信息' --label '金币表格: ' --copy \
  --title '<应用名>-<vm_name>'
```

页面、heading、紧随其后的 code block 和每个字段都必须唯一。禁止回退读取 `截图链接: ` 或任何近似字段。
3. 命令输出只允许包含 ID、计数和 SHA-256，不得显示链接值。两个最终值都必须非空且是完整 URL。`研发金币图链接：` 为空，或任一字段缺失、重复、截断、非 URL、存在多个候选时，保持 guest 页面不动，立即、2 秒、5 秒、10 秒四轮重新执行 `verify-parent` 与两个 `read-field --copy`，每轮都重新核对父页、子页、heading、code block、唯一标签和 URL 完整性。任一轮取得两个唯一非空完整 URL 即自动继续。四轮后仍缺失/非法才记录 `AUTO_RECOVERY_ATTEMPTS=4`、实际重读动作与 `AUTO_RECOVERY_RESULT=unrepairable`，然后进入 `utm-17-notion-links` 最后故障卡。`manual_continue` 和 `retry_skill` 仍先重跑这四轮权威读取，回复本身不是数据证据。不得用其他字段替代，不得在本技能修改 Notion。
4. 每条 URL 都必须在即将处理时重新执行对应字段的完整 `verify-parent + read-field --heading '应用信息' --label '<精确标签>' --copy`，随后立即调用 `OP-BROWSER-URL-NO-SCHEME`：`pbpaste | python3 scripts/shared_operations.py browser-url`。只接受 `BROWSER_URL_CLIPBOARD=verified`；统一执行器只删除最前面的一个 `https://`/`http://` 并逐字节保留 `//` 后全部内容。不要把两条链接混在一次剪贴板内容中，也不得复用前一字段的剪贴板。

### 二、在同一 guest 浏览器中下载

对“研发金币图链接”和“金币表格”各执行一次以下流程，先完成前者再处理后者：

1. 回到 `utm-16` 使用的同一 UTM guest，确认窗口标题/画面属于目标 VM，且当前浏览器进程是已有会话；Notion 读取阶段不操作任何宿主浏览器。
2. 在该已有浏览器进程中新开一个 tab；等待至少 3 秒并确认新 tab 已成为当前页面，再从最新截图定位地址栏。
3. 继续执行 `OP-BROWSER-URL-NO-SCHEME`：只用当前蓝色高亮的 `Paste and Go` 打开已经核对过的无协议链接，不手动补 `https://`。动作完成后立即清理宿主剪贴板和 shell 变量：

```bash
pbcopy </dev/null
test -z "$(pbpaste)"
unset raw_link paste_link
```

只有空剪贴板复验成功才记录 `LINK_CLIPBOARD=cleared`。
4. 等待至少 3 秒，重新读取地址栏和页面；确认 host、path、query/token 与本轮 Notion 源值的非敏感结构证据一致，且页面不是搜索结果、错误页或无关站点。导航失败或链接被截断时先按 `utm-17-navigation` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
5. 对研发金币图：在当前页面找到明确的图片下载控件，下载原图/文件；若页面只显示图片且没有明确下载控件，先按 `utm-17-image-download-control` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定，不用截图或命令行替代。
6. 对金币表格：在当前页面找到明确的 `下载`、`Download` 或 `Export` 控件，选择保留表格数据的文件格式；不点击无关导出、分享或权限操作。
7. 每次点击下载后等待至少 3 秒，重新读取浏览器下载列表/提示或 guest `Downloads` 文件夹；确认本次出现新的下载文件，记录可见文件名即可，不覆盖已有文件。
8. 完成第一条下载后，通过 `scripts/notion_api.py read-field --copy` 重新读取第二条链接并重新做剪贴板核对；不得复用旧剪贴板或旧地址栏状态，第二条也必须新开一个 tab。

### 三、通过 SSH 核对并规范文件名

1. 使用带 `BatchMode=yes` 的新 SSH 连接登录目标 guest，先核对 `id -un` 为 `<vm_name>`、`$HOME` 为 `/Users/<vm_name>`，默认下载目录为 `/Users/<vm_name>/Downloads/`。
2. 结合浏览器下载列表中记录的可见文件名，通过 SSH 读取对应文件的名称、扩展名、大小、修改时间和 SHA-256；必须能唯一对应本轮图片和表格下载。存在多个候选、扩展名不符或来源不明确时先按 `utm-17-download-candidate` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
3. 最终文件名必须严格为：
   - `/Users/<vm_name>/Downloads/<应用名>.png`
   - `/Users/<vm_name>/Downloads/<应用名>.xlsx`
4. 对每个文件先判断：
   - 精确目标名已经是本次下载文件：保持不动，不执行重命名。
   - 当前下载名错误、来源唯一且精确目标名不存在：使用 SSH `/bin/mv` 改为精确目标名。
   - 精确目标名已存在但不是已确认的本次下载文件：先按 `utm-17-target-name-exists` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；不覆盖、不删除，也不自动加序号。
5. 若执行重命名，必须比较重命名前后的 SHA-256，确认内容未变；随后建立新的 SSH 连接，确认两个精确目标文件都存在、错误旧名称已消失，并重新读取文件名、大小和 SHA-256。
6. 使用命令确认 `/Users/<vm_name>/Downloads/Fire_One_en1.2` 是目录，并确认 `<应用名>.png`、`<应用名>.xlsx` 和 `Fire_One_en1.2` 的父目录都精确等于 `/Users/<vm_name>/Downloads`；三者必须是同一级直接子项，不能只凭路径看起来相近。

同级检查必须实际执行等价命令，不能目测：

```bash
base="$HOME/Downloads"
project="$base/Fire_One_en1.2"
image="$base/<应用名>.png"
sheet="$base/<应用名>.xlsx"
test -d "$project" && test -f "$image" && test -f "$sheet"
test "$(dirname "$project")" = "$base"
test "$(dirname "$image")" = "$base"
test "$(dirname "$sheet")" = "$base"
```

## 完成检查

```text
UTM_16=verified
SSH_KEY_AUTH=verified
NOTION_SOURCE=api_unique_matched_and_read
COIN_IMAGE_LINK=verified
COIN_IMAGE_DOWNLOAD=verified
COIN_TABLE_LINK=verified
COIN_TABLE_DOWNLOAD=verified
LINK_CLIPBOARD=cleared
DOWNLOADS=verified
COIN_IMAGE_FILENAME=exact
COIN_TABLE_FILENAME=exact
DOWNLOAD_FILENAMES=verified
FIRE_ONE_SAME_LEVEL=verified
UTM_17=verified
```

两个下载都必须有当前 guest 浏览器的可见下载证据；不能只凭点击反馈或 URL 打开成功报告完成。
全部完成标记均有当前证据后，立即继续 `utm-18`；不得等待用户确认。阻断、失败或未完成状态不得交接。

## 阻断条件

- `BROWSER_PROCESS_GUARD=blocked`、Notion API 父页面/页面标题不匹配，或目标 guest/浏览器会话无法确认。
- `研发金币图链接：` 或 `金币表格: ` 为空、缺失、重复、非 URL、截断或多候选；按第 3 步的异常故障卡恢复，不得读取 `截图链接: ` 兜底。
- `pbpaste` 与待粘贴的无协议 URL 不完全一致，粘贴值仍含协议，或粘贴后地址栏缺少字符。
- 页面打开为搜索结果、错误页、登录/权限阻断页或无关站点。
- 找不到明确下载控件、下载失败、下载文件未出现、文件名冲突或需要未授权的账号/验证码操作。
- SSH 用户或 `$HOME` 不匹配，下载文件无法唯一对应，扩展名异常，精确目标名冲突，重命名前后 SHA-256 不一致，`Fire_One_en1.2` 不存在，或三个父目录不完全一致。

发生阻断时立即暂停后续副作用，先按对应 `utm-17-*` stage 执行本技能自动恢复矩阵并独立复验；只有恢复穷尽后才发送最后故障卡并等待，同时保留字段、链接打开、下载或文件名核对阶段的非敏感可见证据。不得猜链接、补协议、启动新浏览器、改 Notion，或用 `curl`/`wget`/SSH 代替浏览器下载。
