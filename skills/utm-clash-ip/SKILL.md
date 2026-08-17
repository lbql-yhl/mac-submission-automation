---
name: utm-clash-ip
description: Use when the environment-preparation segment reaches Clash/IP setup or this skill is explicitly requested.
---

# utm-clash-ip

所属阶段：环境准备。本技能可人工单独指定执行。

## 执行

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_clash_ip.py \
  --vm-name '<vm-name>' \
  --application-name '<app-name>' \
  --vm-ip '<vm-ip>' \
  --parent-title '<parent-title>' \
  --page-title '<page-title>'
```

主线和人工单独执行均使用以上命令并传入当前目标参数。操作者只运行以上唯一宿主入口，不读取或解释脚本内容，不调用内部脚本或中间步骤。执行失败并修复后，重新运行同一入口。

## 输出与交接

终端只显示 `开始执行：utm-clash-ip`、`执行成功：utm-clash-ip；UTM_CLASH_IP=verified` 或 `执行报错：utm-clash-ip；<非敏感原因>`。

成功后交接 `utm-login`。
