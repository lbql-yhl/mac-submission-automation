# utm-key

所属阶段：环境准备。可人工单独执行。

```bash
/usr/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_9.py --run-id '<run-id>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
/usr/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_9.py --page-title '<page-title>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
```

两个选择器二选一。只运行以上唯一宿主入口，不读取或解释脚本内容。终端只显示 `开始执行：utm-key`、`执行成功：utm-key；UTM_9=verified` 或 `执行报错：utm-key；<非敏感原因>`。成功后交接 `utm-apps`。
