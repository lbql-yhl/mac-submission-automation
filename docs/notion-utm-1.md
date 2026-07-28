# notion-utm-1：读取产品表并填充应用信息

## 输入与来源

继承 `NOTION_UTM=verified` 的同一 Notion 页。产品字段只来自 Feishu API 固定表 `26财年巨风做包表`：先查询金鳞 view `vewKUW4q4W`，三轮 5/15/30 秒精确 `is` 均为 0 后，才查询祥云 view `vew1k7hwhJ` 的 `contains` 回退。

## 步骤

1. `verify-parent` 并重新解析当前 run 的应用名；刷新 tenant token，核对 wiki/table/view ID。
2. 在金鳞 view 以应用名精确查询；唯一一条才接受并记录 `FEISHU_PRODUCT_VIEW=金鳞产品表格`，多条或字段缺失立即进入只读恢复。
3. 三轮金鳞均为 0 时，才在祥云 view 使用 `contains`；候选应用名必须包含目标名且最终恰好一条，记录 `FEISHU_PRODUCT_VIEW=祥云产品表格`。
4. 只取 API 返回字段，规范化应用类型到固定 ASC enum；不要从 Feishu 桌面或浏览器可见表格复制字段值。
5. 读取 Notion `应用信息` before，按精确标签构造新 block；同 run 已有相同值幂等通过，冲突时用新鲜唯一产品记录替换并保存 before。
6. 写入后通过 API 再读三轮，逐标签比较应用名、Bundle ID、SKU、分类和素材链接；哈希不符则原子回滚并独立确认 `NOTION_ROLLBACK=verified`。
7. 所有字段和来源唯一性通过后记录 `NOTION_UTM_1=verified`，交接给 `utm-clone-macos`。

## 恢复和禁止

API/配置异常只重取 token、固定 table/view 并按 5/15/30 秒重读；可见页面与 API 矛盾时仅核对上下文，记录 `FEISHU_TABLE_CONTEXT_MISMATCH=verified` 并停止写入。禁止猜第一条、查询祥云绕过金鳞唯一命中、使用截图字段、发确认卡或等待用户。
