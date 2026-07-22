# apple-store-bm

这是桌面共享目录中的 App Store 批处理工具运行包。

## 已验证文件

- `apple_store_tools`：Mach-O 64-bit `arm64` 可执行文件，适用于 Apple Silicon macOS。
- `config/prod.example.yml`：只含占位符的配置结构。
- 可执行文件 SHA-256：`0e246e1dc86ea8f1ac0edced28d8abd4419104e896437457f5bb166de2202ab2`。

原桌面说明写的是 Intel/x86_64，但当前实际二进制经 `file` 验证为 arm64，本仓库按实物修正说明。

## 安全边界

- 真实 `config/prod.yml` 和 P8 私钥只能在运行时本地生成，不能上传 Git。
- 工具由当前技能流程调用；不要脱离 run、App ID、Key ID、P8 归属和幂等检查手动运行批量命令。
- 运行时保持 `apple_store_tools` 与 `config/` 同级，并保持可执行权限。
