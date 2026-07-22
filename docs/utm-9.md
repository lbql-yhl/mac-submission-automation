# UTM-9 测试说明

`utm-9` 在 `utm-8` 之后运行，严格复现“钥匙串访问 -> 证书助理 -> 从证书颁发机构请求证书”流程，把证书请求文件保存到同一 UTM guest 用户的 Desktop。

## 测试前置

- 使用 `utm-8` 的同一 UTM guest、`<vm_name>` 用户和 guest IP。
- guest 已进入桌面；项目 `.env` 已配置当前父页面的 `NOTION_TOKEN` 和 `NOTION_ROOT_PAGE_ID`。
- 账号邮箱只通过 `scripts/notion_api.py` 从匹配页面读取，不凭记忆填写；不得用宿主浏览器、插件或 GUI 读取 Notion，也不得在测试记录或回复中输出邮箱、密码或其他凭据。

## 固定流程

SSH 直接继承 `utm-8` 已验证的 `<vm_name>`、IP 和宿主公钥认证。所有连接固定使用 `BatchMode=yes`；连接失效时只针对同一精确 VM 自动刷新 IP、修复 Remote Login 并恢复同一宿主公钥，禁止向用户索取密码、SSH Key、IP 或等待 `manual_continue`。

1. 在项目根目录执行父页面校验，再在紧接粘贴前把唯一邮箱安全复制到宿主剪贴板；命令输出不得含邮箱值：

   ```bash
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   python3 scripts/notion_api.py read-field --title '<应用名>-<vm_name>' --heading '账号信息' --label '邮箱：' --copy
   ```

2. 通过 SSH 只执行：

   ```bash
   ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$SUBMISSION_SSH_PRIVATE_KEY" \
     -o ConnectTimeout=5 <vm_name>@<vm_ip> 'open -a "Keychain Access"'
   ```

   不使用 `sudo`，不使用 `openssl req -new`、`certtool`、`security create-keypair` 或其他终端证书生成命令。完成后允许用 `openssl req -in ... -noout -verify` 做只读 CSR 语法/签名核验。
3. 若出现 Passwords App 提示，使用 Computer Use 选择“打开钥匙串访问”。
4. 在 Keychain Access 菜单中用键盘导航：打开应用菜单，按 `Down` 直到 `Certificate Assistant` 高亮，按 `Right` 打开子菜单，再按 `Down` 直到 `Request a Certificate From a Certificate Authority...` 高亮，按 `Return` 确认。
5. 进入 `Certificate Information` 后：
   - Common Name 不固定，只保留页面当前值；
   - CA Email Address 留空；
   - 选择 `Saved to disk`；
   - 不勾选 `Let me specify key pair information`；
   - 邮箱输入框完整调用 `OP-NATIVE-PASTE`：右键打开菜单，等待新截图确认 `Paste` 蓝色高亮后才按 `Return` 粘贴；不得用 `Command+V` 或直接输入替代。
6. 确认页面状态后继续，在保存对话框中把位置改为 `Desktop`，保留系统默认文件名并点击 `Save`。
7. 看到 `Your certificate request has been created on disk` 后点击 `Done`。
8. 用两条新 BatchMode SSH 对固定路径 `/Users/<vm_name>/Desktop/CertificateSigningRequest.certSigningRequest` 做常规文件、非符号链接、非空、稳定 SHA-256 和只读 OpenSSL 校验；只有 `CSR_DISK=verified` 才成功。

## 操作纪律

- 每个 GUI 动作后等待至少 3 秒并读取新状态；目标未高亮或页面不明确时，每轮都先 `Escape`/`Cancel` 回到最近验证锚点、作废旧坐标并安全重新定位，完整执行三轮且每轮独立回读；三轮仍不唯一才发最后故障卡。
- 不复用旧坐标；保存位置必须在最新截图中明确显示为 Desktop。
- 右键菜单未出现或 `Paste` 未高亮时按 `OP-NATIVE-PASTE` 关闭菜单、重新聚焦字段并从新截图安全重试三轮，每轮都独立复核剪贴板和目标；三轮恢复穷尽后才发最后故障卡，不猜坐标。

## 成功标记

```text
UTM_9=verified
SSH_KEY_AUTH=verified
CERTIFICATE_REQUEST_SAVED=verified
CERTIFICATE_REQUEST_LOCATION=Desktop
CSR_DISK=verified
```
