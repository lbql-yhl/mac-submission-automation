# UTM-17：下载研发金币图和金币表格

## 定位

`utm-17` 接在 `utm-16` 后：通过 `scripts/notion_api.py` 从匹配页只读取唯一非空的 `研发金币图链接：` 和 `金币表格: `，回到同一 UTM guest 的已有浏览器进程，为每条链接新开一个 tab 后依次下载。禁止回退 `截图链接: ` 或其他字段。字段为空、缺失、重复或非 URL 时先重新 `verify-parent` 并按 2/5/10 秒三轮读取同一精确页面；仍缺失才作为外部权威数据故障发最后故障卡。链接只移除开头协议，不修改 Notion、不启动新浏览器进程、不用命令行下载。

SSH 继承 `utm-16` 已验证的同一 VM/IP/用户和宿主公钥，全部连接使用 `BatchMode=yes`。连接失效时仅对同一精确 VM 自动刷新 IP、修复 Remote Login 和恢复宿主公钥；不向用户索取密码、SSH Key、IP，也不等待 SSH 人工处理。

## 操作步骤

1. 在项目根目录执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`；失败时重载当前项目配置并对同一父页执行 2/5/10 秒三轮只读复验，不改选页面。
2. 对 `<应用名>-<vm_name>` 的 `应用信息` 使用 `read-field --copy`，只读唯一非空的 `研发金币图链接：` 和 `金币表格: `。禁止读取 `截图链接: ` 兜底；任一字段异常时按同一三轮重新验证父页并读取两个字段。三轮仍异常才记录恢复证据并向当前 run 原 `chat_id` 发送最后故障卡；继续决定也重跑三轮，回复本身不是字段证据。
3. 每条链接都在即将处理时重新 `read-field --copy`，随后调用 `OP-BROWSER-URL-NO-SCHEME`：执行 `pbpaste | python3 scripts/shared_operations.py browser-url`。只接受 `BROWSER_URL_CLIPBOARD=verified`；执行器只删除最前面的一个 `http(s)://`，逐字节保留 `//` 后全部 host/path/query/token，且不输出链接值。
4. 回到 `utm-16` 使用的同一 UTM guest、同一已有浏览器进程；每条链接新开一个 tab，只用蓝色高亮的 `Paste and Go` 导航，绝不补协议。每个动作后等待至少 3 秒并重读，导航后立即清空剪贴板。
5. 在研发金币图页面点击明确的图片下载控件；在金币表格页面点击明确的 `下载`/`Download`/`Export` 控件。每次下载后检查浏览器下载列表/提示或 guest `Downloads` 文件夹，确认新文件出现。
6. 完成第一条后通过 API 重新读取第二条链接并重新核对剪贴板，不复用旧链接状态。
7. 新建带 `-o BatchMode=yes -o ConnectTimeout=5` 的 SSH 连接，核对用户为 `<vm_name>`、`$HOME` 为 `/Users/<vm_name>`，再检查本轮两个下载文件的名称、扩展名、大小、时间和 SHA-256。
8. 最终名称必须严格为 `/Users/<vm_name>/Downloads/<应用名>.png` 和 `/Users/<vm_name>/Downloads/<应用名>.xlsx`，应用名大小写以 Notion 页面为准。
9. 文件名已精确正确时不修改；只有来源唯一、名称错误且目标名不存在时，才通过 SSH `/bin/mv` 重命名。目标名冲突或有多个候选时重新读取下载记录、时间窗、大小和 SHA-256 三轮；仍不能唯一归属才发最后故障卡，禁止覆盖、删除或自动加序号。
10. 若发生重命名，验证前后 SHA-256 一致；再用新的 SSH 连接复核两个精确文件名、大小和 SHA-256。
11. 使用命令确认 `Fire_One_en1.2` 是目录，并确认它与 `<应用名>.png`、`<应用名>.xlsx` 都是 `/Users/<vm_name>/Downloads/` 的同一级直接子项。

同级检查命令：

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

## 完成标准

```text
UTM_16=verified
NOTION_SOURCE=api_unique_matched_and_read
COIN_IMAGE_LINK=verified
COIN_IMAGE_DOWNLOAD=verified
COIN_TABLE_LINK=verified
COIN_TABLE_DOWNLOAD=verified
DOWNLOADS=verified
COIN_IMAGE_FILENAME=exact
COIN_TABLE_FILENAME=exact
DOWNLOAD_FILENAMES=verified
FIRE_ONE_SAME_LEVEL=verified
SSH_KEY_AUTH=verified
UTM_17=verified
```

全部完成标记均有当前证据后，立即继续 `utm-18`；不得等待用户确认。

## 风险点

- 页面标题、guest 或浏览器会话不匹配时回到继承锚点并重新核对三轮；仍不匹配才发最后故障卡。
- `研发金币图链接：` 或 `金币表格: ` 异常时三轮重读同一权威页面，恢复穷尽后才发卡；不猜、不改读其他字段。
- 粘贴值不得含 `http://` 或 `https://`，但不得丢失 host、路径、query 或 token。
- 不启动新浏览器进程，不改 Notion，不用 `curl`、`wget` 或 SSH 下载；每条链接都必须在已有浏览器进程的新 tab 中处理。
- 登录/权限/验证码未知时先完成三轮只读分类；已知登录恢复自动执行，CAPTCHA/账号锁定在三轮复核后才作为外部不可修复状态发最后故障卡。下载控件或结果不明确时回到下载锚点并核对下载记录与 SSH 三轮。
- SSH 用户/家目录或公钥不匹配时自动恢复同一精确 VM 三轮；下载来源不唯一、目标名冲突或哈希不一致时只读对账三轮。恢复穷尽后才发卡。
- `Fire_One_en1.2` 或同级关系不成立时重新核对同一 Downloads 三轮；仍不成立才发最后故障卡，不创建或移动目录。
- 已正确的 `<应用名>.png` 或 `<应用名>.xlsx` 不得重复修改；SSH 只用于核对和必要的重命名，不用于下载。
