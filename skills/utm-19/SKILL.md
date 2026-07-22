---
name: utm-19
description: Use after utm-18 when the same UTM macOS guest must continue the matching app's App Store Connect screenshot workflow.
---

# UTM-19：下载截图包并上传 6.9" 截图

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
  --stage 'utm-19:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-19' \
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
| App/Media Manager/选择器误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图；文件选择器用 `Cancel`，页面用 `Back` 回当前数字 App ID 的 Media Manager，再定位 `6.9" Display`；记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立定位后仍不唯一才发卡 |
| ZIP 下载/解压中断 | 只读核对本轮下载和安全成员；当前 run 部分目录用成员清单续解/复验，不删除其他内容 | 所有权不明、路径穿越或多候选为 `unrepairable` |
| 上传前只读分类 | 核对当前数字 App ID、已有截图数量、剩余容量和 N；只允许 `empty` 一次上传全部 N，或 `complete` 幂等完成 | 任意部分上传、失败项或无法唯一对账都停止新上传并发卡 |
| Open 结果不明 | 记录单次 attempt，只读等待缩略图稳定并比较 N；不再次点击 Open | 仍 ambiguous 才发卡 |

## SSH 全自动约束

- 直接继承 `utm-18` 的同一精确 VM/IP、`<vm_name>` 和 `SSH_KEY_AUTH=verified`；所有宿主 SSH 调用统一使用 `-o BatchMode=yes -o ConnectTimeout=5`，不重复配置 SSH。
- SSH 检查失败时自动按同一 VM 的精确 MAC 刷新 IP、检查 Remote Login/端口，并用固定 `1234` 恢复 `${SUBMISSION_SSH_PUBLIC_KEY}`；不得向用户索取密码、SSH Key 或 IP。
- 恢复后重新核对用户/home 和本轮唯一 ZIP；仍失败时记录 `SSH_AUTO_RECOVERY=blocked`，先按 `utm-19-ssh-auto-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；禁止按最新文件或其他 VM 猜测。

## 前置条件

- `utm-18` 已完成，继续使用同一台 `started` VM、同一 `vm_name` 和同一已登录 guest Microsoft Edge。
- 不启动、重启或切换任何浏览器进程；继承 `utm-18` 的同一 VM、SSH 身份和 guest Edge 会话，不要求 guest Terminal 存在。
- `${PROJECT_ROOT}/.env` 已配置当前父页面的 Notion API 访问；Notion 只通过项目 `scripts/notion_api.py` 读取。
- guest 下载目录固定解析为 `/Users/<vm_name>/Downloads`；不得代入旧 run 或示例中的 VM 名称。
- 每个 GUI 操作后等待至少 3 秒，重新读取最新截图/状态；未确认目标页面、控件和高亮不得点击。

## 操作步骤

1. 在 `${PROJECT_ROOT}` 执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，再执行 `python3 scripts/notion_api.py read-field --title '<应用名>-<vm_name>' --heading '应用信息' --label '截图链接: ' --copy`。要求父页面、页面标题、heading、紧随其后的 code block 和字段都唯一，且安全元数据表明值非空；不得用宿主浏览器、Notion 插件、Playwright、CUA、坐标或浏览器剪贴板读取 Notion。
2. 调用 `OP-BROWSER-URL-NO-SCHEME`：把当前剪贴板直接送入 `pbpaste | python3 scripts/shared_operations.py browser-url`，不得打印或持久化 URL。统一执行器只删除字符串最前面的一个 `https://` 或 `http://`，从 `://` 后第一个字符开始逐字节保留全部内容，并只输出字节数/SHA-256。只有 `BROWSER_URL_CLIPBOARD=verified` 才能继续；`Paste and Go` 后从地址栏结构复验并立即清空剪贴板及 URL 变量。
3. 切回同一 UTM guest 的现有 Edge，新开一个 tab。确认地址栏已聚焦后用 guest 原生右键菜单选择已高亮的 `Paste and Go`，打开无协议链接；不得键入链接或启动新浏览器进程。
4. 点击页面上唯一明确的下载控件。等待下载自然完成，并在 Edge 下载记录中确认本轮文件名和“已完成”状态；`.crdownload`、进行中、失败或名称不明确都不算完成。
5. 从宿主通过新的 `BatchMode=yes` 只读 SSH 核对 `id -un=<vm_name>`、`$HOME=/Users/<vm_name>`，再检查 `/Users/<vm_name>/Downloads`。用“开始下载前目录清单 + Edge 本轮下载记录中的文件名 + 下载完成后的文件大小和 ZIP 魔数”唯一关联本轮 ZIP，绝不按“修改时间最新”猜测。第一次不唯一时先刷新同一 Edge 下载记录并重新读取同一目录；仍不唯一时只对本轮开始时间以后、名称与浏览器记录一致的候选执行 `/usr/bin/unzip -t`，由校验结果自动排除未完成或非 ZIP 项。只有完成三轮独立只读诊断仍有多个有效候选时，才把它记为 `AUTO_RECOVERY_RESULT=unrepairable` 并进入最后故障卡。
6. 通过宿主 SSH 先用 `/usr/bin/unzip -t` 校验压缩包，再把已验证的唯一 archive 绝对路径作为位置参数交给 guest `python3` 做安全成员检查。检查必须实际使用 `zipfile.ZipFile`、`PurePosixPath` 和 `ZipInfo.external_attr`，并同时拒绝：空成员名、NUL/反斜杠、绝对路径、任一 `.`/`..` 分量、加密成员、Unicode NFC+casefold 后重复路径、符号链接及其他特殊文件。不得用只列名称的 `zipinfo` 推断链接类型。所有成员通过后记录 `ZIP_MEMBER_SAFETY=verified`。下载未完成或 CRC 校验失败时先在原下载页只重试一次同一资源下载，并用新的 attempt 文件名重新执行第 5 步；不安全或列表不明确时不得解压。
7. 解压目录使用 ZIP 文件名去掉 `.zip` 后的名称，且必须是 `/Users/<vm_name>/Downloads` 的直接子目录。若目标已存在，先只读分类：成员、相对路径、文件类型、大小和 SHA-256 全部与 ZIP 解压清单一致时记为 `already_complete` 并复用；若它带有当前 run/attempt 证据但不完整，则保留原目录并创建带当前稳定 `attempt_id` 的新目录重新完整解压；若所有权不明或内容冲突，不删除、不清空、不合并、不覆盖，经过三轮独立清单复核后才进入最后故障卡。只有选定目标不存在时才执行安全解压；等价实现必须包含以下检查和动作：

   ```python
   import os, stat, unicodedata
   from pathlib import Path, PurePosixPath
   from zipfile import ZipFile

   archive = Path("<SSH 已唯一验证的 ZIP 绝对路径>")
   downloads = Path("/Users/<vm_name>/Downloads").resolve(strict=True)
   dest = downloads / "<ZIP 文件名去掉 .zip>"
   if archive.is_symlink() or not archive.is_file() or archive.parent.resolve() != downloads:
       raise SystemExit("ARCHIVE_IDENTITY_INVALID")
   if dest.exists() or dest.is_symlink() or dest.parent.resolve() != downloads:
       raise SystemExit("DESTINATION_NOT_NEW")

   seen = set()
   with ZipFile(archive) as bundle:
       bad_crc = bundle.testzip()
       if bad_crc is not None:
           raise SystemExit("ZIP_CRC_INVALID")
       for info in bundle.infolist():
           name = info.filename
           path = PurePosixPath(name)
           parts = path.parts
           folded = unicodedata.normalize("NFC", name).casefold()
           mode = (info.external_attr >> 16) & 0xFFFF
           if (not name or "\x00" in name or "\\" in name or path.is_absolute()
                   or not parts or any(part in ("", ".", "..") for part in parts)
                   or info.flag_bits & 0x1 or folded in seen
                   or stat.S_ISLNK(mode)
                   or (mode and not info.is_dir() and not stat.S_ISREG(mode))):
               raise SystemExit("ZIP_MEMBER_UNSAFE")
           seen.add(folded)
       dest.mkdir(mode=0o700)
       bundle.extractall(dest)

   dest_real = dest.resolve(strict=True)
   for item in dest.rglob("*"):
       st = item.lstat()
       if stat.S_ISLNK(st.st_mode) or not (stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode)):
           raise SystemExit("EXTRACTED_MEMBER_UNSAFE")
       if dest_real not in item.resolve(strict=True).parents:
           raise SystemExit("EXTRACTED_PATH_ESCAPE")
   ```

   实际代码通过 SSH heredoc 发送，archive/dest 只作为已校验位置参数传入，不把 ZIP 内容放入 argv。命令失败后保留现场，先读取退出码、目标目录成员和 ZIP 清单；若只是当前 attempt 的部分结果，使用新的稳定 attempt 目录重新完整解压并复验，禁止在部分目录上覆盖续写。只有在新目录解压已证明无覆盖、无越界且可安全重试时，才做满三次独立安全目标修复并逐次复验；文件系统只读、结果归属不明或不能安全新建时则不再写入，改做三轮文件系统/清单独立只读复核。三轮仍失败时，才记录恢复证据并进入最后故障卡。
