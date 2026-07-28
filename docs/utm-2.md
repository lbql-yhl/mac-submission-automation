# utm-2：无视觉 SSH 与 guest 身份

## 输入

继承同一 run 的 `vm_name`、bundle、config UUID 与 `UTM_1=verified`。唯一网络锚点是 config 中的 `Network[0].MacAddress`；不得采用固定子网、最新 VM 或名称相似项。

## 执行

1. 从 ARP、受支持的 `utmctl ip-address` 与同一 UTM lease 取规范 MAC 的唯一交集，记录 `VM_IP_MATCH=verified`。
2. 以 `nc` 和 SSH banner 检查 22；已有 SSH 通道时用 `systemsetup -setremotelogin on`，新会话回读 `Remote Login: On`。
3. 复用或建立宿主 key，只在 BatchMode 失败时通过 PTY 执行 `ssh-copy-id`，回读权限、指纹和 `demo` 身份。
4. 用新 BatchMode SSH 读取当前 guest 的 `ioreg` 两项身份和 `ifconfig` MAC；不启动、不打开源模板，也不从克隆机反向读取模板基线，只与当前 run、当前配置 MachineIdentifier 和历史登记逐项比较，再原子更新身份登记。

## 成功证据

```text
VM_CONFIG_MAC=verified
IP_CANDIDATE_INTERSECTION_COUNT=1
VM_IP_MATCH=verified
REMOTE_LOGIN=verified
SSH_SERVICE=verified
SSH_DEMO_KEY=verified
TEMPLATE_GUEST_IDENTIFIERS=not_required_by_policy
GUEST_IDENTIFIER_LINES=2
GUEST_MAC_MATCH=verified
GUEST_IDENTITY_DIFF=verified
UTM_2=verified
```

## 恢复边界

MAC→IP、22、key、三码各自最多三轮同一 VM 诊断与独立回读。无 SSH 连接时只能报告 `SSH_AUTO_RECOVERY=blocked` 并走最后故障卡，不得以其它方式宣称 Remote Login 已修复。所有证据均来自 UTM CLI/Registry、ARP、SSH 与命令输出。
