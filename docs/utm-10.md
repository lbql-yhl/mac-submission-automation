# UTM-10：登录 Apple Developer

## 输入与前置

继承 `utm-9` 的同一 guest Edge、`UTM_9=verified`、证书请求文件和当前 run。账号邮箱等字段必须临近操作时通过 Notion API `verify-parent`/`read-field` 读取。

## 步骤

1. 在同一 Edge 复用已有标签；只有目标标签不存在才用 `OP-BROWSER-URL-NO-SCHEME` 打开 `developer.apple.com/account/`，每次导航后等待至少 3 秒并读新截图。
2. 确认页面标题、URL、账户头像/名称属于当前 Apple 账号；出现协议时只接受当前账号对应的协议页面并自动同意，回到 Account 后再读一次。
3. 若出现登录、电话或短信挑战，重新用 Notion API 读取账号/电话/短信链接，验证码必须走 `OP-APPLE-PHONE-OTP` 原生粘贴；不在 URL、日志或剪贴板长期保留敏感值。
4. 进入 `developer.apple.com/account/` 后，读取头像/账户标签并与 API 来源做邮箱后缀/唯一账号复核；不匹配时回到安全锚点，不猜测。
5. 记录 `EDGE=verified`、`APPLE_ACCOUNT=verified`、`UTM_10=verified`，把同一 Edge 会话交给 `utm-11`。

## 恢复与禁止

标签误点只关闭本轮错误标签并回到已验证 Account；三轮页面/账号只读复核后仍无法分类才发卡。禁止操作 Feishu/Notion 浏览器页面、启动新 Edge、打印密码或验证码。
