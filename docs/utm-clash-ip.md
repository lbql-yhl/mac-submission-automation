# utm-clash-ip

所属阶段：环境准备。可人工单独执行。

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_clash_ip.py \
  --vm-name '<vm-name>' --application-name '<app-name>' --vm-ip '<vm-ip>' \
  --parent-title '<parent-title>' --page-title '<page-title>'
```

只运行以上唯一宿主入口，不读取或解释脚本内容。终端只显示 `开始执行：utm-clash-ip`、`执行成功：utm-clash-ip；UTM_CLASH_IP=verified` 或 `执行报错：utm-clash-ip；<非敏感原因>`。成功后交接 `utm-login`。
