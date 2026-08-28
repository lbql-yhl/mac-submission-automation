---
name: utm-21
description: 在 utm-p8 完成后，根据飞书卡片选择的分支下载代码，写入同一台 UTM 虚拟机，并替换固定的 App ID 与正式包名字符串。
---

# utm-21

读取并遵守 [`../_shared/AUTOMATION_CONTRACT.md`](../_shared/AUTOMATION_CONTRACT.md)。在仓库根目录执行入口命令前，先运行 `eval "$(python3 scripts/preflight.py --project-only --emit-shell)"`。

## Contract

- Segment: 4, 代码处理；本技能是该段入口。
- 执行前提：同一台 UTM 虚拟机的同一 Run 必须已有成功的 `UTM_P8=verified` 证据。
- 固定继承精确的 `run_id`、原始 `chat_id`、宿主、应用、四字母 VM/用户、VM IP、唯一 Notion 页面、App ID、Bundle ID 和浏览器会话。禁止按“最新”“第一个”或“最接近”重新选择。
- 只运行以下完整 UTM-21 工作流入口：

  ```bash
  python3 "$PROJECT_ROOT/scripts/utm_21_prepare.py" \
    --run-id '<run-id>' --chat-id '<chat-id>' --app-name '<app-name>' \
    --vm-name '<vm-name>' --vm-ip '<vm-ip>'
  ```

- 入口只使用 Feishu OpenAPI、命令和 API 传输。`VISUAL_CONTROL=forbidden`、`AGENT_CONTROL=forbidden`：禁止使用页面 DOM、截图、坐标、剪贴板或交互式智能体操作。

## Required workflow

1. 执行任何动作前，重新校验精确的活动 Run 和成功的 `UTM_P8=verified` 尝试。全程保持同一应用、VM、IP/用户、Notion 页面、App ID、Bundle ID、宿主、群聊路由和浏览器会话。
2. 仅通过 Feishu OpenAPI 读取精确应用行的 `代码 URL` 字段。字段无链接时，按 0/5/10 秒做三次只读复核，通过共享恢复门禁发送最终故障卡，然后停止；不得打开浏览器或发送分支卡。
3. 使用宿主命令在宿主浏览器中打开已校验的仓库 URL。发送一张绑定当前 Run 的飞书分支卡，选项严格为 `main`、`dev`、`release`；只接受授权且完全匹配的回调，并在同一浏览器会话中打开所选分支。
4. 将所选分支解析为唯一 commit，下载固定到该 commit 的 ZIP。ZIP 必须落为当前 Run 私有临时文件，校验并安全解压后删除。
5. 将解压后的根目录原子放置到已配置的宿主共享目录，并命名为 `<app-name>-git`。新鲜内容清单必须包含隐藏文件和可执行位，并满足 `HOST_CONTENT_MANIFEST=verified`。
6. 通过已配置的 SSH 密码通道，将整个目录复制到 `/Users/<vm-user>/Downloads/<app-name>-git`。重新校验虚拟机用户身份，先用新鲜虚拟机内容清单与未修改的宿主清单逐项比较，并满足 `GUEST_CONTENT_MANIFEST=verified`。
7. 只通过 `scripts/notion_api.py` 读取固定的 `<app-name>-<vm-user>` Notion 页面。先后校验同一宿主父页三次，并稳定读取两次 `账号信息` 下的 `APP_ID：`、`应用信息` 下的 `正式包名: ` 和 `应用名: `。两次结果、应用名或固定页面身份不一致时立即停止；不得按最新页面重新选择。
8. 在虚拟机内递归检查 `Downloads/<app-name>-git` 的全部普通文件，包括隐藏文件。以下字符串独立处理，不要求全部存在；不存在时计数为 0 并继续：

   | 待替换字符串 | 替换值 |
   | --- | --- |
   | `5372311233` | 当前固定 Notion 页的 App ID |
   | `jltest.test.test` | 当前固定 Notion 页的正式包名 |
   | `uildbet.brovaxtere` | 当前固定 Notion 页的正式包名 |
   | `xycoins.2027.test` | 当前固定 Notion 页的正式包名 |
   | `org.toolbox.fastcleaner` | 当前固定 Notion 页的正式包名 |

9. 替换值只通过 SSH stdin JSON 进入虚拟机，不得出现在命令参数、日志或卡片中。每个文件只做一次非级联字节替换，以同目录临时文件原子写入并保留权限；符号链接、硬链接和其他特殊文件一律拒绝。宿主共享目录中的原始代码保持不变。
10. 宿主在内存中计算替换后的预期清单和各字符串命中数，虚拟机替换后重新生成新鲜清单并逐项匹配。私有 ledger 只保存标识符哈希、命中数和清单，不保存 App ID 或正式包名明文。中断恢复只接受同一 Run 中每个文件处于“原始”或“已完成替换”两种状态，已完成文件不得重复替换。

不得覆盖、合并、删除或重命名未绑定的既有宿主或虚拟机目标。只有私有 ledger 和新鲜一致的内容清单能证明属于同一 Run 时，才允许恢复临时状态或结果未知状态。其他失败遵守共享合同的有界恢复规则。

## Result and handoff

只有虚拟机最终清单与宿主计算的替换后预期清单完全一致后，才能输出 `执行成功：utm-21；UTM_21=verified`。随后立即把同一 Run、应用、VM/IP/用户、所选分支与 commit、`Downloads/<app-name>-git`、标识符和存活的浏览器会话交接给 `utm-22`。
