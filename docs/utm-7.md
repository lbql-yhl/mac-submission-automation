# UTM-7：无视觉 Apple Account 登录

`utm-7` 继承 `utm-6` 的同一 run、`vm_name`、guest IP、最终 SSH 用户和 SSH 身份。它不启动 Computer Use，不操作 UTM 画面，不打开 guest Terminal，也不把账号值放入命令参数或日志。

这里替换的是 guest macOS System Settings 内的 Apple Account 登录；`utm-10`/`utm-18` 的 Apple Developer/Edge 网页会话属于独立浏览器流程，继续使用各自的 API-only 凭据读取和既有 Edge 会话规则，不调用这个 System Settings helper。

## 固定执行步骤

1. 在项目根目录执行 `eval "$(python3 scripts/preflight.py --project-only --emit-shell)"`，确认当前 run、精确 VM、BatchMode SSH 和 Notion 父页一致。
2. 执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，然后确认唯一匹配的 `<应用名>-<vm_name>` 页面和 `账号信息` heading。通过同一 API 读取 `邮箱：`、非空 `修改后的密码：`（为空才读 `初始密码：`）、`电话：`、`电话短信接收平台：`；值只进入当前脚本内存。
3. 执行：

   ```bash
   python3 scripts/utm_7_login.py \
     --parent-title '<宿主机名称>' \
     --page-title '<应用名>-<vm_name>' \
     --vm-ip '<当前精确 VM IP>' \
     --vm-user '<vm_name>'
   ```

   仅标题、IP 和用户名允许出现在 argv；账号、密码、电话和短信 URL 通过 SSH 标准输入 JSON 进入 guest helper。
4. `utm_7_login.py` 将项目内 `apple_account_login.py`、`find_system_settings_general.py`、`apple_account_post_login.py` 和 `mac_password_prompt.py` 上传到 guest Downloads，并以 SHA-256 和 `python3 -m py_compile` 独立核对。哈希不匹配时暂停业务动作，只修复同一 VM 三轮。
5. helper 入口结束同一路径旧实例后，用 Accessibility API 自动完成邮箱、密码、Continue、唯一电话尾号、当前短信页面最新验证码、Mac Password `1234`、`Don't know passcode?`/`Enter Passcode Later` 和 `Don't Merge`。不使用视觉、坐标、Computer Use、剪贴板、键盘盲输或人工确认。
6. helper 每轮先轻量检查目标邮箱；邮箱在初始页面、验证码后或安全提示期间出现即跳过不必要步骤。首次邮箱确认后关闭 System Settings，重开后进入 Apple Account 详情页再次确认邮箱；第二次确认后保留 System Settings 打开。
7. 只有 helper 退出码 `0`、输出 `APPLE_ACCOUNT=verified`、`UTM_7=verified`、邮箱与 Notion `邮箱：` 完全匹配以及重开复核成功时，才记录 `UTM_7=verified` 并连续交接 `utm-8`。

## 自动恢复与阻断

- Notion 页面/字段、SSH 连接、helper 上传、哈希、AX 瞬态错误均只对同一目标执行三轮诊断→修复→独立复验。
- SMS 始终按 `OP-APPLE-PHONE-OTP` 读取当前 URL、过滤旧码并接受最新六位码（有时间取时间最新，无时间按页面顺序取最后一条）；不得复用旧码。
- CAPTCHA、锁号、账号/邮箱不匹配、无法判定最新验证码、未知安全挑战或第二次邮箱复核持续失败，完成三轮只读复核后才进入 `utm-7` 最后故障卡。
- 任何失败或未完成状态不得交接 `utm-8`；不得选择其他 VM、修改 Notion、修改 UTM 设置或要求用户人工操作。
