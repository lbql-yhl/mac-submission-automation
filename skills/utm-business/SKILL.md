---
name: utm-business
description: Use when the environment-preparation segment reaches business setup or this skill is explicitly requested.
---

# utm-business

所属阶段：环境准备。本技能可人工单独指定执行。

## 执行

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_business.py \
  --run-id '<run-id>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
```

人工单独执行也可改用精确页面：

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_business.py \
  --page-title '<page-title>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
```

两个选择器二选一。操作者只运行以上唯一宿主入口，不读取或解释脚本内容，不调用内部脚本或中间步骤。执行失败并修复后，重新运行同一入口。

## 输出与交接

终端只显示 `开始执行：utm-business`、`执行成功：utm-business；UTM_BUSINESS=verified` 或 `执行报错：utm-business；<非敏感原因>`。

成功后结束本段；需要继续下一段时交接 `utm-env`。
