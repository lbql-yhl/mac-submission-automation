# UTM-15：获取 App ID 并登记 Notion

## 定位

`utm-15` 接在 `utm-14` 后，继续使用同一 guest Edge 和已有标签页，从 App Store Connect `Business` 页面进入 `Apps`，打开匹配的应用，读取详情页 URL 中的数字 App ID，并登记到匹配 Notion 页面的 `账号信息` → `APP_ID：`。

本技能不创建应用、不点击 `Add Apps`，也不新增已不存在的 `app_id:`。

## 操作 Checklist

- [ ] `utm-14` 已完成，确认 `DAC7_INFO=No_saved`，并确认当前仍是 App Store Connect `Business` 页面；缺少 DAC7 保存证据时不得进入 `Apps`。
- [ ] 仍使用同一个 guest、同一个 Edge 进程和已有标签页；不启动、重启或切换新浏览器。
- [ ] 等待至少 3 秒，读取最新截图，确认账号会话有效且顶部导航出现 `Apps`。
- [ ] 从最新截图重新定位顶部 `Apps`，点击一次；等待至少 3 秒并确认进入 Apps 页面。
- [ ] 运行 `scripts/notion_api.py verify-parent`，通过 `read-field --copy` 从匹配 `<应用名>-<vm_name>` 页的 `'应用名: '` 读取应用名。
- [ ] 在 Apps 页面只点击与 Notion `应用名`一致的应用名；不点击 `Add Apps`。
- [ ] 等待至少 3 秒，确认进入应用详情页。
- [ ] 从当前详情页 URL 提取唯一 `/apps/<纯数字>/`；无法唯一提取时回到 Apps 列表并按应用名/App ID/页头重新定位三轮，仍不唯一才发最后故障卡。
- [ ] 用 `read-field --copy` 读取 `APP_ID：`；空值才写、相同值幂等。不同值时重新读取同一详情 URL 和 Notion 字段三轮，仍冲突才报告 `notion_app_id_mismatch` 并发最后故障卡；不覆盖、不新增 `app_id:`。
- [ ] 将 URL 提取的纯数字 App ID 放入已验证剪贴板，通过 `pbpaste | scripts/notion_api.py set-field ... --value-stdin` 只更新 `APP_ID：`，不使用 `--replace-existing`。
- [ ] API 写后自动回读；再用 `read-field --copy` 按字节数/SHA-256 复核 App ID，只允许一个字段匹配。

## 成功方法

```text
Business → Apps → 匹配应用名 → /apps/<数字>/ → Notion API set-field APP_ID： → API 回读
```

Notion 写入必须是字段级 API 操作：精确唯一匹配 `APP_ID：`，通过标准输入传值，不能整块重写，也不能使用 Chrome/插件/Playwright/CUA 写入。

## 完成标准

```text
UTM_15=verified
APP_STORE_CONNECT=focused
APPS=opened
APP_DETAIL=opened
APP_ID=extracted
APP_ID_NOTION=updated_and_persisted
```

## 风险点

- 页面变化后不复用旧坐标；每一步都必须等待并读取最新状态。
- 未确认 `DAC7_INFO=No_saved` 时只读恢复同一 Business 条目和 `utm-14` 证据；恢复穷尽后才发最后故障卡，不能凭 W-8BEN 或返回 Business 猜测。
- URL 中的数字必须来自当前应用详情页的 `/apps/<纯数字>/` 段，不能从旧截图或页面其他数字推断。
- Apps 列表中应用名必须与 Notion 应用名匹配。
- `APP_ID：` 不同值按三轮独立来源对账后才发最后故障卡，不覆盖；页面没有 `app_id:` 时不要添加。
- API 回读失败按 2/5/10 秒三轮重读；其他字段变化时使用 before 证据核对并恢复可逆误写，仍不一致才发最后故障卡。
