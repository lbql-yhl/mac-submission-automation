---
name: utm-1
description: Use when the user asks to run UTM-1 after cloning a UTM macOS VM, prepare the cloned VM's Sharing and Network settings, start it, and log in to the macOS desktop.
---

# UTM-1

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
  --stage 'utm-1:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-1' \
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
| 克隆交接缺失 | 自动重跑同一 run/`vm_name` 的 `utm-clone-macos` 一次并复验，不生成新名称 | 同一目标仍不唯一才发卡 |
| UTM 编辑页/共享页误点 | 窗口尺寸/焦点变化或误点后等待至少 3 秒，用最新截图 `Escape` 回到目标 VM，重新打开 Edit→Sharing；成功记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立定位后仍找不到唯一控件才 `exhausted` |
| 共享目录/只读未保存 | 重开同一 VM Sharing，只修复目标行，保存后重新读取偏好；不得增加重复行 | 三轮安全保存修复且每轮独立回读后仍不一致才发卡 |
| 启动/登录结果不明 | 只读查询同一 VM 状态与当前登录画面；证明未启动才重试一次，已 started 只恢复画面 | 仍无法确认精确 VM/用户为 `unrepairable` |

## Overview

Prepare the VM created by the clone skill, then boot it into the macOS desktop. UTM 4.7.x does not expose Sharing edits through `utmctl`, and its main window may have an empty accessibility tree, so drive the UTM GUI with screenshots/clicks when needed.

## Target VM

- Directly inherit the current Feishu run `vm_name` and `UTM_CLONE_MACOS=verified` from `utm-clone-macos`, and require `${SUBMISSION_VM_IMAGES_DIR}/<vm_name>.utm` to exist.
- The current executor must retain the immutable `run_id`, original `chat_id`, and `vm_name`; a transient runtime read failure re-reads only that exact run. If `UTM_CLONE_MACOS=verified` or `${SUBMISSION_VM_IMAGES_DIR}/<vm_name>.utm` is missing, 自动重新执行 `utm-clone-macos` for the same run and `vm_name`, then recheck both values. Never generate another name or select a user-named/newest VM.
- If the exact upstream rerun cannot restore an unambiguous verified clone, use the first row of this file's **本技能自动恢复矩阵**: read the same clone marker twice, require exact run/`vm_name`/source/attempt ownership, recheck the plist identity and unique stopped UTM registration, and rerun only the incomplete upstream check. This is the complete `utm-1-handoff-recovery` procedure; it is not a separate or missing skill. Only recovery exhaustion or a proven external ownership conflict enters the last global fault-card flow. `manual_continue` rechecks the same handoff; `retry_skill` 立即重跑当前技能 and first repeats this exact recovery check while skipping verified work.

Do not edit the source template VM `macOS`.

## Fixed Values

- Shared folder: only the absolute path resolved by `SUBMISSION_SHARED_DIR`. It must be an existing, non-symlink directory; never substitute a copied Desktop path.
- Shared folder must be read-only.
- Network: click Random three times.
- Login user: `demo`.
- Login password 调用 `OP-FIXED-PASSWORD-1234` 的 VM 登录子流程：`1234` 仅以四次独立按键输入并回读四个圆点，不通过剪贴板。

## Workflow

1. 固定 `name`、bundle、config 和 share；要求名称四位小写、bundle marker 与上游同一 run/attempt 精确匹配，share 为绝对的非符号链接目录。两次读取 `utmctl status "$name"`；只有两次都是 `stopped` 才允许编辑：

   ```bash
   name="<inherited-vm_name>"
   bundle="${SUBMISSION_VM_IMAGES_DIR}/$name.utm"
   config="$bundle/config.plist"
   share="${SUBMISSION_SHARED_DIR}"
   [[ "$name" =~ ^[a-z]{4}$ ]]
   test -d "$bundle" -a ! -L "$bundle"
   test -f "$config" -a ! -L "$config"
   test -d "$share" -a ! -L "$share"
   utmctl status "$name"
   sleep 3
   utmctl status "$name"
   ```

