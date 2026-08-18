---
name: utm-vm-clone
description: Use when the virtual-machine preparation segment or this skill is explicitly requested.
---

# utm-vm-clone

## 执行规则

收到开始、继续、重新执行或指定步骤后，立即运行对应命令。不得读取、搜索、解释或审查脚本正文；不得自行运行正文未列出的诊断命令。终端仅显示开始、最终成功或完整实际报错；不得显示内部检查、重试和步骤过程。`utm-vm-clone` 不对错误内容脱敏或截断。

普通执行只运行唯一总入口：

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_clone_and_initialize.py
```

总入口自动依次执行 10 步，失败只按 0/5/10 秒重跑当前步骤；已验证步骤实时复验后跳过副作用。
若活动指针对应的 VM 已绑定其他应用，视为已绑定其他应用的陈旧活动指针，由总入口自动清除并创建新 VM；其他库存异常仍阻断，操作者不得手工删除活动文件。
步骤 1 在复制前检查目标卷可用空间，至少覆盖模板实际占用与 5 GiB 安全余量；不足时在创建目标目录前失败。
新 VM 注册后由步骤 1 最多 30 秒条件复验：UTM CLI 必须唯一且为 `stopped`，Registry 域可用时再与 Registry 的精确包路径交叉验证；Registry 域不可用时不得伪造一致结果，也不得手工选 VM。
步骤 3 读取共享目录注册时，`defaults export` 为空则从同域的直接 plist 读回；仍须精确匹配当前 VM 的 UUID、名称、包路径和唯一只读共享目录。UTM-1 三轮随机 MAC 完成并严格读回后，必须立即把最终 config MAC 幂等同步到当前 VM 的库存 `mac_address`/`guest_mac_address`；已完成步骤的复验也执行同一同步，避免后续依赖检查因陈旧库存 MAC 把全部来宾项误报为未安装。
需要从 `stopped` 恢复目标 VM 时，先启动 UTM 应用并等待就绪，再由宿主 AX 锁定精确 bundle 对应窗口和 Run/Start 按钮；同时存在库详情窗口与控制台时优先库详情窗口的 `play.circle.fill`，`starting` 只作为中间态轮询，最终必须读回运行态。
SSH 子步骤必须使用共享 `OP-CONFIGURED-GUEST-PASSWORD`，唯一密码来源是宿主 `.env` 的 `SUBMISSION_GUEST_PASSWORD`，不得写死、询问或回显。失败必须同时保留 SSH stdout 与 stderr，禁止只回显 `CalledProcessError` 而丢失远端根因。
步骤 9 必须经 SSH 直接运行来宾 `/usr/bin/python3 -B - --vm-user ...`，不得套用同 UID 会失败的 `launchctl asuser`，也不得使用 `sudo`。App Management 已打开但为空时，来宾 AX 流程必须唯一定位 Add 按钮；Add 后只接受唯一密码/Modify Settings 认证面板，或认证已缓存而直接出现唯一 Open 面板。需要认证时完成认证，然后在文件选择器精确选择 `/System/Applications/Utilities/Terminal.app`，再严格读回唯一 Terminal 行及已启用开关；任何节点不唯一或读回不一致均关闭失败。禁止直接写 TCC.db 或使用 `tccutil reset`。
步骤 7 发现未安装项时必须在错误中列出具体标签，不得只返回笼统的 `DEPENDENCY_CHECK_NOT_ALL_INSTALLED`。
步骤 6 已完成后的复验必须调用来宾侧 `verify_copy` 做清单读回；总协调模块必须显式导出该函数，不能只在首次 `copy_shared` 路径可用。
步骤 4 用限定当前用户和完整 `-MiniBuddyYes` 命令行的 `pgrep -f` 识别 Accessibility MiniBuddy；已完成步骤复验只对白名单状态（精确的 loginwindow `root/missing/absent`，或目标用户的 Finder/MiniBuddy 已知过渡状态）调用精确目标的幂等桌面恢复流程，其他状态关闭失败。登录前必须读回 `/Library/Preferences/com.apple.loginwindow` 的 `SHOWFULLNAME`：值为真时，在精确 UTM 窗口焦点和 Capture Input 均已读回后，用短间隔纯键盘执行“清名称、用户名、Return、清密码、当次配置的 guest 密码、Return”，不得依赖无法进入来宾的宿主定向鼠标事件；值为假时才使用已验证的选中用户分支。完成后严格读回目标控制台用户、Finder 和 Setup Assistant 状态。

## 故障步骤入口

只有用户明确要求重跑某一步，或总入口报出该步骤失败且已完成修复时，才使用当前活动克隆的精确四位小写 `<vm_name>` 运行对应入口：

1. `/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_vm_clone_step_01_clone.py`
2. `/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_vm_clone_step_02_account.py --vm-name '<vm_name>'`
3. `/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_vm_clone_step_03_hardware.py --vm-name '<vm_name>'`
4. `/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_vm_clone_step_04_desktop.py --vm-name '<vm_name>'`（首次桌面引导）
5. `/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_vm_clone_step_05_settings.py --vm-name '<vm_name>'`
6. `/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_vm_clone_step_06_delivery.py --vm-name '<vm_name>'`
7. `/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_vm_clone_step_07_dependencies.py --vm-name '<vm_name>'`（调用 `/Users/yehailin/Documents/mac提审自动化/scripts/check_host_vm_dependencies.py` 验证 26 项）
8. `/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_vm_clone_step_08_accessibility.py --vm-name '<vm_name>'`
9. `/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_vm_clone_step_09_app_management.py --vm-name '<vm_name>'`
10. `/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_vm_clone_step_10_finalize.py --vm-name '<vm_name>'`

不得跳过前置步骤、选择“最新”或其他 VM，也不得直接调用任何内部 helper。

## 输出与交接

总入口成功必须输出 `执行成功：utm-vm-clone；UTM_CLONE_AND_INITIALIZE=verified`。步骤入口成功必须输出对应的 `步骤X已操作` 或 `步骤X已完成，跳过`，以及 `STEP_01_CLONE=verified` 至 `STEP_10_FINALIZE=verified`。失败输出 `步骤X故障：<非敏感原因>` 和最终报错。

成功后结束本段；用户要求继续主线时交接 `utm-notion`。
