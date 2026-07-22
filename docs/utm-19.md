# UTM-19：下载截图包并上传 6.9" 截图

SSH 直接继承 `utm-18` 已验证的同一 VM/IP/用户和宿主公钥，全部连接固定使用 `BatchMode=yes`。连接失效时仅对同一精确 VM 自动刷新 IP、修复 Remote Login 和恢复宿主公钥；不得向用户索取密码、SSH Key、IP 或等待 SSH 人工处理。

## 操作步骤

1. 接着 `utm-18`，继续使用同一台 `started` VM、同一 `vm_name`、同一 SSH 身份和同一已登录 guest Microsoft Edge；不要求 guest Terminal 存在。
2. 在项目根目录执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，再执行 `python3 scripts/notion_api.py read-field --title '<应用名>-<vm_name>' --heading '应用信息' --label '截图链接: ' --copy`。要求父页面、页面、heading、code block 和字段唯一且值非空；不得用宿主浏览器或插件读取 Notion。随后调用 `OP-BROWSER-URL-NO-SCHEME`，执行 `pbpaste | python3 scripts/shared_operations.py browser-url`；统一执行器只删除最前面的一个 `https://`/`http://`，逐字节保留 `//` 后全部内容且不展示链接。
3. 只有 `BROWSER_URL_CLIPBOARD=verified` 才在同一 guest Edge 新开 tab，通过原生右键菜单中蓝色高亮的 `Paste and Go` 打开链接；导航后立即清空剪贴板。点击页面唯一下载控件，并在 Edge 下载记录中确认本轮 ZIP 已完成。
4. 通过带 `-o BatchMode=yes -o ConnectTimeout=5` 的宿主 SSH 确认 `/Users/<vm_name>/Downloads` 中唯一对应本轮下载的 ZIP。`unzip -t` 验证 CRC 后，必须用 Python `zipfile.ZipFile`、`PurePosixPath` 和 `ZipInfo.external_attr` 拒绝绝对/点路径、反斜杠、重复路径、加密成员、symlink/特殊文件；只列名称不能证明安全。
5. 仅在目标不存在时按安全成员清单解压到 Downloads 直接子目录；不得删除、清空、合并或覆盖。新 SSH 递归核对所有解压项不越界/非 symlink，并用 `rglob` 统计大小写不敏感 `.jpg/.jpeg` 的普通非空文件；每张前三字节必须为 `FF D8 FF`，真实路径唯一，记录 `JPEG_SET_RECURSIVE=verified`、`JPEG_MAGIC=verified` 和实际 `N`。
6. 返回同一 guest Edge 并新开 tab，调用 `OP-BROWSER-URL-NO-SCHEME` 并执行 `printf '%s' 'appstoreconnect.apple.com/apps' | python3 scripts/shared_operations.py browser-url --allow-bare`；只在 `BROWSER_URL_CLIPBOARD=verified` 且 `Paste and Go` 蓝色高亮后确认一次，随后清空剪贴板。点击与本轮继承的应用名精确且唯一匹配的应用；等待至少 3 秒，确认页头应用名匹配，且详情 URL 中 `/apps/<纯数字 App ID>/` 的 App ID 与本轮继承值完全一致。名称或 URL 任一不符都先回到应用列表锚点重新定位，不得继续上传。
7. 滚动到截图区域，点击右上角 `View All Sizes in Media Manager`。
8. 在 Media Manager 中选择 `6.9" Display`，只允许 `SCREENSHOT_PREUPLOAD_CLASSIFICATION=empty|complete`：`empty` 必须 E=0 且 1≤N≤10，一次上传全部 N；`complete` 必须已有全部 N 张稳定缩略图且显示 `N of 10 Screenshots`，直接跳过。任意部分上传、其他截图、加载/失败项或无法唯一归属都停止新上传并进入恢复，绝不逐项补传。
9. 在原生文件选择器进入 `Downloads` 和本轮解压目录；若只有一层唯一同名目录，继续进入。确认看见与 SSH 数量和文件一致的全部 `N` 张 JPEG。
10. 先点击第一张 JPEG，确认其蓝色高亮且 `Open` 变蓝，以建立文件列表焦点。打开 guest Edge 顶部 `Edit` 菜单，每次只按一次 `Down`，每次等待至少 3 秒并读取新截图：`Undo` → `Redo` → `Select All`。只有 `Select All` 本身蓝色高亮时才按一次 `Return`。
11. 确认本轮待上传集合全部蓝色高亮、右侧数量与待上传数一致、`Open` 为蓝色，再只点击一次 `Open`，并记录稳定上传 attempt。不得直接坐标点击 `Select All`，不得在菜单项未高亮时确认，也不得以重复点击 `Open` 探测结果。误入目录或误选文件时先点 `Cancel`，确认没有上传后从同一入口恢复。
12. 等待处理完成，确认 `6.9" Display` 显示 `N` 张完整缩略图和 `N of 10 Screenshots`；页面数量必须与 SSH 统计一致，且无加载动画或错误。不点击 `Save`、`Add for Review` 或其他提交控件。

## 完成标准

```text
UTM_18=verified
NOTION_PAGE=api_unique_matched
SCREENSHOT_LINK=verified_without_scheme
SCREENSHOT_ARCHIVE_DOWNLOAD=verified
ZIP_MEMBER_SAFETY=verified
SCREENSHOT_ARCHIVE_EXTRACTED=verified
JPEG_SET_RECURSIVE=verified
JPEG_MAGIC=verified
SSH_KEY_AUTH=verified
APP_STORE_CONNECT=verified
APP_NAME=matched
MEDIA_MANAGER=open
IPHONE_69_DISPLAY=selected
SCREENSHOT_PREUPLOAD_CLASSIFICATION=empty|complete
SCREENSHOT_COUNT=verified_N
SCREENSHOT_FILES=all_N_selected
SCREENSHOT_UPLOAD=verified_N_of_10
UTM_19=verified
```

记录 `UTM_19=verified`，结束 `utm-19`，保留当前 VM、guest Edge 和 Media Manager 页面，立即继续 `utm-20`；不得等待用户确认。

## 风险点

- 每个 GUI 操作后等待至少 3 秒并重新读取画面；目标、焦点或蓝色高亮未确认时不得继续。
- 下载记录和 SSH 文件必须唯一对应；ZIP 损坏、路径不安全、目标已存在、解压结果含符号链接、图片数量或尺寸不符时，先按本技能自动恢复矩阵诊断、修复和复验，恢复穷尽后才允许发最后故障卡。
- App Store Connect 未登录、应用/App ID 不唯一、`Select All` 未蓝色高亮、待上传集合未同时选中，或最终 `N of 10 Screenshots` 与 SSH 统计不一致时，先回滚到最近验证锚点并只读分类；无法安全恢复后才发最后故障卡。
- 不启动或重启浏览器，不要求或操作 guest Terminal，不泄露链接/token/账号信息，不删除或覆盖 Downloads 内容，不执行保存、送审或发布动作。