8. 使用新的 SSH 连接复核解压目录存在、没有符号链接，且目录仍是 `/Users/<vm_name>/Downloads` 的直接子项。递归使用 `dest.rglob("*")` 统计扩展名大小写不敏感为 `.jpg`/`.jpeg` 的普通非符号链接文件；每个文件必须位于 `dest.resolve()` 下、非空、真实路径唯一，且前三个字节满足 JPEG SOI 魔数 `FF D8 FF`。集合必须非空，数量记为实际 `N`，输出只包含 N、相对文件名和 SHA-256，不输出文件内容。全部通过后记录 `JPEG_SET_RECURSIVE=verified` 与 `JPEG_MAGIC=verified`；不要预设数量，不要重命名或移动它们。
9. 返回同一 guest Edge 并新开一个 tab，调用 `OP-BROWSER-URL-NO-SCHEME` 并执行 `printf '%s' 'appstoreconnect.apple.com/apps' | python3 scripts/shared_operations.py browser-url --allow-bare`。只有 `BROWSER_URL_CLIPBOARD=verified` 且地址栏原生菜单的 `Paste and Go` 已蓝色高亮才确认一次；粘贴后立即清空剪贴板。确认 App Store Connect 已登录且 Apps 列表可见。若会话失效，先在同一 Edge 进程按 `utm-10` 的 API-only 凭据读取路径自动恢复登录并重读 Apps；只有 CAPTCHA、账号锁定或无法自动完成的新安全挑战才属于外部不可修复状态，完成三轮独立只读复核后进入最后故障卡。
10. 从继承上下文取得当前数字 App ID，并在 Apps 列表中只点击与本轮 `<应用名>` 精确且唯一匹配的应用。点击后等待至少 3 秒，重新读取页面；成功必须同时满足可见应用名匹配且地址栏路径包含唯一的 `/apps/<当前数字 App ID>/`。若名称正确但 URL 不符，立即停止页面副作用，用 `Back` 返回 Apps 列表，等待至少 3 秒取得最新截图后重新定位；这个可逆恢复完整执行三轮，每轮都回读名称和精确 App ID URL。三轮仍不符才记录 `APP_IDENTITY=unrepairable`，绝不在错误 App 中继续。
11. 在当前应用版本页面向下滚动，每次滚动后等待至少 3 秒并重新截图，直到看见截图区域右上角的 `View All Sizes in Media Manager`；仅在当前 URL 仍含相同数字 App ID 时点击一次该链接。误点或进入错误页面时使用 `Back` 回到刚验证的应用版本锚点，等待至少 3 秒、作废旧坐标并重做当前最小动作，成功后记录 `GUI_RECOVERY=verified`。
12. 等待至少 3 秒并重新读取 Media Manager，确认 URL 仍属于当前数字 App ID。在尺寸列表中只选择 `6.9" Display`，再次等待至少 3 秒确认该区域高亮。执行上传前只读分类并持久化非敏感证据：已有截图数量 `E`、页面显示的最大容量 `10`、剩余容量 `R=10-E`、本轮 JPEG 数 `N`、可见文件名/缩略图状态以及是否存在加载或失败项。
    - `E=0`、`1<=N<=10` 且 `N<=R`：分类为 `empty`，允许一次上传全部 `N` 张。
    - 页面已显示本轮同一 attempt 的全部 `N` 个唯一文件名/稳定缩略图，且计数为 `N of 10 Screenshots`：分类为 `complete`，不得再点 `Choose File`，直接执行第 16 步复核。
    - 页面只存在本轮一部分、存在任何其他截图、已有截图无法与本轮文件唯一对账、存在失败/加载项、`N=0`、`N>R` 或页面计数互相矛盾：分类为冲突，不得再上传或补传。先刷新同一页面并在 5/10/20 秒做三次只读复核；仍不是 `empty` 或 `complete` 时记录外部/不可逆状态并进入最后故障卡。

    分类落盘为固定二选一标记 `SCREENSHOT_PREUPLOAD_CLASSIFICATION=empty|complete`；竖线表示允许值，不是第三种状态。
