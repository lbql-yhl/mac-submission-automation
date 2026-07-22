# UTM-8 测试说明

`utm-8` 是 UTM 提交流程中 `utm-7` 之后的账号收尾步骤。它使用同一个 `vm_name`、同一个已登录 Apple Account 和同一个 Notion 注册页，不创建 VM、不改 UTM 配置、不重新读取 Feishu 桌面数据。

## 测试前置

- `utm-7` 已完成，目标 UTM guest 正在桌面或 Apple Account 页面。
- guest 中已登录目标 Apple Account，且当前用户是 `<vm_name>`。
- `.env` 中 Notion API 连接可用，`NOTION_ROOT_PAGE_ID` 指向当前宿主机页面，匹配子页面为 `<应用名>-<vm_name>`。
- Notion `账号信息` 中存在以下字段：

```text
用户名：
邮箱：
初始密码：
修改后的密码：
生日：
```

- 当前密码取值：优先使用非空的 `修改后的密码：`，否则使用 `初始密码：`。两者都为空时保持 guest 页面不动，在立即、5 秒、10 秒三轮重新执行 `verify-parent` 和两个字段读取；仍为空才作为权威数据缺失发送最后故障卡。

## 固定流程

1. 先运行 `scripts/notion_api.py verify-parent`，再用 `read-field --copy` 分别读取当前 `邮箱：`、`初始密码：`、`修改后的密码：`、`用户名：`、`生日：`；值不打印、不落临时文件，确认邮箱和 guest Apple Account 一致。
2. guest 打开 `System Settings` -> Apple Account -> `Personal Information`。
3. 记录页面显示的 `Name` 和 Birthday（统一为 `YYYY/MM/DD`）；每个值经已验证剪贴板通过 `pbpaste | scripts/notion_api.py set-field ... --value-stdin` 分别更新 `用户名：`、`生日：`。
4. Notion 只走字段级 API；父页、页面、标题和字段必须唯一。已有不同值时重新读取同一 guest Apple Account 与 Notion 字段三轮；仍冲突才作为外部所有权/数据冲突发最后故障卡，不覆盖。脚本保留代码块格式和空行，写后自动回读。
5. 返回 Apple Account，进入 `Sign-In & Security` -> `Change Password`。
6. 生成随机密码，满足至少 8 位、至少含一个大写字母、一个小写字母和一个数字，避免符号、易混字符、生日、邮箱前缀和旧密码。
7. 每个密码框完整调用 `OP-NATIVE-PASTE`，用随机哨兵、字节数和 SHA-256 做逐次校验；只有右键菜单 `Paste` 在新截图中可见、可用且蓝色高亮时才激活，不猜坐标、不复用旧菜单索引。填写 `New Password` 和 `Verify`，核对两边圆点数量一致。
8. 重新确认当前账号、两处新密码、相同圆点数和已启用的唯一 `Change`/`Continue`，然后自动点击一次最终 `Change`/`Continue`。复杂度拒绝时按拒绝类别最多生成三个互不重复候选；每次都重新填写、回读，重填验证通过后再次自动点击一次最终 `Change`/`Continue`。每个候选只提交一次；三个候选都被策略拒绝、限流、锁定或未知挑战才发最后故障卡。Apple 接受后才更新 `修改后的密码：`。
9. 用 `read-field --copy` 回读用户名、生日和新密码并按字节数/SHA-256 核对；确认 `初始密码：` 未变，随后清空并验证宿主剪贴板为空。

每个 UI 动作都执行“动作 → 等待至少 3 秒 → 重新读取状态 → 再做下一步”；菜单高亮未确认时不得点击。

## 弹窗规则

- 普通加载、确认和与本次改密直接相关的 macOS 权限弹窗：截图确认后继续。
- Apple 当前密码提示：使用 Notion 当前有效密码，不能猜测。
- Mac 密码提示：调用 `OP-FIXED-PASSWORD-1234`，固定值只有 `1234`，无“默认值”或覆盖分支，并走 `OP-NATIVE-PASTE` 的 GUI 授权子流程。
- 已知验证码/2FA/SMS 调用 `OP-APPLE-PHONE-OTP`；账号锁定、CAPTCHA、iPhone passcode 或未知安全弹窗完成三轮独立只读复核后，才作为外部不可修复状态发最后故障卡，不绕过。

## 成功标记

```text
USERNAME=verified
BIRTHDAY=verified
PASSWORD_CHANGE=verified
MODIFIED_PASSWORD_NOTION=verified
```

不得在测试记录、截图或最终回复中出现新密码、完整手机号、短信 URL、OTP 或其他凭据。不得用 Chrome、Notion 插件、Playwright、CUA 或浏览器剪贴板读写 Notion。
