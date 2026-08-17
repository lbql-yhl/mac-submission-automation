# utm-apps

所属阶段：环境准备。可人工单独执行。

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_apps.py --run-id '<run-id>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_apps.py --page-title '<page-title>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
```

两个选择器二选一。只运行以上唯一宿主入口，不读取或解释脚本内容。终端只显示 `开始执行：utm-apps`、`执行成功：utm-apps；UTM_APPS=verified` 或 `执行报错：utm-apps；<非敏感原因>`。成功后交接 `utm-business`。