13. 只有第 12 步分类明确需要上传时，才点击该 `6.9" Display` 区域内唯一的 `Choose File`。等待至少 3 秒并确认 macOS 原生文件选择器已打开；若打开了错误选择器、错误尺寸或页面身份丢失，先点击 `Cancel`，等待至少 3 秒回到 Media Manager，重新验证当前 App ID、`6.9" Display` 和上传前分类，记录 `GUI_RECOVERY=verified` 后再重做，禁止直接沿用旧坐标。
14. 仅 `empty` 分支进入文件选择器：左侧点击 `Downloads`，只进入第 8 步验证的本轮解压目录；沿 SSH 已确认的唯一相对目录进入包含完整 JPEG 集合的位置。必须看见与 SSH 递归清单一致的全部 `N` 张且不含额外可选文件。任何路径、数量或文件名不一致都先 `Cancel` 回滚并重新读取 SSH 清单；不得选择 ZIP、其他 Downloads 内容、非 JPEG 文件或只选缺失子集。
15. 仅 `empty` 分支先点击第一张 JPEG，确认它蓝色高亮且 `Open` 变蓝，以建立正确文件列表焦点。打开 guest Edge 顶部 `Edit` 菜单，然后每次只按一次 `Down`，每次等待至少 3 秒并重新截图；从 `Undo` 经 `Redo` 前进，直到 `Select All` 本身蓝色高亮。只在该高亮状态下按一次 `Return`。重新截图确认全部 `N` 张同时蓝色高亮、右侧显示 `N items` 且 `Open` 为蓝色；任一不符都 `Cancel`，不得逐项上传或用坐标猜选。
16. `empty` 分支在点击前先持久化唯一 `SCREENSHOT_UPLOAD_ATTEMPT_ID`，记录 App ID、尺寸、N、JPEG 清单哈希和 `state=prepared`，然后只点击一次蓝色 `Open`；随后不再重复点击，只在 5/10/20/40 秒读取同一页面。`complete` 分支记录 `SCREENSHOT_UPLOAD_ATTEMPT_ID=not_needed_existing_complete`，不打开选择器。两条成功路径最终都必须由当前页面证明：`6.9" Display` 显示本轮全部 `N` 张可唯一对账的稳定缩略图、无加载或错误，且页面显示 `N of 10 Screenshots`；结果不明时只回查同一 attempt 和页面计数，绝不盲目重传。不点击 `Save`、`Add for Review` 或其他提交控件。

