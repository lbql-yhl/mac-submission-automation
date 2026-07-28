# UTM-Clash：配置 Clash Verge 与代理 Profile

## 前置与输入

继承 `FILES=verified`、同一 guest 用户 `<vm_name>`、VM/IP 和 SSH key；guest 目标必须是 `$HOME/Downloads/socks5.yml`，不能使用宿主路径。先执行项目预检并做一次 BatchMode 检查。

## SSH 配置步骤

1. 在 guest `~/Library/Application Support` 下枚举包含非符号链接 `verge.yaml` 和 `config.yaml` 的候选目录，要求唯一 `CONFIG_DIR_MATCH_COUNT=1`。
2. 关闭同一 guest 的 Clash Verge（等待 3 秒并确认进程退出），保存两个配置 before；只修改固定开关：Tun on、System Proxy off、Auto Launch on、Silent Start on、IPv6 off、Unified Delay on。
3. 用临时文件+fsync+原子 replace 写入；逐 key 回读，失败立即用 before 恢复。重新启动 Clash Verge，确认 `CLASH_PROCESS=verified`、runtime TUN enabled。

## Profile 与 GUI 步骤

1. 通过 SSH 再次确认 `Downloads/socks5.yml` 为非空普通文件且哈希与 `files` 证据一致。
2. 在 guest Clash Verge 的 Profiles 执行本地文件 Import，选择 `/Users/<vm_name>/Downloads/socks5.yml`，等待列表出现后选中唯一该 profile。
3. 在 Proxies 的 `PROXY` 组选择 `My-SOCKS5-Proxy`；每次点击后等待至少 3 秒、读取新截图，成功证据是右侧 check 变为延迟数字。
4. 最终逐项回读 Tun/System Proxy/Auto Launch/Silent Start/IPv6/Unified Delay 和已选 profile；记录 `CONFIG_WRITE=atomic_verified`、`RUNTIME_TUN=verified`、`PROFILE=verified`、`UTM_CLASH=verified`。

## 恢复与交接

菜单误点用 Escape 回到 Profiles；五次选择失败才重读窗口/配置并只重启一次。SSH 失败只恢复同一 VM 三轮；禁止启动其他 VM、改写代理内容、操作宿主浏览器或跳过 profile 导入。成功后交接 [`utm-6`](../skills/utm-6/SKILL.md)。
