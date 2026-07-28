# UTM-8 测试说明

`utm-8` 是 UTM 提交流程中 `utm-7` 之后的账号收尾步骤。它使用同一个 `vm_name`、同一个已登录 Apple Account 和同一个 Notion 注册页，不创建 VM、不改 UTM 配置、不重新读取 Feishu 桌面数据。

## 测试前置

- `utm-7` 已完成并记录 `APPLE_ACCOUNT=verified`、`UTM_7=verified`；登录 helper 已完成目标邮箱精确匹配和 System Settings 关闭/重开复核，目标 UTM guest 保留在 Apple Account 页面。
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
6. 生成最终随机密码：先生成 16 位随机基串（至少含一个大写字母、一个小写字母和一个数字，避免符号与易混字符），再固定追加尾部字母 `y`，因此最终值为 17 位且保留 `y`；不得使用生日、邮箱前缀或旧密码。
7. 每个密码框先写入 16 位随机基串，再由脚本对已聚焦字段真实输入固定尾字母 `y`，触发 macOS SwiftUI 的校验事件；最终两个字段都必须是同一个 17 位值且圆点数量一致。若 AX 只显示圆点但 `Change` 仍禁用，禁止直接提交，重新执行同一字段的基串写入和 `y` 唤醒事件。
8. 重新确认当前账号、两处新密码、相同圆点数和已启用的唯一 `Change`/`Continue`，然后自动点击一次最终 `Change`/`Continue`。复杂度拒绝时按拒绝类别最多生成三个互不重复候选；每次都重新填写、回读，重填验证通过后再次自动点击一次最终 `Change`/`Continue`。每个候选只提交一次。宿主入口会在 guest 提交前先把本轮最终值写入 `修改后的密码：` 并独立回读；guest 已知失败时自动恢复改密前的值，只有 Apple 接受后才保留该预写值。
9. 用 `read-field --copy` 回读用户名、生日和新密码并按字节数/SHA-256 核对；确认 `初始密码：` 未变，随后清空并验证宿主剪贴板为空。

宿主机可使用 `scripts/utm_8_change_password.py --vm-name '<vm_name>' --vm-ip '<vm_ip>'` 作为端到端入口。宿主名自动取当前 `.env` 的 `SUBMISSION_HOST_MACHINE`，Notion 子页按 VM 名称精确匹配，不再手工传页面标题。它在宿主进程内生成候选密码，并调用 `scripts/notion_register_password.py` 通过 Notion API 先写入并回读 `修改后的密码：`，再通过 SSH 标准输入传给原有 guest `apple_account_change_password.py --stdin-json`；guest 已知失败时恢复预写前值，Apple 接受后只做独立回读确认。候选密码不进入 argv、终端输出或日志。单独运行 guest helper 不会登记 Notion，也不能替代端到端入口。

每个 UI 动作都执行“动作 → 等待至少 3 秒 → 重新读取状态 → 再做下一步”；菜单高亮未确认时不得点击。

## 弹窗规则

- 普通加载、确认和与本次改密直接相关的 macOS 权限弹窗：截图确认后继续。
- Apple 当前密码提示：使用 Notion 当前有效密码，不能猜测。
- 若出现 `Enter your password to view account details.`，宿主先读取当前页面非空的 `修改后的密码：`，为空才回退 `初始密码：`，通过 stdin 传给 guest，填写该弹窗并点击唯一 `Continue`；不得填 `1234`。
- Mac 密码提示：调用 `OP-FIXED-PASSWORD-1234`，固定值只有 `1234`，无“默认值”或覆盖分支，并走 `OP-NATIVE-PASTE` 的 GUI 授权子流程。
- 首次脚本真实输入尾字母 `y` 可能出现“某程序 wants access to control System Events”（例如 `Terminal` 或 `sshd-keygen-wrapper`）；脚本识别同一授权弹窗并自动点击唯一 `Allow`，授权完成后继续输入 `y`，不得重复启动脚本。
- 改密成功后若出现 `Sign out other devices using your Apple Account?`，脚本自动点击 `Don’t Sign Out`，保留其他设备登录状态。
- 已知验证码/2FA/SMS 调用 `OP-APPLE-PHONE-OTP`；账号锁定、CAPTCHA、iPhone passcode 或未知安全弹窗完成三轮独立只读复核后，才作为外部不可修复状态发最后故障卡，不绕过。

## 成功标记

```text
USERNAME=verified
BIRTHDAY=verified
PASSWORD_CHANGE=verified
MODIFIED_PASSWORD_NOTION=verified
```

不得在测试记录、截图或最终回复中出现新密码、完整手机号、短信 URL、OTP 或其他凭据。不得用 Chrome、Notion 插件、Playwright、CUA 或浏览器剪贴板读写 Notion。
