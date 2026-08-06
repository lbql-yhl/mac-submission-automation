# UTM-A 独立 Accessibility 自动化设计

> 状态：已获用户口头批准的实现规格；脚本与技能通过验证前，不作为可执行成功证明。

## 目标与边界

`utm-a` 是项目内唯一新增的独立技能。它只操作用户明确指定、已经运行并停留在 Aqua 桌面的 UTM macOS 客体，在“隐私与安全性 → 辅助功能”中启用以下三项现有记录：

- `AEServer`
- `sshd-keygen-wrapper`
- `Terminal`

它明确排除 `ChatGPT` 和 `Codex Computer Use`，不添加其他应用，不使用 `+` 文件选择器，不修改 TCC 数据库，不调用 `tccutil` 绕过授权，不启动、停止、重启、恢复或切换任何虚拟机，也不加入飞书提审主线、run、卡片或后续技能交接。

唯一入口为：

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_a_accessibility.py \
  --vm-name '<精确四位小写虚拟机名称>'
```

入口不接受“当前”“最新”、模糊名称、IP、用户名或密码参数。密码固定为项目约定的 `1234`，只在进程内用于 SSH/PTTY 或向精确 UTM 窗口发送四个数字键；不得进入 argv、环境变量、剪贴板、日志、输出或新建的持久文件。

## 架构

### 宿主编排器

`/Users/yehailin/Documents/mac提审自动化/scripts/utm_a_accessibility.py` 负责目标锁定、只读运行态核验、IP/SSH 身份核验、UTM 窗口锁定、截图、OCR 结果判定、点击与键盘事件、三秒闭环、二次视觉复验和独立 SSH 信任复验。

脚本复用项目已有 SQLite 库存与固定密码 SSH 的安全约束，但不复用会把密码写入 `SSH_ASKPASS` 文件的传输实现。UTM-A 自己用受控 PTY 响应唯一密码提示，输出缓冲在返回前移除提示和密码，且异常只报告阶段和非敏感原因。

### Vision OCR 辅助器

`/Users/yehailin/Documents/mac提审自动化/scripts/utm_a_vision.swift` 只读取宿主编排器传入的临时 PNG 路径，使用 macOS 原生 Vision 返回文字、置信度和归一化矩形。它不点击、不键入、不选择 VM，也不保存 OCR 结果。

编排器只截取已锁定的精确 UTM 客体窗口。每轮 OCR 都来自刚生成的截图；文字矩形必须唯一命中页面标题、目标行或授权按钮。开关目标通过“唯一文字行 + 同行右侧开关几何/颜色状态”动态解析，不能使用跨运行保存的绝对坐标。找不到、重复、低置信度或无法判断开关状态时立即阻断。

### 技能与发现

项目源新增：

- `/Users/yehailin/Documents/mac提审自动化/skills/utm-a/SKILL.md`
- `/Users/yehailin/Documents/mac提审自动化/skills/utm-a/agents/openai.yaml`

`utm-a` 进入 `STANDALONE=("utm-a",)`，但 21 个 `ORDERED` 主线技能及其顺序、交接和成功标记保持不变。安装器为 `utm-a` 建立 `/Users/yehailin/.codex/skills/utm-a` 发现软链接；它不建立第二份正文。

## 执行数据流

1. 校验 `--vm-name` 精确匹配四位小写名称。
2. 从 `/Users/yehailin/Documents/mac提审自动化/runtime/vm-inventory.sqlite3` 唯一读取记录，并逐项核对 bundle 真实路径、非符号链接、`config.plist` UUID、唯一网络 MAC 与 SQLite 值。
3. 只读执行 `utmctl status <vm_name>`，只接受唯一 `started` 或 `running`；任何其他状态阻断，绝不发出生命周期命令。
4. 通过 `utmctl ip-address <vm_name>` 与注册 MAC 对应的 ARP 结果取唯一交集；0 个或多个候选均阻断。
5. 用密码 PTY 建立新 SSH 连接，精确回读 `id -un=<vm_name>`、`HOME=/Users/<vm_name>`、`stat -f %Su /dev/console=<vm_name>`，并确认 Aqua 会话可用。
6. 通过该 SSH 会话打开辅助功能设置深链接；至少等待三秒。
7. 通过宿主 UTM Accessibility 树唯一锁定 UTM 进程、名称完全相同的单一客体窗口以及唯一 `Capture Input` 控件；若关闭则只点击一次，等待三秒并重新读取为开启。
8. 新截取该窗口并用 Vision 确认辅助功能页面和三个唯一目标行。仅对当前明确为关闭的目标开关逐项操作；每次操作后至少等待三秒、重新截图、重新 OCR 并确认该项已经开启，才能进入下一项。
9. 若点击后出现唯一“隐私与安全性”授权对话框，必须在新截图中确认对话框归属当前设置页、用户名唯一等于 `<vm_name>`、密码框唯一、`Modify Settings` 按钮唯一且启用。点击密码框后仅向精确 UTM PID 发送 `1`、`2`、`3`、`4`，再等待三秒并新截图确认密码框已填写但不读取内容；点击唯一 `Modify Settings` 一次，再等待三秒确认对话框关闭且原目标开关开启。
10. 三项全部处理后，间隔至少三秒取得两张新截图；两次都必须确认三项唯一且为开启状态，同时确认排除项从未成为点击目标。
11. 新建独立 SSH 进程运行只读 `AXIsProcessTrusted()` 探针；只有 `sshd-keygen-wrapper` 返回 true 才记录独立信任成功。

脚本不关闭 System Settings，保留用户可见的最终辅助功能页面。

## 失败关闭与安全性

以下任一情况都返回非零且不猜测、不继续：库存或 bundle 身份不一致、VM 未运行、IP 不唯一、SSH 用户/Home/console user 不一致、UTM 窗口不唯一、`Capture Input` 不唯一、页面标题不匹配、目标行缺失或重复、开关状态不可判定、授权对话框归属/用户名/密码框/按钮不唯一、任一动作后三秒新截图未验证、两轮最终截图不一致、SSH 信任探针不是 true。

脚本不得把屏幕截图长期保存在项目、桌面或客体。运行期截图创建在 mode-700 临时目录中，并在正常或异常退出时逐个删除后移除该精确临时目录。日志只输出阶段标记，不输出截图 OCR 全文、IP、UUID、MAC、用户名、密码、命令原文或授权字段内容。

由于本技能只启用已有行，任何目标行不存在时都阻断并明确报告 `target_row_missing`；当前版本不自动通过 `+` 添加应用。这是有意的安全边界。

## 成功合同

返回码必须为 `0`，并依次包含：

```text
UTM_A_TARGET=verified
UTM_A_WINDOW=verified
AESERVER_ACCESSIBILITY=verified
SSHD_KEYGEN_WRAPPER_ACCESSIBILITY=verified
TERMINAL_ACCESSIBILITY=verified
SSHD_AX_TRUST=verified
UTM_A=verified
```

任何缺失标记、`blocked` 标记或非零返回码都不是成功。

## 测试与验收

先写失败测试，再实现最小代码。自动化测试至少覆盖：

- 精确 VM 名称、库存/bundle/UUID/MAC、运行态和唯一 IP 的接受与拒绝路径。
- 代码静态保证不存在 `utmctl start|stop|restart`、TCC 数据库写入、`tccutil`、ChatGPT/Codex 点击目标、密码 argv/环境变量/剪贴板/输出以及固定坐标表。
- PTY 只响应一次唯一密码提示，且公开结果不含密码。
- OCR 唯一性、置信度、行到开关的动态关联、开/关分类、授权对话框唯一性和用户名匹配。
- 每个 GUI 动作后至少三秒再截图，最终两轮新截图均通过。
- 新 SSH 进程的 `AXIsProcessTrusted=true` 是独立成功门禁。
- `skills/utm-a/SKILL.md`、`agents/openai.yaml`、`STANDALONE`、安装软链接、21 主线顺序不变以及项目详细技能合同。
- `python3 /Users/yehailin/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/yehailin/Documents/mac提审自动化/skills/utm-a` 通过。

真实运行验收只能针对用户明确给出的、已运行的精确 VM；测试或验证不得自行启动、切换或重启 VM。若没有安全的真实目标，本轮只声明离线合同通过，不得把它表述成客体权限已实际开启。