2. 打开 UTM 后，从最新截图确认唯一卡片名精确为 `$name`，再依次执行“右键卡片 → 等 3 秒/重读 → Edit → 等 3 秒/重读 → Sharing → 等 3 秒/重读”。每次只能在最新截图仍显示目标高亮时点击下一项；名称不唯一或选中模板 `macOS` 时立即退出编辑且不保存。
3. 在 Sharing 表中按规范化绝对路径统计 `$share`：
   - 0 行：启用 `添加只读`，点击一次 `添加`；等待并确认原生文件选择器属于 UTM，再选择精确目录 `$share`，点击一次 `打开`；
   - 1 行且 `只读?` 已启用：不改；
   - 1 行但未只读：只删除该行；等待/重读后启用 `添加只读` 并重新添加同一路径；
   - 多于 1 行：不猜哪一行，关闭且不保存，进入 `utm-1-sharing-duplicate` 恢复。
4. 最新截图必须同时证明路径完整匹配且该行 `只读?` 开启；此时点击一次 `存储/Save`，等待至少 3 秒，重新打开同一 VM 的 Sharing 页再次读取。记录 `SHARING_MATCH_COUNT=1` 和 `SHARING_READ_ONLY=verified`。
5. 再用结构化 plist 读取器核对 UTM preferences：先从 config 精确读取目标 UUID，再将 preferences 转为对象，只统计这个 UUID 所属对象中规范化后等于 `$share` 的 `SharedDirectories` 项；要求计数 1 且其 `ReadOnly` 为 true。不得用跨整个 plist 的文本 `rg "$uuid|$share|ReadOnly"` 拼接证据，因为它可能把不同 VM 的字段混在一起。
6. 回到同一 VM 的 Edit → Network。读取 config 中当前 MAC 为 `mac_0`；对可见 `Random` 按钮重复三轮“点击一次 → 等 3 秒 → 保存/回读 config → 要求新 MAC 合法且不同于上一值”，得到 `mac_1`、`mac_2`、`mac_3`。任一轮界面未变化只恢复该轮，不把连续三击当作一个动作。最终记录 `NETWORK_RANDOM_ROUNDS=3` 和 `NETWORK_MAC_CHANGED=verified`。
7. 关闭编辑页后再次读 `utmctl status "$name"`：
   - `stopped`：执行一次 `utmctl start "$name"`，等待至少 3 秒；
   - 已为 `started/running` 且本 attempt 已记录启动请求：只恢复控制台，不再 start；
   - 其他状态：两轮只读检查，不发送第二个启动请求。

   随后轮询同一名称与同一 config UUID，直到唯一状态为 running，并记录 `VM_START_ATTEMPT=verified`。
8. 最新 UTM 控制台截图必须显示窗口标题精确为 `$name` 和 macOS 登录界面。若只显示别的用户，点击一次用户切换区域，等待/重读后选择唯一 `demo`。确认标题/账号均正确后清空密码框至占位文字 `Enter Password`，分别输入 `1`、`2`、`3`、`4`；每个按键后等待至少 3 秒并重读，最终要求恰好四个圆点，再提交一次。
9. 提交结果不明时不重复输入：等待并用两张新截图分类 `login_screen|progress|desktop|password_rejected|locked`。仅 `password_rejected` 才清空后重做同一固定密码；`locked` 等待页面显示的完整时间。成功必须看到桌面菜单栏/访达和当前用户菜单中的 `demo`，窗口标题仍为 `$name`，记录：

   ```text
   SHARING_MATCH_COUNT=1
   SHARING_READ_ONLY=verified
   NETWORK_RANDOM_ROUNDS=3
   NETWORK_MAC_CHANGED=verified
   LOGIN_USER=demo
   LOGIN_DESKTOP=verified
   UTM_1=verified
   ```

## Guardrails

- Only change Sharing and Network settings.
- Do not change CPU, memory, display, disk, boot, or VM identity fields outside the network random action.
- Save after the Sharing change and save again after the Network randomization.
- If macOS says the account is locked, wait for the full lockout period before retrying; clear the password field before entering `1234` again.

## 连续交接

仅当本技能全部完成检查通过并记录 `UTM_1=verified` 时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-2`；不得等待用户确认。阻断、失败或未完成状态不得交接。
