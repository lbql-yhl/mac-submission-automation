# utm-edit

所属阶段：环境准备。可人工单独执行。

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_8_change_password.py \
  --page-title '<page-title>' --vm-name '<vm-name>' \
  --vm-ip '<vm-ip>' --vm-user '<vm-user>'
```

只运行以上唯一宿主入口，不读取或解释脚本内容。终端只显示 `开始执行：utm-edit`、`执行成功：utm-edit；UTM_8=verified` 或 `执行报错：utm-edit；<非敏感原因>`。成功后交接 `utm-key`。
