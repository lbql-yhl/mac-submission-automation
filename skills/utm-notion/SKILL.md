---
name: utm-notion
description: Use when the environment-preparation segment or this skill is explicitly requested.
---

# utm-notion

所属阶段：环境准备。本技能可人工单独指定执行，也是本段入口。

## 执行

按 run 执行：

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_notion.py --run-id '<run-id>'
```

按应用人工单独执行：

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_notion.py --app-name '<app-name>' --vm-name '<vm-name>'
```

两个选择器二选一。操作者只运行以上唯一宿主入口，不读取或解释脚本内容，不调用内部脚本或中间步骤。执行失败并修复后，重新运行同一入口。

## 输出与交接

终端只显示 `开始执行：utm-notion`、`执行成功：utm-notion；status=verified` 或 `执行报错：utm-notion；<非敏感原因>`。

成功后交接 `utm-clash-ip`。
