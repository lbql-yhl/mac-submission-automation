# utm-p8

所属阶段：脚本准备、执行。可人工单独执行。

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_p8.py --run-id '<run-id>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_p8.py --page-title '<page-title>' --vm-name '<vm-name>' --vm-ip '<vm-ip>' --vm-user '<vm-user>'
```

两个选择器二选一。只运行以上唯一宿主入口，不读取或解释脚本内容。终端只显示 `开始执行：utm-p8`、`执行成功：utm-p8；UTM_P8=verified` 或 `执行报错：utm-p8；<非敏感原因>`。成功后结束本段；需要继续时交接 `utm-21`。
