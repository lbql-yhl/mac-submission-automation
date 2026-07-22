# 桌面共享项目文件

本目录保存 `/Desktop/共享文件` 中属于项目源码或不可重建工具的部分，用于私有仓库备份和跨机器恢复。运行时目标目录仍由 `.env` 的 `SUBMISSION_SHARED_DIR` 决定，不能写死旧机器路径。

## 已纳入仓库

- `Fire_One_en1.2/`：`utm-18` 使用的 TypeScript 源码、依赖锁文件和无凭据配置示例。
- `apple-store-bm/`：当前 arm64 批处理二进制、说明和无凭据配置模板。
- `tools/README.md`：当前 Flutter 工具链版本记录和重建说明。

## 只保留在本机运行时

- 根目录和子项目的真实 `.env`。
- `socks5.yml`、`config/prod.yml`、P8、证书、账号、联系人、代理和 token。
- `node_modules/`、Flutter SDK/cache、构建输出、日志和 `.DS_Store`。

这些文件不是遗漏：`.env` 由 `utm-16` 生成，`socks5.yml` 由 `utm-5` 生成，P8/生产配置按后续技能的安全流程创建；Node 依赖用锁文件恢复，Flutter 是第三方 SDK。

## 新机器恢复

1. 先按根目录 README 创建新机器自己的项目 `.env` 并运行项目预检。
2. 将本目录内容合并复制到 `${SUBMISSION_SHARED_DIR}`；不要删除该目录已有的本机凭据或运行文件。
3. 在 `${SUBMISSION_SHARED_DIR}/Fire_One_en1.2` 执行 `npm ci`。
4. 按 `tools/README.md` 安装匹配 Flutter SDK，再由对应技能生成运行时敏感文件并逐项回读验证。

仓库中的共享文件均小于 GitHub 单文件 100 MiB 限制；3.9GB 的 Flutter checkout/cache 不进入 Git。
