---
name: utm-script
description: Use when the script-preparation and execution segment reaches script execution or this skill is explicitly requested.
---

# utm-script

所属阶段：脚本准备、执行。本技能可人工单独指定执行。

## 执行

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_18.py \
  --run-id '<run-id>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
```

人工单独执行也可改用精确页面：

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_18.py \
  --page-title '<page-title>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
```

两个选择器二选一。操作者只运行以上唯一宿主入口，不读取或解释脚本内容，不调用内部脚本或中间步骤。执行失败并修复后，重新运行同一入口。

## 输出与交接

终端只显示 `开始执行：utm-script`、`执行成功：utm-script；UTM_18=verified` 或 `执行报错：utm-script；<非敏感原因>`。

成功后交接 `utm-image`。
