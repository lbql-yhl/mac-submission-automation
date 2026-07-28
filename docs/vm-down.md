# vm-down：无视觉共享与持久系统设置

## 输入

继承 `utm-3` 的同一 run、VM 名称、IP、config UUID、最终管理员和 `SSH_KEY_AUTH=verified`。共享路径只读取当前 `${SUBMISSION_SHARED_DIR}`；模板与目标 UUID 从各自 config.plist 获取。

## 执行

1. 用最终管理员的 BatchMode SSH 执行 `/sbin/shutdown -h now`，再用 `utmctl status` 等待 stopped。
2. UTM 进程不运行时，调用 `scripts/utm_registry_share.py sync` 与 `verify`。它只复制模板内同路径的既有只读 bookmark 到当前 UUID，并输出 `UTM_SHARE_READONLY=verified`。
3. 不启动或打开克隆 VM；共享同步完成后，只有在外部已启动同一 VM 时才用新的 BatchMode SSH 核对最终用户/admin、精确共享路径和只读写入探针。
4. 以 root 安装 bootstrap shell、系统 LaunchDaemon 和每用户 LaunchAgent；重启后用 SSH 回读 Remote Login、pmset、daemon 结果和 `idleTime=0`。

## 成功证据

```text
UTM_SHARE_READONLY=verified
MOUNT_PATH=/Volumes/My Shared Files/共享文件
READONLY_PROBE=verified
REMOTE_LOGIN_PERSISTENCE=verified
PMSET_PERSISTENCE=verified
SCREENSAVER_IDLETIME=0
VM_DOWN=verified
```

## 恢复边界

关机、Registry、挂载/只读、服务/电源设置各做三轮同一对象的诊断、可安全修复和独立回读。bookmark 不存在、多项、路径不匹配或共享可写时不修改其它 UUID 项。所有动作和检查只通过 UTM CLI/Registry、SSH 与命令回读完成。
