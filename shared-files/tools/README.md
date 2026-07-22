# 第三方工具链

桌面共享目录当前包含完整 Flutter checkout 和缓存，合计约 3.9GB。它是可重建的第三方依赖，不提交到 GitHub。

当前机器记录：

- Flutter：`3.24.5`
- Engine revision：`a18df97ca57a249df5d8d68cd0820600223ce262`

迁移时安装匹配版本到 `${SUBMISSION_SHARED_DIR}/tools/flutter`，再由项目预检和 `utm-21` 实际验证 `flutter`、依赖解析与 iOS/CocoaPods 环境。不要复制旧机器的 Flutter cache 或嵌套 `.git` 作为项目源码。
