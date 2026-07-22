---
name: utm-clone-macos
description: Use when the user asks to clone, duplicate, or prepare the UTM macOS virtual machine at ${SUBMISSION_VM_TEMPLATE} for a Feishu-triggered submission run.
---

# UTM Clone macOS

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
  --stage 'utm-clone-macos:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-clone-macos' \
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
| 模板暂时不可读 | 重载动态路径，验证固定模板包、plist 和卷可读性三轮 | 模板确实缺失/损坏为 `unrepairable` |
| 目标已存在/半成品 | 比较当前 run 克隆标记、目标名和 identity；完整匹配即幂等完成；只有当前 run 明确拥有的未完成目标才移入隔离临时路径、重建并验证后删除隔离副本 | 所有权不明或完整但身份冲突时不删除，发卡 |
| 复制/identity 写入失败 | 在同一目标上核对实际完成点；可逆 plist 写入用 before 自动还原，再重新应用一次；第三轮只读比较 before/after/identity | 三轮复验仍失败才 `exhausted` |
| GUI 注册误点 | 窗口尺寸/焦点变化或误点后，等待至少 3 秒读取最新截图，`Escape`/`Cancel` 回到 VM 列表并重新定位精确包；成功记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立定位后仍不能唯一注册才发卡 |

## Fixed Paths

- Source VM: `${SUBMISSION_VM_TEMPLATE}`
- Clone output folder: `${SUBMISSION_VM_IMAGES_DIR}/`
- Clone package path: `${SUBMISSION_VM_IMAGES_DIR}/<vm_name>.utm`
- 固定模板由项目预先提供 at `${SUBMISSION_VM_TEMPLATE}`; its presence is a required infrastructure invariant, not an optional user input. If unavailable, reload this host's dynamic path configuration and check the exact package, parent volume, mount/readability and `config.plist` at 2/5/10 seconds. Do not search for or substitute another template. Only a persistent missing/damaged configured asset after `utm-clone-template` recovery exhaustion may use the last global fault-card exit.

Use the global card with these stages: invalid/missing immutable run context = `utm-clone-run-context`; fixed template unavailable = `utm-clone-template`; existing or partial destination = `utm-clone-destination`; unexpected plist shape = `utm-clone-schema`; copy/identity/registration verification failure = `utm-clone-verification`. `manual_continue` rechecks the same exact source/run/destination. `retry_skill` must 立即重跑当前技能 and skip only verified checks; it must never overwrite or delete an ambiguous destination. Repeated failure sends a new card.

## Workflow

1. 运行 preflight 后，从同一 Feishu run 取 `run_id`、`vm_name` 和宿主机名称；要求 `run_id` 只含字母、数字和连字符且长度 8–80，`vm_name` 精确匹配 `^[a-z]{4}$`，本机 `SUBMISSION_HOST_MACHINE` 与 run 宿主机精确相等。解析并固定路径：

   ```bash
   src="${SUBMISSION_VM_TEMPLATE}"
   name="<run vm_name>"
   run_id="<current-run-id>"
   dst="${SUBMISSION_VM_IMAGES_DIR}/$name.utm"
   marker="$dst/.submission-clone.json"
   [[ "$run_id" =~ ^[A-Za-z0-9-]{8,80}$ ]]
   [[ "$name" =~ ^[a-z]{4}$ ]]
   test -d "$src" -a ! -L "$src"
   test -f "$src/config.plist" -a ! -L "$src/config.plist"
   test "$(dirname "$dst")" = "$SUBMISSION_VM_IMAGES_DIR"
   ```

2. 在两次相隔 3 秒的只读检查中确认模板 VM 为 `stopped`，且 UTM 没有正在保存/编辑该模板。模板仍运行时只请求一次 guest 正常关机并等待 stopped；结果不明时不得复制磁盘。记录 `CLONE_SOURCE_STATE=stopped`。
3. 在任何复制前分类目标：
   - 目标不存在：创建目标目录，并以原子 replace 写入 mode-600 `marker`，内容绑定 `run_id`、`vm_name`、源模板规范路径、随机稳定 `CLONE_ATTEMPT_ID` 和 `status=copying`；记录 `CLONE_DESTINATION=absent`。
   - 目标存在且 marker 四项完全匹配：记录 `CLONE_DESTINATION=resume_verified`，继承原 attempt；不得生成新 attempt 或新身份。
   - 目标存在但 marker 缺失、不可解析、符号链接或任一所有权字段不匹配：记录 `CLONE_DESTINATION=conflict`，不执行 `ditto`、删除或改名；完成三轮独立只读核对后才进入最后故障卡。

   marker 必须先于第一个复制副作用落盘；后续每次状态更新都写同目录临时文件、`fsync`、`chmod 600`、`os.replace` 并重新读取精确匹配。

