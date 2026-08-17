---
name: utm-apps
description: Use when the environment-preparation segment reaches UTM Apps or this skill is explicitly requested.
---

# utm-apps

按 run-id 运行：

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_apps.py \
  --run-id '<run-id>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
```

按页面运行：

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_apps.py \
  --page-title '<page-title>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
```
