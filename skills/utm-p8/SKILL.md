---
name: utm-p8
description: Use when the script-preparation and execution segment reaches P8 registration or this skill is explicitly requested.
---

# utm-p8

所属阶段：脚本准备、执行。本技能可人工单独指定执行。

## 执行

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_p8.py \
  --run-id '<run-id>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
```

人工单独执行也可改用精确页面：

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_p8.py \
  --page-title '<page-title>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
```

只清理本地共享文件时，在精确页面命令末尾追加 `--cleanup-only`，并省略 `--vm-ip`、`--vm-user`。该模式只按页面中的当前应用名处理四项本地临时文件，不要求 VM 运行，也不连接 VM 或 Notion。

两个选择器二选一。操作者只运行以上唯一宿主入口，不读取或解释脚本内容，不调用内部脚本或中间步骤。执行失败并修复后，重新运行同一入口。

## 输出与交接

终端只显示 `开始执行：utm-p8`、`执行成功：utm-p8；UTM_P8=verified`、清理模式的 `执行成功：utm-p8；SHARED_APP_ASSETS_CLEANED=verified` 或 `执行报错：utm-p8；<非敏感原因>`。

成功标记同时证明唯一入口已按当前应用名精确清理共享目录中的应用目录、`-git` 目录、`.png` 和 `.xlsx` 四项临时文件，并记录 `SHARED_APP_ASSETS_CLEANED=verified`；其他共享内容不处理。

成功后结束本段；需要继续下一段时交接 `utm-21`。
