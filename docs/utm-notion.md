# utm-notion

所属阶段：环境准备。可人工单独执行，也是本段入口。

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_notion.py --run-id '<run-id>'
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_notion.py --app-name '<app-name>' --vm-name '<vm-name>'
```

两个选择器二选一。只运行以上唯一宿主入口，不读取或解释脚本内容。终端只显示 `开始执行：utm-notion`、`执行成功：utm-notion；status=verified` 或 `执行报错：utm-notion；<非敏感原因>`。成功后交接 `utm-clash-ip`。
