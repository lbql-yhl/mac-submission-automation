# UTM-5：生成 SOCKS5 配置

## 输入

继承 `UTM_4=verified`、同一 run/`vm_name`。代理四元组只能从 `runtime/feishu-runs.json` 当前 run 的 `submission_data.proxy` 读取；输出路径由 `preflight --emit-shell` 得到的 `${SUBMISSION_SHARED_DIR}/socks5.yml` 决定。

## 步骤

1. 预检固定 run、宿主机匹配和四个非空代理字段；IP、端口、用户名、密码只在内存变量中使用，不打印。
2. 生成标准 SOCKS5 YAML payload，检查字段语法和无额外文档/模板内容。
3. 对目标执行 `lstat`，捕获 before 字节和 mode；相同字节且 mode 600 时记录 `SOCKS5_WRITE=unchanged`，否则用同目录 mode-600 临时文件、fsync、原子 replace 写入。
4. 新进程重新读取同一 run，确认宿主机和 `vm_name` 没变；读取文件只校验四个字段的字节/哈希，不输出值。
5. 独立回读确认 mode 600、非符号链接、SHA-256 与预期完全一致，并记录 `SOCKS5_RUN_ID=exact_matched`、`SOCKS5_READBACK=exact`、`SOCKS5_OUTPUT=verified`、`UTM_5=verified`。

## 恢复与交接

写入失败先用 before 恢复并独立回读；run 在写入期间变化时只重读同一 run、重新生成一次，第二次竞争即 exhausted。禁止选择其他 run、显示代理凭据或覆盖未验证文件。成功后交接 [`files`](../skills/files/SKILL.md)。
