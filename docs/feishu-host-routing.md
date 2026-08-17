# 飞书宿主路由

本文只记录宿主路由配置，不重复技能或脚本流程。

## 配置

每台宿主机在自己的 `.env` 中设置唯一：

```env
SUBMISSION_HOST_MACHINE=<宿主机名称>
FEISHU_APP_ID=
FEISHU_APP_SECRET=
NOTION_TOKEN=
NOTION_ROOT_PAGE_ID=
```

不要复制其他宿主机的 `.env`、运行历史、VM 绑定或凭据。

## 检查

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/preflight.py --json
curl http://127.0.0.1:8787/health
```

宿主名、应用、VM 和 Notion 页面必须精确匹配；禁止按“最新”或模糊名称路由。

## 消息边界

- 提审启动入口当前禁用。
- 日报专用群只允许用户确认后的日报。
- 其他群的已有运行状态和故障卡按项目规则处理。
