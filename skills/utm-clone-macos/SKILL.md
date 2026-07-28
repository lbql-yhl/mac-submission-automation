---
name: utm-clone-macos
description: Use when the current submission run needs a nonvisual UTM macOS clone created from the configured template on the current host.
---

# UTM Clone macOS

## 无视觉执行边界

本技能只允许 UTM CLI/Registry、宿主 shell、plist/文件操作和命令回读；其他交互方式不属于本技能。所有路径从 `preflight.py` 的当前宿主配置读取；克隆包只能写入 `${SUBMISSION_VM_IMAGES_DIR}`，不得写入系统盘默认 Documents 目录。

执行任何命令前，在项目根目录运行：

```bash
eval "$(python3 scripts/preflight.py --project-only --emit-shell)"
```

本技能继承 [`../_shared/AUTOMATION_CONTRACT.md`](../_shared/AUTOMATION_CONTRACT.md) 的自动诊断、自动修复、自动复验和最后故障卡规则；其中 `OP-NATIVE-PASTE`、`OP-BROWSER-URL-NO-SCHEME`、`OP-APPLE-PHONE-OTP`、`OP-FIXED-PASSWORD-1234`、`OP-USER-CONFIRMATION` 不在本技能正常路径调用。正常成功路径不等待用户确认。

## 本技能自动恢复矩阵

| 故障点 | 自动诊断、修复和复验 | 最后出口 |
|---|---|---|
| 模板/目标卷不可读 | 间隔 2/5/10 秒重读动态路径、模板包、`config.plist` 和目标卷挂载状态 | 同一固定模板仍缺失或损坏 |
| 目标包已存在 | 只读比较 marker 的 run/name/source/attempt；完全匹配才续跑 | 缺 marker、符号链接或归属不明，绝不覆盖 |
| 复制/identity 写入失败 | 保留同一 attempt，比较清单；对本次 plist 写入用 before bytes 原子还原后独立复验 | 三轮后仍不一致 |
| UTM 注册不匹配 | 三轮读取 `utmctl list` 与 UTM Registry；计数 0 时只对精确 bundle 调用一次系统注册命令 | 多条、名称/UUID/路径不一致或状态不明 |

## 输入与不可变目标

1. 从同一 Feishu run 继承 `run_id`、四位小写 `vm_name` 和登记宿主机。`run_id` 必须匹配 `^[A-Za-z0-9-]{8,80}$`，`vm_name` 必须匹配 `^[a-z]{4}$`；不得重新生成名称或选择其他 run。
2. 固定并验证路径。`src` 只能是 `${SUBMISSION_VM_TEMPLATE}`，`dst` 只能是 `${SUBMISSION_VM_IMAGES_DIR}/$name.utm`，二者均非符号链接；模板、目标目录和目标卷均必须存在且可读写。

```bash
src="${SUBMISSION_VM_TEMPLATE}"
name="<inherited-vm_name>"
run_id="<inherited-run-id>"
dst="${SUBMISSION_VM_IMAGES_DIR}/$name.utm"
marker="$dst/.submission-clone.json"
[[ "$run_id" =~ ^[A-Za-z0-9-]{8,80}$ ]]
[[ "$name" =~ ^[a-z]{4}$ ]]
test -d "$src" -a ! -L "$src"
test -f "$src/config.plist" -a ! -L "$src/config.plist"
test "$(dirname "$dst")" = "$SUBMISSION_VM_IMAGES_DIR"
```

3. 两次相隔 3 秒执行 `utmctl list`，要求模板 UUID 的状态均为 `stopped`。模板不是 stopped 时只读等待同一状态变化；不得复制运行中的磁盘，也不得替换模板。

## 克隆、身份与文件回读

1. 在任何复制前分类目标。分类枚举固定为 `CLONE_DESTINATION=absent|resume_verified|conflict`：目标不存在时以 mode `600` 原子写入 marker，包含 `run_id`、`vm_name`、模板规范路径、稳定 `CLONE_ATTEMPT_ID` 和 `status=copying`。目标已存在时，只有 marker 四项逐字节匹配才复用同一 attempt；其他情况记录 `CLONE_DESTINATION=conflict`，完成三轮独立只读比较后进入最后出口。
2. 对当前 run 拥有的 absent 或 copying 目标执行一次复制：

```bash
/usr/bin/ditto "$src/." "$dst/"
```

只接受 exit `0`。中断时保留 marker，比较源/目标清单后只对同一 attempt 允许一次补齐复制；不得创建第二个目标包。

