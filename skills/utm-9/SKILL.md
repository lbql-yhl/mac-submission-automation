---
name: utm-9
description: Use after utm-8 when the target UTM macOS guest must use Keychain Access Certificate Assistant to request a certificate and save the request to the guest Desktop.
---

# UTM-9

## 全局自动恢复与最后故障卡规则

本技能强制继承共享重复操作记忆：原生粘贴调用 `OP-NATIVE-PASTE`，浏览器 URL 调用 `OP-BROWSER-URL-NO-SCHEME`，Apple 电话/验证码调用 `OP-APPLE-PHONE-OTP`，固定 VM 密码调用 `OP-FIXED-PASSWORD-1234`，必须由用户决定的业务节点才调用 `OP-USER-CONFIRMATION`。不得在本技能内发明简化版或冲突步骤。可安全修复的故障必须做满三轮“诊断→实际修复→独立复验”；只有不可逆动作、不能安全重复写入或外部不可修复状态，才改做三轮独立只读复核。少于三轮时运行时拒绝发卡。

执行任何命令前，在项目根目录运行 `eval "$(python3 scripts/preflight.py --project-only --emit-shell)"`，取得当前机器的动态路径。必须先完整遵守 [`../_shared/AUTOMATION_CONTRACT.md`](../_shared/AUTOMATION_CONTRACT.md)：固定顺序是自动诊断、自动修复、自动复验，只有智能体确实无法修复时才允许发送飞书故障卡。

- 正常成功路径连续自动执行，不发送故障卡，不等待用户确认或普通聊天回复。
- 可逆误点先回到本技能矩阵列出的最近验证锚点，作废旧坐标，等待至少 3 秒并用最新截图重做当前最小动作；成功后记录 `GUI_RECOVERY=verified` 并继续。
- SSH、API、文件和页面瞬态错误按共享合同有界恢复；不可逆动作只执行一次，结果不明时只读查询同一 attempt，禁止盲目重做。
- 只有恢复预算穷尽或只读证明为外部不可修复状态，才记录 `AUTO_RECOVERY_ATTEMPTS`、`AUTO_RECOVERY_ACTIONS`、`AUTO_RECOVERY_RESULT=exhausted|unrepairable` 和最后验证锚点。
- 自动恢复穷尽后，使用下列最后出口；`--unrepairable` 只允许用于 CAPTCHA、账号锁定、权威数据缺失、权限/所有权冲突或不可逆结果仍不明确，不能绕过可执行的恢复：

```bash
python3 services/feishu_bot.py notify-fault \
  --run-id '<current-run-id>' \
  --chat-id '<original-chat-id>' \
  --stage 'utm-9:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-9' \
  --recovery-attempts '<actual-count-at-least-3>' \
  --recovery-actions '<diagnose,repair,reverify>' \
  --recovery-result '<exhausted|unrepairable>'
python3 services/feishu_bot.py wait-decision \
  --run-id '<current-run-id>' --decision-kind fault --timeout-seconds 3600
```

规则：`--recovery-result unrepairable` 必须同时追加 `--unrepairable`；恢复穷尽的 `exhausted` 分支不得追加该参数。两种分支都必须填写真实的恢复次数和动作，不能把占位符原样执行。

故障卡仍固定保留 `stop`、`manual_continue`、`retry_skill` 三个决定及稳定 UUID/首次送达后一小时超时规则。当前执行器收到继续决定后立即重读同一精确现场；已验证步骤只有在证据仍成立时才跳过。故障卡是最后恢复出口，不是正常确认节点。

## 本技能自动恢复矩阵

| 故障点 | 自动诊断、修复和复验 | 最后发卡边界 |
|---|---|---|
| Keychain/菜单误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图，`Escape` 关闭菜单/向导，回到 Certificate Assistant 锚点重开；记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立定位后仍无法唯一确认才发卡 |
| 邮箱粘贴不符 | 只清邮箱字段，API 实时重读，剪贴板哨兵后右键 Paste 并回读 | 三轮安全重贴且每轮独立回读后仍不符才 `exhausted` |
| 保存位置/文件结果不明 | `Cancel` 文件选择器后重新选择 Desktop；落盘后用 SSH 唯一路径/时间/类型确认 | 多候选或所有权不明为 `unrepairable` |
| SSH/Keychain 启动失败 | 自动恢复同一 SSH 并只启动一次；已运行只聚焦 | 三轮后才发卡 |

