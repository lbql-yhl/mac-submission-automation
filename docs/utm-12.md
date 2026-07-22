# UTM-12：Apple Developer 到 App Store Connect 应用创建

## 定位

`utm-12` 接在 `utm-11` 后，使用同一台 UTM guest、同一个 Microsoft Edge 进程和同一个登录会话。它负责协议处理、会员信息登记、App ID 注册和 App Store Connect 应用创建；验证 `iOS App Version 1.0` 后结束。

本技能是自动化流程，不等待用户确认。每个关键动作前后都检查；异常先按技能矩阵回到最近锚点、自动修复和复验，只有恢复穷尽或外部状态不可修复时才发最后故障卡。

## 通用规则

- 每次点击、粘贴、切换标签页后等待至少 3 秒，再读取最新截图和状态。
- 页面变化后重新定位坐标，禁止复用旧坐标。
- 页面滚动必须慢速、小步进行。
- Name、Description、Bundle ID、SKU 等内容完整调用 `OP-NATIVE-PASTE`，只能在 guest Edge 当前菜单中 `Paste` 可见、可用且蓝色高亮后激活并回读。
- Notion 只通过 `scripts/notion_api.py` 读写；每次先用 `verify-parent` 确认当前宿主机页面，不操作 Chrome Notion。
- 不记录密码、短信验证码、代理密码或完整短信链接。

## 操作步骤

### 1. Apple Developer Account

1. 已有且唯一的 `developer.apple.com/account/` 标签只切换；不存在时才新建 tab，调用 `OP-BROWSER-URL-NO-SCHEME` 并执行 `printf '%s' 'developer.apple.com/account/' | python3 scripts/shared_operations.py browser-url --allow-bare`，只在 `BROWSER_URL_CLIPBOARD=verified` 且 `Paste and Go` 蓝色高亮后确认一次，随后清空剪贴板。
2. 确认 URL、`Account` 标题和登录账户正确。
3. 如果出现 `The program license agreement has been updated`：
   - 点击 `Review agreement`。
   - 等待协议页。
   - 自动勾选协议并点击 `Agree`。
   - 返回 Account 后确认提示消失。
4. 没有协议提示时跳过。

### 2. Membership details 与 Notion

1. 慢速滚动到 `Membership details`。
2. 读取 `Team ID` 和 `Renewal date`。
3. 运行 `verify-parent`，通过 API 唯一解析 `<应用名>-<vm_name>` 和 `账号信息`。
4. 将两个来源值分别通过标准输入交给 `set-field`，只更新精确标签 `team ID:` 和 `Renewal date：`。
5. 不使用 `--replace-existing`；已有相同值幂等通过，已有不同值时重读 Apple Membership 和 Notion 三轮，仍冲突才作为外部数据冲突发最后故障卡，不覆盖。
6. 分别用 `read-field --copy` 回读，并以字节数/SHA-256 确认与 Apple 页面来源一致。

### 3. 注册 App ID

1. 回到 Account 页面顶部，慢速滚动到 `Apps`。
2. 点击 `Apps` → `Add Apps`。
3. 点击 `Register a new bundle ID in Certificates, Identifiers & Profiles`。
4. 通过 `read-field --copy` 从 `应用信息` 的精确标签 `'应用名: '` 和 `'正式包名: '` 实时读取，分别填写 `Description` 和 `Bundle ID`；不打印值。
5. 对两个字段分别完整调用 `OP-NATIVE-PASTE`，每次都重新取得权威值、哨兵验证、右键高亮粘贴、回读并清空敏感剪贴板。
6. 确认字段完全匹配后点击 `Continue`。
7. 在 `Confirm your App ID` 页面再次自检。
8. 自检通过后自动点击 `Register`。
9. 回到 Identifiers 列表后确认新行包含正确应用名和 Bundle ID。

### 4. 创建 App Store Connect 应用

1. 切换到同一个 Edge 的 App Store Connect Apps 标签页。
2. 页面异常或旧模态框残留时，双击地址栏左侧圆形刷新按钮，等待约 6 秒。
3. 确认回到 Apps 页面后点击 `Add Apps`。
4. 在 `New App` 中填写：
   - 勾选 `iOS`
   - `Name`：Notion 应用名
   - `Primary Language`：`English (U.S.)`
   - `Bundle ID`：唯一的已注册 Bundle ID
   - `SKU`：Notion 正式包名
   - `User Access`：`Full Access`
5. 如果 Bundle ID 下拉框为空，先检查 App ID 是否完成 Register，不要手填。
6. 自动核对所有字段后点击 `Create`。
7. 验证进入正确应用详情页，并显示正确应用名和 `iOS App Version 1.0`。

## 完成标准

```text
UTM_12=verified
DEVELOPER_ACCOUNT=opened
NOTION_MEMBERSHIP_FIELDS=updated
APP_ID_FORM=confirmed
APP_ID_REGISTERED=verified
APP_STORE_APP=created
```

完成后交给 `utm-13`，不要在 `utm-12` 进入 Certificates 页面。

## 自动恢复与最后故障卡

`account_page_missing`、`agreement_page_missing`、`notion_page_missing`、`notion_save_unverified`、`bundle_id_not_available`、`navigation_error`、`field_mismatch`、`result_not_verified` 都先执行技能矩阵的有界重读、可逆回滚和独立复验；只有恢复穷尽才携带恢复证据发最后故障卡。