4. 对 `absent` 或 `resume_verified/status=copying` 的同一 attempt 执行：

   ```bash
   /usr/bin/ditto "$src/." "$dst/"
   ```

   仅 exit 0 可进入下一步。传输中断时保留 run-owned marker，重新比较源/目标清单；只对这个同一 attempt 再执行一次 `ditto` 补齐，禁止创建第二目标。
5. 先把计划身份持久化进 marker，再改 plist。计划只生成一次，包括新 `Information.UUID`、locally-administered unicast MAC 和 Apple backend 的非零 ECID；恢复时复用相同计划值。随后由 Python 原子改写 `$dst/config.plist`：
   - schema 必须唯一存在 `Information.Name`、`Information.UUID`、恰好一个 `Network[0].MacAddress`；Apple backend 还必须有 `System.MacPlatform.HardwareModel` 和 `MachineIdentifier`；
   - 保存本次 config before bytes；写临时文件、`fsync`、保留权限并 `os.replace`；
   - 立即回读，要求名称等于 `vm_name`，UUID/MAC/ECID 等于 marker 的计划值，UUID、MAC、MachineIdentifier 均不同于模板，`HardwareModel` 与模板逐字节相同；
   - 任一断言失败就用 before bytes 原子还原并独立回读，然后停止；不得再生成一组身份。

   配置 plist 中没有由本技能安全修改的 guest serial 字段，因此本技能不得声称“已修改序列号”。guest `IOPlatformSerialNumber`/`IOPlatformUUID` 的模板对账只由启动后的 `utm-2` 完成。
6. 用单个只读 Python 校验器递归枚举源/目标。排除仅允许不同的 `config.plist` 和目标 marker 后，对每个相对路径核对类型、符号链接目标、权限类别、字节数和文件 SHA-256；任何额外、缺失或哈希不同都失败。输出仅含：

   ```text
   CLONE_SOURCE_MANIFEST_SHA256=<manifest-sha256>
   CLONE_DESTINATION_MANIFEST_SHA256=<same-value>
   CLONE_MISSING=0
   CLONE_EXTRA=0
   CLONE_MISMATCHED=0
   CLONE_CONFIG_IDENTITY=verified
   ```

   这一步替代“目录大小差不多”的判断；比较器自身异常也算失败，不能把非 0 一律解释为“身份不同”。
7. 先读 `utmctl list` 并以目标 UUID + 精确 `vm_name` 计数：
   - 计数 0：执行一次 `open "$dst"`，等待至少 3 秒，重新读取；
   - 计数 1：要求同一行状态为 `stopped`；
   - 计数大于 1、名称与 UUID 分属不同条目或状态不明：不再打开，进入注册冲突恢复。

   成功证据必须为 `UTM_REGISTRATION_MATCH_COUNT=1` 和 `UTM_REGISTRATION_STATE=stopped`。
8. 将 marker 原子更新为 `status=complete`，写入两个 manifest SHA-256、最终 config SHA-256、UTM UUID 与完成时间；再开一个全新只读进程回读 marker、plist 和 `utmctl list`。只有全部仍匹配才记录：

   ```text
   CLONE_ATTEMPT_ID=<stable-attempt-id>
   CLONE_DESTINATION=absent|resume_verified|conflict
   CLONE_MARKER=verified
   CLONE_SOURCE_MANIFEST_SHA256=<sha256>
   CLONE_DESTINATION_MANIFEST_SHA256=<same-sha256>
   UTM_REGISTRATION_MATCH_COUNT=1
   UTM_REGISTRATION_STATE=stopped
   UTM_CLONE_MACOS=verified
   ```

   `CLONE_DESTINATION=conflict` 绝不属于成功取值；该枚举保留在契约中用于明确阻断分类。Only after `UTM_CLONE_MACOS=verified` immediately hand the same run/clone/attempt to `utm-1`. Do not start it here; `utm-2` owns guest-visible identity verification after `utm-1` boots it.

## Guardrails

- Do not generate or substitute a clone name here.
- Do not search for or substitute another source template.
- Do not skip the final destination-exists check.
- Do not change CPU, memory, disk, display, or boot settings.
- If the plist schema is different from expected, do not guess keys. Re-read the exact source/destination plist with `plutil -lint` and the known schema paths twice, restore any current-attempt reversible write from its before copy, and preserve both packages. Only persistent incompatible schema after `utm-clone-schema` recovery exhaustion may use the last global fault-card exit.
