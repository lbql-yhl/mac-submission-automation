---
name: utm-edit
description: Use when the environment-preparation segment reaches account editing or this skill is explicitly requested.
---

# utm-edit

所属阶段：环境准备。本技能可人工单独指定执行。

## 执行

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_8_change_password.py \
  --page-title '<page-title>' \
  --vm-name '<vm-name>' \
  --vm-ip '<vm-ip>' \
  --vm-user '<vm-user>'
```

主线和人工单独执行均使用以上命令并传入当前目标参数。操作者只运行以上唯一宿主入口，不读取或解释脚本内容，不调用内部脚本或中间步骤。执行失败并修复后，重新运行同一入口。

## 输出与交接

终端只显示 `开始执行：utm-edit`、`执行成功：utm-edit；UTM_8=verified` 或 `执行报错：utm-edit；<非敏感原因>`。

成功后交接 `utm-key`。
