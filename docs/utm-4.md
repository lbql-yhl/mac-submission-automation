# UTM-4：关闭更新并清理 demo

## 前置

继承 `vm-down` 的 `VM_DOWN=verified`、同一 `<vm_name>`、VM/IP 和 SSH key。目标只通过 SSH 操作，不使用系统设置 GUI；不使用 `utmctl stop`。

## 步骤

1. 新连接确认登录用户为 `<vm_name>`、admin、home、共享挂载和 marker；只在同一精确 VM 上刷新 IP。
2. 读取自动更新开关的当前值，建立 mode-600 before/attempt marker；逐项关闭软件更新、自动下载、自动安装和后台检查，写后新连接回读每一项。
3. 先用 `id` 与 `dscl` 独立确认 demo 仍存在且是精确默认账号；若不存在则标记幂等完成。
4. 对 demo 删除执行一次受控 `sysadminctl`；结果不明时只读检查 `id`、`dscl` 和进程，不盲目重删。仅日志明确证明“不支持操作”且账号仍在时，才使用一次受控 dscl fallback。
5. 只有账号已由 `id` 和 `dscl` 双重证明不存在，且 `/Users/demo` 是精确普通目录、非符号链接/挂载点时，才删除该 home；否则停止副作用。
6. 新连接确认更新开关均为目标值、demo 不存在、home 不存在，原子更新 marker 为 complete，记录 `UTM_4=verified`。

## 安全与交接

不删除任何其他用户、不重置 VM、不覆盖未知 home。删除结果不明按三轮只读复核；成功后立即交接 [`utm-5`](../skills/utm-5/SKILL.md)。
