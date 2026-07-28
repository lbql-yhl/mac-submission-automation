# UTM-3：创建最终管理员账号

## 前置与输入

继承 `utm-2` 的同一 VM/IP、`UTM_2=verified`、demo BatchMode 和宿主公钥。用户名只能是当前 run 生成的 `<vm_name>`，固定密码仅通过 `OP-FIXED-PASSWORD-1234` 输入。

## 步骤

1. 新 SSH 连接只读确认 guest 为 demo、系统版本、admin 组和当前 run marker；失败时只恢复同一 VM 的 SSH，不改选目标。
2. 读取账号 marker 和 `dscl`/`id`/home/admin/Secure Token/key 指纹。完整匹配且 marker 属于当前 run 时记录 `UTM_3_USER_PRECHECK=resume_verified`，从第一个缺失项继续。
3. 仅当用户不存在且没有外部同名冲突时，以 SSH `sudo` 创建 `<vm_name>`、设置 home 和 admin；固定密码只进入已识别的 sudo 提示，绝不进 argv/日志。
4. 用两次独立连接确认 UID、home、admin、Secure Token 状态和 run marker；账号已存在但属性冲突时禁止删除或猜测。
5. 将同一宿主公钥安装到最终用户 `authorized_keys`，校验权限、SHA-256 指纹和 `BatchMode=yes`。
6. 原子写入完成 marker，确认 `ACCOUNT_MARKER=verified`、`ACCOUNT_IDENTITY=verified`、`ACCOUNT_ADMIN=verified`、`SSH_KEY_AUTH=verified` 后记录 `UTM_3=verified`。

## 交接

所有命令结果不明先只读复核，不重复 `addUser`；SSH 修复三轮仍失败或出现外部同名冲突才发最后故障卡。成功后立即交接 [`vm-down`](../skills/vm-down/SKILL.md)，不得等待用户。
