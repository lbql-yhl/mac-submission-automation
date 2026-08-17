# utm-env

所属阶段：脚本准备、执行。可人工单独执行，也是本段入口。

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_env.py \
  --parent-title '<parent-title>' --app-name '<app-name>' \
  --vm-ip '<vm-ip>' --vm-user '<vm-user>'
```

只运行以上唯一宿主入口，不读取或解释脚本内容。终端只显示 `开始执行：utm-env`、`执行成功：utm-env；UTM_ENV=verified` 或 `执行报错：utm-env；<非敏感原因>`。成功后交接 `utm-script`。