## SSH 全自动约束

- 直接继承 `utm-8` 的同一 VM/IP、`<vm_name>` 和 `utm-3` 已建立的宿主机 Key；启动钥匙串前只做一次 `BatchMode=yes` 身份检查，不重新配置 SSH。
- SSH 连接失败时只对同一精确 VM 自动刷新 IP、检查 Remote Login/端口并用固定 `1234` 恢复 `${SUBMISSION_SSH_PUBLIC_KEY}`；不得向用户索取密码、SSH Key 或 IP。
- SSH 恢复完成后只执行本技能允许的 `open -a "Keychain Access"`；仍失败则记录 `SSH_AUTO_RECOVERY=blocked`，先按 `utm-9-ssh-auto-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。

## 前置条件

- 当前目标是 `utm-8` 使用的同一个 UTM guest 和 `<vm_name>` 用户。
- 虚拟机已进入桌面。
- 匹配的 Notion 页面包含本次要填写的 Apple Account 邮箱。
- `${PROJECT_ROOT}/.env` 已配置 `NOTION_TOKEN` 与指向当前宿主机页面的 `NOTION_ROOT_PAGE_ID`。
- Notion 邮箱只通过项目 `scripts/notion_api.py` 读取；不得用宿主浏览器、Notion 插件、Playwright、CUA、坐标或浏览器剪贴板读取 Notion。
- 只处理“证书助理 -> 从证书颁发机构请求证书”流程，不判断或选择证书类型。

## 固定流程

1. 回到目标 UTM guest，确认当前窗口属于该虚拟机，并确认 guest 已进入桌面。固定 `CSR_PATH=/Users/<vm_name>/Desktop/CertificateSigningRequest.certSigningRequest`；在宿主 `runtime/attempts/<run_id>/utm-9.json` 原子持久化 mode-600 `CSR_ATTEMPT_ID`、run、vm、guest IP、该固定路径和 Desktop 写入前文件清单。若固定路径已存在，只有 marker 同 run 且后述 OpenSSL/哈希验证完整时可幂等恢复；marker 缺失或冲突时不得覆盖。
2. 在 `${PROJECT_ROOT}` 先校验父页面；失败时先按 `utm-9-notion-parent` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定：

   ```bash
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   ```

3. 通过 SSH 只执行启动应用命令，不执行证书生成命令：

   ```bash
   private_key="${SUBMISSION_SSH_PRIVATE_KEY}"
   ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" \
     -o ConnectTimeout=5 <vm_name>@<vm_ip> 'open -a "Keychain Access"'
   ```

   不要加 `sudo`。确认钥匙串访问窗口已在目标 guest 的桌面出现后，切换到当前 Computer Use/sky GUI 驱动器。
4. 如果出现“在‘系统设置’中管理密码”，使用当前 GUI 驱动器点击“打开钥匙串访问”，不要打开“密码”。
5. 使用当前 GUI 驱动器打开 macOS 顶部“钥匙串访问”菜单；按 `Down` 逐项确认，直到“证书助理”高亮；按 `Right` 打开子菜单；继续按 `Down`，直到“从证书颁发机构请求证书…”高亮；按 `Return` 确认。不要用未经确认的坐标直接点击菜单项。
6. 在“证书助理”窗口：
   - 紧接粘贴前，在项目根目录执行 `python3 scripts/notion_api.py read-field --title '<应用名>-<vm_name>' --heading '账号信息' --label '邮箱：' --copy`。要求安全元数据表明字段唯一且非空，并用 `pbpaste` 做本地只读核对；命令输出不得含邮箱值。
   - 右键“用户电子邮件地址”输入框，等待菜单出现，按 `Down` 使 `Paste` 高亮，再按 `Return` 粘贴；不得用 `Command+V` 快捷键或直接输入代替。
   - “常用名称”不固定，保留证书助理页面当前显示的值，不自行修改或写死用户名；
   - “CA 电子邮件地址”留空；
   - 选择“存储到磁盘”；
   - 不勾选“让我指定密钥对信息”。
7. 确认邮箱、常用名称和“存储到磁盘”均正确后，使用当前 GUI 驱动器点击“继续”。
8. 在保存对话框中使用当前 GUI 驱动器选择虚拟机桌面“Desktop”，确认文件名精确为 `CertificateSigningRequest.certSigningRequest`；仅当步骤 1 的写入前清单证明该路径不存在时点击一次“存储”。若系统显示替换确认，取消保存并进入所有权恢复，绝不覆盖。
9. 确认“证书请求已创建并存储到磁盘”的完成页出现，使用当前 GUI 驱动器点击“完成”。
10. 完成页不是磁盘证据。用两条全新、只读、显式私钥 SSH 分别验证：固定路径为非空常规非符号链接文件；Desktop 相对写前清单恰好新增这一项；mode/字节数/SHA-256 稳定；下列解析命令 exit 0 且不输出 subject/email：

   ```bash
   csr='/Users/<vm_name>/Desktop/CertificateSigningRequest.certSigningRequest'
   ssh -o BatchMode=yes -o IdentitiesOnly=yes -i "$private_key" <vm_name>@<vm_ip> \
     'test -s "'"$csr"'" -a ! -L "'"$csr"'"; /usr/bin/openssl req -in "'"$csr"'" -noout -verify >/dev/null 2>&1'
   ```

   两次 byte count/SHA-256 必须相同，marker 原子更新 `status=complete` 并独立回读后记录 `CSR_DISK=verified`。零新增、多个新增、解析失败或路径冲突均不得交接。

## 操作纪律

- 不得改走终端命令、OpenSSL、`certtool`、Apple Developer 网页或其他证书创建路径。
- SSH 可执行启动 Keychain Access，以及完成后的只读 `stat`/SHA-256/`openssl req -in ... -noout -verify` 核验；不得通过 SSH 执行 `certtool`、`security create-keypair`、`openssl req -new` 或任何生成/修改命令。
- 不得选择“发送给 CA”、创建证书颁发机构、评估证书或其他菜单项。
- `computer-use` 每次点击、输入、滚动或菜单操作后，必须等待至少 3 秒，再重新读取最新 app state/截图并重新定位；只有确认界面和目标高亮无误后才能继续。菜单、弹窗或保存位置不明确时暂停 GUI 操作，先按 `utm-9-gui-state` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；不猜坐标、不复用旧坐标。
- 邮箱只能使用 `scripts/notion_api.py read-field --copy` 从当前匹配页面读取；粘贴前确认剪贴板内容准确，禁止手动猜写。右键菜单未出现或 `Paste` 未高亮时暂停 GUI 操作，先按 `utm-9-paste-state` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；不猜坐标。
- 遇到钥匙串授权弹窗时调用 `OP-FIXED-PASSWORD-1234`：确认弹窗属于当前 `<vm_name>` guest 和本次 CSR 操作，按 `OP-NATIVE-PASTE` 粘贴固定值，验证四个圆点，再自动点击唯一蓝色授权按钮并确认弹窗关闭；不得使用 Apple Account 密码或询问用户。未知或归属不明的授权弹窗先暂停输入，重读窗口、进程、CSR attempt 和 guest 归属三轮；只有三轮独立复核仍不能归属时才进入当前 run 的最后故障卡出口。
- 不删除、导出、覆盖或修改已有钥匙串项目。

## 完成标准

仅当以下状态全部确认后完成：

```text
UTM_9=verified
CERTIFICATE_REQUEST_SAVED=verified
CERTIFICATE_REQUEST_LOCATION=Desktop
CSR_ATTEMPT_ID=<stable-id>
CSR_PATH=/Users/<vm_name>/Desktop/CertificateSigningRequest.certSigningRequest
CSR_DISK=verified
```

失败或弹窗目标不明确时记录 `UTM_9=blocked` 和可见阻塞类别，先按 `utm-9-gui-state` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；卡片证据与报告均不得包含邮箱、密码或其他凭据。

## 连续交接

仅当本技能全部完成检查通过时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-10`；不得等待用户确认。阻断、失败或未完成状态不得交接。
