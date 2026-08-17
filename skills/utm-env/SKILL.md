---
name: utm-env
description: Use when the script-preparation and execution segment or this skill is explicitly requested.
---

# utm-env

所属阶段：脚本准备、执行。本技能可人工单独指定执行，也是本段入口。

## 执行

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_env.py \
  --parent-title '<parent-title>' \
  --app-name '<app-name>' \
  [--asset-app-name '<Feishu源应用名>'] \
  --vm-ip '<vm-ip>' \
  --vm-user '<vm-user>'
```

主线和人工单独执行均使用以上命令并传入当前目标参数。Feishu Base 的源应用名与当前应用名不同时传入 `--asset-app-name`；一致时省略。操作者只运行以上唯一宿主入口，不读取或解释脚本内容，不调用内部脚本或中间步骤。执行失败并修复后，重新运行同一入口。

## 输出与交接

终端只显示 `开始执行：utm-env`、`执行成功：utm-env；UTM_ENV=verified` 或 `执行报错：utm-env；<非敏感原因>`。

成功后交接 `utm-script`。