## 完成标准

```text
UTM_18=verified
SSH_KEY_AUTH=verified
NOTION_PAGE=api_unique_matched
SCREENSHOT_LINK=verified_without_scheme
SCREENSHOT_ARCHIVE_DOWNLOAD=verified
SCREENSHOT_ARCHIVE_ZIP=verified
ZIP_MEMBER_SAFETY=verified
SCREENSHOT_ARCHIVE_EXTRACTED=verified
JPEG_SET_RECURSIVE=verified
JPEG_MAGIC=verified
APP_STORE_CONNECT=verified
APP_NAME=matched
APP_IDENTITY=current_numeric_id_verified
MEDIA_MANAGER=open
IPHONE_69_DISPLAY=selected
SCREENSHOT_PREUPLOAD_CLASSIFICATION=empty|complete
SCREENSHOT_REMAINING_CAPACITY=verified
IPHONE_69_CHOOSE_FILE=clicked|not_needed_existing_complete
FILE_PICKER=verified|not_needed_existing_complete
SCREENSHOT_COUNT=verified_N
SCREENSHOT_FILES=all_N_selected|already_complete
SCREENSHOT_UPLOAD_ATTEMPT_ID=<stable-id>|not_needed_existing_complete
SCREENSHOT_UPLOAD=verified_N_of_10
UTM_19=verified
```

记录 `UTM_19=verified`，结束 `utm-19`，保留当前 VM、guest Edge 和 Media Manager 页面，立即继续 `utm-20`；不得等待用户确认。阻断、失败或未完成状态不得交接。

## 阻断条件

- VM、SSH 用户、home、guest Edge、Notion API 父页面/匹配页面或应用名不匹配。
- 链接/剪贴板核对失败，或除最前面的 `https://`/`http://` 协议头外，`://` 后的任何字符被删改、截断或重新拼接。
- 下载未完成、ZIP 不能唯一对应、压缩包损坏、成员路径不安全、解压目标已存在、解压失败、结果为空或含符号链接。
- App Store Connect 未登录、应用不唯一、应用页面未打开、Media Manager/`6.9" Display`/该尺寸的 `Choose File` 无法明确定位，或点击后文件选择器未出现。
- JPEG 集合不能唯一确定、文件列表焦点不明确、`Select All` 未蓝色高亮、全部 `N` 张未同时选中、`Open` 不可用，或上传后的 `N of 10 Screenshots` 与 SSH 统计不一致。

出现上述条件时先暂停后续副作用，并严格执行本技能自动恢复矩阵；每轮都从最新截图、同一数字 App ID、SSH 清单和同一 attempt 重建判断。只有自动恢复预算穷尽或只读证明是外部不可修复状态，才以对应 `utm-19-*` stage 和完整恢复证据发送最后故障卡并等待。不得泄露链接、token、账号、密码、手机号或验证码；不得删除/覆盖 Downloads 现有内容，不得上传未经核对的文件。