3. 先将唯一计划身份写入 marker，再用原子 Python/plist 写入修改 `$dst/config.plist`。必须只改 `Information.Name`、`Information.UUID`、唯一 `Network[0].MacAddress` 与 Apple `System.MacPlatform.MachineIdentifier` 的新非零 ECID；`HardwareModel` 必须逐字节保留。MAC 必须 locally-administered unicast，UUID、MAC、MachineIdentifier 必须均不同于模板。写前保存 before bytes，写后独立回读；任一断言失败先原子还原 before bytes 并停止。
4. 用单个只读 Python 比较器递归枚举源/目标，排除 `config.plist` 与当前 marker 后逐项核对类型、链接目标、权限类别、字节数和 SHA-256。只接受下列输出：

```text
CLONE_SOURCE_MANIFEST_SHA256=<sha256>
CLONE_DESTINATION_MANIFEST_SHA256=<same-sha256>
CLONE_MISSING=0
CLONE_EXTRA=0
CLONE_MISMATCHED=0
CLONE_CONFIG_IDENTITY=verified
```

## UTM CLI/Registry 注册与回读

1. 从目标 `config.plist` 读取精确 UUID。连续两次执行 `utmctl list`，并读取 UTM Registry；不得从名称相似的包、默认目录或其他 UUID 推断注册结果。

```bash
target_uuid="$(/usr/libexec/PlistBuddy -c 'Print :Information:UUID' "$dst/config.plist")"
utmctl list
defaults read com.utmapp.UTM Registry
```

2. 若目标 UUID 在 UTM CLI 和 Registry 均为零条，且 bundle、marker、plist identity 都已验证，才允许一次：

```bash
open "$dst"
sleep 3
utmctl list
defaults read com.utmapp.UTM Registry
```

这是系统注册调用，不得对任何其他包执行；调用后不进行界面操作。
3. 在新的只读进程中按 Registry 的精确 UUID 条目验证：名称等于 `$name`、包规范路径等于 `$dst`、UTM CLI 同 UUID/名称组合计数为 `1` 且状态为 `stopped`。任何多条、路径不匹配或状态不明都完成三轮只读复核，不得删除、重命名或重新注册其他 VM。
4. 将 marker 原子更新为 `status=complete`，写入两个 manifest SHA-256、最终 config SHA-256、UTM UUID 和完成时间。新进程再次读取 marker、plist、UTM CLI 和 Registry；全部精确一致才记录：

```text
CLONE_ATTEMPT_ID=<stable-attempt-id>
CLONE_DESTINATION=absent|resume_verified
CLONE_MARKER=verified
CLONE_SOURCE_MANIFEST_SHA256=<sha256>
CLONE_DESTINATION_MANIFEST_SHA256=<same-sha256>
CLONE_CONFIG_IDENTITY=verified
UTM_REGISTRATION_MATCH_COUNT=1
UTM_REGISTRATION_STATE=stopped
UTM_CLONE_MACOS=verified
```

## Guardrails

- 不得修改 CPU、内存、磁盘、显示、启动参数或网络以外的 VM 配置。
- 不得在系统盘、默认 UTM Documents 目录或模板包中创建目标。
- 不得把 guest `IOPlatformSerialNumber` 或 `IOPlatformUUID` 当作本技能成功证据；`utm-2` 负责经 SSH 的 guest 三码读取和模板对账。
- 不得把 UTM 已启动、命令无错误或历史状态当作注册成功证据。

## 最后出口

每个不可恢复状态必须先完成同一模板、目标包和 attempt 的三轮诊断、可安全修复和独立复验，记录：

```text
AUTO_RECOVERY_ATTEMPTS=<actual-count-at-least-3>
AUTO_RECOVERY_ACTIONS=<diagnose,repair,reverify>
AUTO_RECOVERY_RESULT=exhausted|unrepairable
```

自动恢复穷尽后才执行：

```bash
python3 services/feishu_bot.py notify-fault \
  --run-id '<current-run-id>' --chat-id '<original-chat-id>' \
  --stage 'utm-clone-macos:<fault-stage>' --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-clone-macos' --recovery-attempts '<actual-count-at-least-3>' \
  --recovery-actions '<diagnose,repair,reverify>' --recovery-result '<exhausted|unrepairable>'
python3 services/feishu_bot.py wait-decision --run-id '<current-run-id>' --decision-kind fault --timeout-seconds 3600
```

`--recovery-result unrepairable` 必须同时追加 `--unrepairable`；少于三轮时运行时拒绝发卡。`manual_continue` 与 `retry_skill` 都只重读同一 source/destination/attempt。

## 连续交接

仅当 `UTM_CLONE_MACOS=verified` 后，将同一 run、`vm_name`、bundle、config UUID、MAC、marker 和 `CLONE_ATTEMPT_ID` 原样交接给 `utm-1`。不得启动 guest 或改选其他目标。
