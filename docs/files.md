# Files：共享目录复制步骤

## 输入与前置

- 输入只来自同一 run 的 `vm_name`、已验证 VM/IP、宿主 SSH key，以及 guest `/Volumes/My Shared Files/共享文件`。
- 前置必须有 `UTM_5=verified`、`UTM_4=verified`、`SSH_KEY_AUTH=verified`；目标是同一 guest 用户的 `$HOME/Downloads`。
- 先执行 `eval "$(python3 scripts/preflight.py --project-only --emit-shell)"`，再做一次 `BatchMode=yes` 身份检查。

## 可执行步骤

1. 只读确认 guest 用户等于 `<vm_name>`、组包含 `admin`、共享源是非符号链接目录；不满足时不创建目录、不复制。
2. 在 guest 生成源 manifest，记录相对路径、类型、符号链接目标、字节数和 SHA-256；要求条目数大于 0，且 `socks5.yml` 是非空普通文件。
3. 读取当前 run 的 mode-600 copy marker，逐项比较 Downloads 目标：不存在或字节完全相同才可继续；不同且没有同一 attempt marker 的目标必须停止并记录冲突。
4. 原子写入绑定 run、`vm_name`、源 manifest 和 attempt 的 marker，独立新 SSH 会话回读，确认 `COPY_PREFLIGHT=verified`、`DEST_CONFLICTS=0`。
5. 通过 SSH `/usr/bin/ditto "$src/." "$dst/"` 复制全部内容（含隐藏项），不删除源或无关目标文件；命令退出后等待并重新建立 SSH 连接。
6. 新连接逐项比较路径类型、链接目标和 SHA-256；另一次新连接单独核对 `socks5.yml` 两端非空、非符号链接、非其他用户可写且哈希相同。
7. marker 原子更新为 `status=complete`，回读全部证据后记录 `FILES=verified`。

## 成功证据与恢复

必须同时有 `SOURCE_ENTRIES=>0`、`missing=0`、`mismatched=0`、`SOCKS5_COPY_HASH=verified`、`verification=passed`。复制中断只修复缺失/哈希不符且由同一 marker 授权的条目；三轮仍不一致才按共享合同发最后故障卡。

## 禁止与交接

禁止使用宿主路径、Finder GUI、删除源文件、覆盖未知冲突、打印代理密码。完成后立即把同一 run/VM/IP 交给 [`utm-clash`](../skills/utm-clash/SKILL.md)，不等待用户。
