---
name: utm-business
description: Use when the prepared App Store Connect application needs its business and banking setup verified in the same UTM guest.
---

# utm-business

执行约束：[`../_shared/AUTOMATION_CONTRACT.md`](../_shared/AUTOMATION_CONTRACT.md)。

收到执行请求后，直接运行下面对应的公开命令。禁止在执行前打开、搜索、检查或分析任何技能与脚本源码；不解释、不判断流程，只报告脚本输出。

## 使用 run-id 执行

```bash
eval "$(python3 scripts/preflight.py --project-only --emit-shell)"
python3 "$PROJECT_ROOT/scripts/utm_business.py" \
  --run-id '<run-id>' \
  --vm-name '<vm-name>' \
  --vm-ip '<vm-ip>' \
  --vm-user '<vm-user>'
```

## 使用 page-title 执行

```bash
eval "$(python3 scripts/preflight.py --project-only --emit-shell)"
python3 "$PROJECT_ROOT/scripts/utm_business.py" \
  --page-title '<page-title>' \
  --vm-name '<vm-name>' \
  --vm-ip '<vm-ip>' \
  --vm-user '<vm-user>'
```
