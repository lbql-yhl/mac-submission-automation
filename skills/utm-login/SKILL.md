---
name: utm-login
description: Use when the environment-preparation segment reaches account login or this skill is explicitly requested.
---

# utm-login

所属阶段：环境准备。本技能可人工单独指定执行。

## 执行

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_7_login.py \
  --parent-title '<parent-title>' \
  --page-title '<page-title>' \
  --vm-ip '<vm-ip>' \
  --vm-user '<vm-user>'
```

主线和人工单独执行均使用以上命令并传入当前目标参数。操作者只运行以上唯一宿主入口，不读取或解释脚本内容，不调用内部脚本或中间步骤。执行失败并修复后，重新运行同一入口。

## 输出与交接

终端只显示 `开始执行：utm-login`、`执行成功：utm-login；UTM_7=verified` 或 `执行报错：utm-login；<非敏感原因>`。

成功后交接 `utm-edit`。
