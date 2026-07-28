# notion-utm：创建 Notion 虚拟机登记页

## 输入来源

从项目 Feishu bot runtime/API 读取同一 `run_id` 的应用名、宿主机名、`vm_name` 和账号登记；Notion 只通过 `scripts/notion_api.py`。`NOTION_ROOT_PAGE_ID` 必须是当前宿主机页，不能是流程主页或历史页。

## 步骤

1. 运行项目预检，并用 `verify-parent --title '<宿主机名称>'` 确认唯一父页。
2. 重新读取同一 run，校验固定登记模板；银行区块可以省略或为空，但账号国家、邮箱、初始密码、电话和短信链接缺失时不得猜测。
3. 在父页下查询标题恰为 `模板` 的唯一 child。多条、无条或父页不一致时只读恢复，不选第一条。
4. 保存模板页 before 内容；通过 API 创建 `<应用名>-<vm_name>`，不得从浏览器/Notion 插件写入。
5. 按固定 33 行格式生成 `账号信息`，原子写入并立即用 API 读取；保持 `应用信息` 空白，银行标签保留但可为空。
6. 用字节数/SHA-256 对 before/after 和页面标题、父级、run/`vm_name` 归属做独立回读；测试页必须移入回收站并回读 `in_trash=true`。

## 完成与恢复

成功证据：`PARENT_PAGE=verified`、`TEMPLATE_SOURCE=verified`、`ACCOUNT_INFO=verified`、`NOTION_UTM=verified`。目标页已存在且完全属于同一 run 时幂等继续；部分写入只修缺项。写入不一致先用 before 回滚并独立回读，三轮仍无法唯一归属才发最后故障卡。

## 交接/禁止

禁止使用 Feishu 桌面 app、Chrome Notion、其他 run、最新页面或用户记忆；不把密码/短信链接写入日志。完成后立即交给 [`notion-utm-1`](../skills/notion-utm-1/SKILL.md)。
