# UTM-1：同一克隆的共享、网络、启动与视觉登录

对应技能：`utm-1`。它只能继承 `utm-clone-macos` 已验证的同一 `run_id`、`vm_name`、VM bundle 和 clone marker；不选择“最新”VM，不改模板 `macOS`，不改 CPU、内存、磁盘、显示或启动项，也不自动启动或打开克隆机。目标必须在本技能开始前已经运行。

## 可恢复边界

开始时建立 `${PROJECT_ROOT}/runtime/utm-1-attempts/<run_id>.json`，文件 mode `600`、目录 mode `700`。账本绑定 run、四字母 VM 名、bundle、config UUID、规范化共享目录和 clone marker SHA-256，输出 `UTM_1_ATTEMPT_ID`、`UTM_1_ATTEMPT_MODE=600`。阶段必须依次为：

```text
handoff_verified → sharing_verified → network_verified
→ running_verified → login_verified → UTM_1=verified
```

恢复时先读 `next`：已验证阶段只轻量回读；未验证阶段从该阶段继续。任何目标未运行或状态不明都只读复核并进入故障出口，绝不启动或打开克隆机。

## 操作与证据

1. 两次读取同一 `utmctl status <vm_name>`，目标必须在本技能开始前已为 `started/running`；核对 config UUID 与 clone marker 后记录 `handoff_verified`。
2. 在 UTM GUI 的同一 VM 执行 Edit → Sharing。共享目录只允许规范化路径的一条只读记录；保存后重新打开同一页和结构化 preferences 双重回读，记录 `SHARING_MATCH_COUNT=1`、`SHARING_READ_ONLY=verified` 和 `sharing_verified`。
3. 在同一 Edit → Network 对 `Random` 做三次独立“点击、等待 3 秒、保存、读取 config”闭环。每轮 MAC 必须与前一轮不同，只记录 `MAC_0_SHA256` 至 `MAC_3_SHA256`；config UUID 不得变化。成功记录 `NETWORK_RANDOM_ROUNDS=3`、`NETWORK_MAC_CHANGED=verified` 和 `network_verified`。
4. 只读确认同名、同 config UUID 的 VM 在本技能开始前已为 `running` 后记录 `running_verified`。目标 `stopped` 或状态不明时不启动，只做三轮状态/UUID/控制台复核并记录 `CLONE_START_GUARD=blocked`；正常接管成功记录 `CLONE_START_GUARD=verified`。
5. 登录始终保留视觉操作：UTM 控制台必须显示目标 VM 的 macOS 登录页和 `demo`。通过四次独立按键输入固定 VM 密码，四个圆点后仅提交一次。成功必须同时看到菜单栏、访达和用户菜单 `demo`，才记录 `LOGIN_USER=demo`、`LOGIN_DESKTOP=verified`、`login_verified` 与 `UTM_1=verified`。

共享目录重复且不能证明由当前 attempt 创建、config UUID 漂移、目标 VM 不唯一、启动结果三轮仍不明或登录状态无法分类时，暂停新副作用，按共享恢复合同完成三轮证据核对后才进入最后故障卡。正常路径不等待人工确认，完成后立即交接 `utm-2`。
