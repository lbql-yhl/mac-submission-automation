# UTM-6：验证代理出口并写入 guest 环境

## 前置

继承 `utm-clash` 的同一 VM/IP、`vm_name`、`SSH_KEY_AUTH=verified`、选中的 `socks5.yml` 和 Clash 固定开关；先做一次 BatchMode 身份检查。

## 步骤

1. 从当前 Feishu run 只读取得注册代理 IP；在 guest 通过 `curl`/项目允许的出口检查取得公网 IPv4。必须与注册 IP 完全相等才记录 `PROXY_EGRESS=verified`。
2. 不相等或请求失败时按 5/15/30 秒重读同一代理、profile、Clash 进程和监听端口；必要时只重启同一 Clash 一次。三轮仍不匹配才停止。
3. 读取 guest `~/.zshrc` before，按项目固定 Ruby/Flutter/Pub 环境变量生成目标文本；只改本技能管理的行，使用临时文件+fsync+原子 replace。
4. 新 SSH 连接 source `.zshrc`，逐行检查变量、PATH 和运行时 `ruby/flutter/dart/pub` 值；失败时用 before 恢复并确认 `ZSHRC_ROLLBACK=verified`。
5. 记录 `ZSHRC_WRITE=atomic_verified`、`ZSHRC=verified`、`UTM_6=verified`，立即交接 `utm-7`。

禁止打印代理用户名/密码、修改其他 shell 配置或在出口不等时继续；恢复穷尽才发最后故障卡。
