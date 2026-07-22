---
name: utm-16
description: Use after utm-15 to read the matching Notion app record through the project API and turn it into a verified review environment file in the matching UTM macOS guest.
---

# UTM-16：生成并 SSH 写入提审环境文件

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
  --stage 'utm-16:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-16' \
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
| Notion GET/生成失败 | 同一父页/子页按 2/5/10 秒重读三次；未知类别/缺字段不猜 | 权威数据仍非法为 `unrepairable` |
| host `.env` 写入失败 | 生成器用同目录 mode-600 临时文件、`fsync` 和 `os.replace` 原子提交；失败时恢复旧字节/权限并独立复验 | 还原后才发卡 |
| SSH/原子覆盖/hash 不一致 | SSH 或三端身份可安全恢复时，锁定同一 VM 做满三轮恢复且每轮重新比较三端。覆盖已发生或结果不明时禁止再覆盖；旧目标保留到新目标独立回读成功，失败时只原子还原一次并记录 `GUEST_ENV_ROLLBACK=verified`，其余轮次只读比较 before/after/三端 hash | 对应的三轮恢复或三轮安全只读复核均穷尽后才 `exhausted` |
| 目标目录暂时缺失 | 重读同一继承 workspace 三次，不创建或改选项目 | 确认缺失为上游外部状态，发卡 |

## 定位

`utm-16` 是 `utm-15` 后的最后一步环境准备：只通过 `scripts/notion_api.py` 读取当前匹配的 Notion 页面并校验字段，立即使用宿主脚本生成共享目录 `.env`，再通过宿主 SSH 在匹配 guest 内执行 `cp`，最后用新 SSH 连接核验文件。全流程自动执行，不设置用户审核或确认节点。

本技能只对 Notion 发起 GET 请求，不修改 Notion，不使用宿主 Chrome、Notion 插件、Playwright、CUA、坐标、DOM 或浏览器剪贴板读写 Notion，不把完整脚本输入 guest Terminal，也不运行提审或发布命令。

## SSH 全自动约束

- 直接继承前序同一精确 VM/IP、`<vm_name>` 和 `SSH_KEY_AUTH=verified`；正常路径只做一次 `BatchMode=yes` 身份检查，不重复配置 SSH。
- BatchMode 失败时自动按该 VM 的精确 MAC 刷新 IP、检查 Remote Login/端口，并用固定 `1234` 恢复宿主机 `${SUBMISSION_SSH_PUBLIC_KEY}`；不得向用户索取密码、SSH Key 或 IP。
- 恢复后重新验证用户/home；仍失败时记录 `SSH_AUTO_RECOVERY=blocked`，先按 `utm-16-ssh-auto-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；不改用密码型长命令、不切换 VM。

## 前置条件

- `utm-15` 已完成，页面标题为 `<应用名>-<vm_name>`。
- 已配置 `NOTION_TOKEN` 和 `NOTION_ROOT_PAGE_ID`，integration 对当前父页面有读取权限。
- 已从当前运行上下文唯一确定 `<宿主机名称>` 与 `<应用名>-<vm_name>`，不得从浏览器页面猜测。
- `<vm_name>` 必须是四位小写字母，目标 UTM VM 必须处于 `started`。
- 项目中存在 `scripts/notion_api.py` 和 `scripts/utm_16_generate_env.py`。
- UTM 共享目录已挂载为 guest `/Volumes/My Shared Files/共享文件`。

## 字段映射

| `.env` 字段 | Notion 来源 |
|---|---|
| `APP_ID` | `APP_ID：`，必须是纯数字 |
| `CONTACT_PHONE` | `电话：`，保留 `+` |
| `CONTACT_EMAIL` | `邮箱：` |
| `VM_NAME` | 页面标题最后一个 `-` 后的四位小写字母 |
| `CONTACT_FIRST_NAME` / `CONTACT_LAST_NAME` | `用户名：` 按空白拆分；只有一个词时先按 `utm-16-contact-name` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定 |
| `COPYRIGHT` | `应用名: ` |
| `BUNDLE_ID` | `正式包名: ` |
| `PRIMARY_CATEGORY` | `应用类型：`；必须由固定脚本按下表转换为 App Store Connect 枚举值 |
| `DESCRIPTION` | `应用描述：`；真实换行转换为字面量 `\n` |
| `KEYWORDS` | `关键词: ` |
| `PROD_SERVER_URL` | `https://apple-callback.` + `顶级域名: ` |
| `SUPPORT_URL` | `支持链接: ` |
| `PRIVACY_POLICY_URL` | `隐私协议: ` |
| `PRIVACY_CHOICES_URL` | `用户协议: ` |

### `PRIMARY_CATEGORY` 固定转换

Notion `应用类型：` 的原值原样交给 `scripts/utm_16_generate_env.py`。中文或英文展示名只允许由该脚本统一转换；如果 Notion 已保存下表中的枚举值，脚本必须原样保留。生成的 `.env` 中禁止保留中文类别或 `Graphics & Design` 这类展示名。

| Notion 原值 | `.env` 枚举值 |
|---|---|
| `报刊杂志` | `MAGAZINES_AND_NEWSPAPERS` |
| `财务` | `FINANCE` |
| `参考资料` | `REFERENCE` |
| `导航` | `NAVIGATION` |
| `工具` | `UTILITIES` |
| `购物` | `SHOPPING` |
| `健康健美` | `HEALTH_AND_FITNESS` |
| `教育` | `EDUCATION` |
| `旅游` | `TRAVEL` |
| `美食佳饮` | `FOOD_AND_DRINK` |
| `软件开发工具` | `DEVELOPER_TOOLS` |
| `商务` | `BUSINESS` |
| `社交` | `SOCIAL_NETWORKING` |
| `摄影与录像` / `Photo & Video` | `PHOTO_AND_VIDEO` |
| `生活` | `LIFESTYLE` |
| `体育` | `SPORTS` |
| `天气` | `WEATHER` |
| `贴纸` | `STICKERS` |
| `图书` | `BOOKS` |
| `图形和设计` / `图形与设计` / `Graphics & Design` | `GRAPHICS_AND_DESIGN` |
| `效率` | `PRODUCTIVITY` |
| `新闻` | `NEWS` |
| `医疗` | `MEDICAL` |
| `音乐` | `MUSIC` |
| `游戏` | `GAMES` |
| `娱乐` | `ENTERTAINMENT` |

原值既不在上表左列、也不是上表右列枚举值时暂停生成，先按 `utm-16-category` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；不得猜测、自行翻译或原样写入 `.env`。

固定值只能是：

```dotenv
RELEASE_OPTION=manual
CDP_ENDPOINT=http://127.0.0.1:9222
```

密码、短信链接、验证码、代理信息及其他未映射字段不得进入生成参数或 `.env`。

## 操作步骤

### 一、通过 Notion API 确认读取目标

1. 从当前运行上下文取得唯一 `<宿主机名称>` 和 `<应用名>-<vm_name>`；页面标题最后一个 `-` 后必须是四位小写 `<vm_name>`，标题中的应用名必须与 `应用名: ` 完全一致。
2. 每次读取前先执行父页面校验：

```bash
python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
```

3. 只有 `verify-parent` 成功后才能继续。生成器内部只通过同一 API 客户端 GET 读取唯一页面的 `账号信息` 和 `应用信息`；标题、heading 和紧随 heading 的 code block 都必须唯一。
4. 账号块精确读取 `用户名：`、`邮箱：`、`电话：`、`APP_ID：`；应用块精确读取 `应用名: `、`顶级域名: `、`正式包名: `、`隐私协议: `、`用户协议: `、`支持链接: `、`应用类型：`、`应用描述：`、`关键词: `。每个必填标签必须只出现一次。
5. `应用描述：` 从该标签同行的值开始读取到唯一 `关键词: ` 之前，保留真实换行；写入 `.env` 时再转换为字面量 `\n`。
6. 不把账号块、应用块或敏感字段打印到终端，不把字段组成 JSON 命令参数，不调用任何 Notion 写入方法。

### 二、宿主脚本生成共享文件

1. 让固定生成器再次校验父页面、通过 API 读取两个区块、解析字段并生成文件：

```bash
python3 -m scripts.utm_16_generate_env \
  --parent-title '<宿主机名称>' \
  --page-title '<应用名>-<vm_name>'
```

命令行不得携带任何 Notion 字段值；标准输出只允许包含文件路径、字节数、行数、SHA-256 和不含数据值的 `ENV_WRITE=changed|unchanged`、`ENV_READBACK=exact`。

2. 输出必须固定为：

```text
${SUBMISSION_SHARED_DIR}/.env
```

不得生成 `.env.<vm_name>` 或其他文件名。

3. 生成器创建临时文件时就以 `600` 打开，写完对文件执行 `fsync`，再以 `os.replace` 同目录原子提交并同步目录；目标内容未变且原权限已是 `600` 时不替换 inode。提交后重新读取宿主文件，校验字节数、行数、权限 `600`、SHA-256、必填字段唯一，确认 `PRIMARY_CATEGORY` 是上表枚举值且不是原展示名，并确认未包含密码、短信链接或代理密码。失败时按生成前字节和权限自动还原并独立回读；全部成功后记录 `NOTION_SOURCE=api_unique_matched_and_read`、`ENV_DATA=validated`、`ENV_WRITE=changed|unchanged` 和 `ENV_READBACK=exact`。

### 三、确认 VM、SSH 和目标路径

1. 直接继承 `utm-15` 的当前 `vm_name`、VM IP 和 SSH 身份；正常路径不得运行 `utmctl` 扫描、重新选择 VM 或重新发现 IP。
2. 先解析并核对 `private_key="${SUBMISSION_SSH_PRIVATE_KEY}"` 为当前宿主固定私钥：必须是非符号链接、普通非空文件且权限不宽于 `600`；记录 `SSH_PRIVATE_KEY=verified`。对继承 IP 执行一次只读 BatchMode SSH 核验；输出必须证明当前用户和 home 都匹配：

```bash
private_key="${SUBMISSION_SSH_PRIVATE_KEY}"
ssh -i "$private_key" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=5 \
  '<vm_name>@<vm-ip>' 'id -un; pwd'
```

只有继承 IP 不可达时，才允许从 `${SUBMISSION_VM_IMAGES_DIR}/<vm_name>.utm/config.plist` 读取该精确 VM 的 MAC，并通过 `arp -an` 刷新一次 IP，再执行上方全自动 SSH 恢复和同一身份检查。不得选择其他或“最新”VM；用户不匹配、IP 不唯一或恢复后仍不可达时记录 `SSH_AUTO_RECOVERY=blocked`，先按 `utm-16-ssh-auto-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定，不向用户索取信息。

3. 确认 guest 共享源是非符号链接普通文件、目标目录是非符号链接目录：

```text
/Volumes/My Shared Files/共享文件/.env
/Users/<vm_name>/Downloads/Fire_One_en1.2/
```

4. 在覆盖前记录 guest 共享源与旧目标文件的路径、字节数、权限和 SHA-256；旧目标不存在是允许状态。旧目标若存在但不是非符号链接普通文件则停止，不得覆盖。

### 四、SSH 复制并重新连接核验

1. 在宿主机通过 SSH 执行固定原子替换脚本；私钥必须是上一步已核对的 `private_key`，不得把 `.env` 内容放进 argv 或命令正文：

```bash
ssh -i "$private_key" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=5 \
  '<vm_name>@<vm-ip>' /bin/zsh -s -- \
  '/Volumes/My Shared Files/共享文件/.env' \
  '/Users/<vm_name>/Downloads/Fire_One_en1.2/.env' <<'GUEST'
set -euo pipefail
src=$1
target=$2
target_dir=${target:h}
[[ -f "$src" && ! -L "$src" && -d "$target_dir" && ! -L "$target_dir" ]]
[[ ! -e "$target" || ( -f "$target" && ! -L "$target" ) ]]

backup=''
had_before=0
if [[ -e "$target" ]]; then
  backup=$(/usr/bin/mktemp "$target_dir/.env.before.XXXXXX")
  /bin/cp -p "$target" "$backup"
  /usr/bin/cmp -s "$target" "$backup"
  had_before=1
fi
tmp=$(/usr/bin/mktemp "$target_dir/.env.new.XXXXXX")
rollback=''
cleanup() {
  [[ -z "$tmp" ]] || /bin/rm -f "$tmp"
  [[ -z "$backup" ]] || /bin/rm -f "$backup"
  [[ -z "$rollback" ]] || /bin/rm -f "$rollback"
}
trap cleanup EXIT

/bin/chmod 600 "$tmp"
/bin/cp "$src" "$tmp"
/bin/chmod 600 "$tmp"
/usr/bin/cmp -s "$src" "$tmp"
/bin/sync
/bin/mv -f "$tmp" "$target"
tmp=''
/bin/sync

if ! /usr/bin/cmp -s "$src" "$target" ||
   [[ "$(/usr/bin/stat -f '%Lp' "$target")" != 600 ]]; then
  rollback=$(/usr/bin/mktemp "$target_dir/.env.rollback.XXXXXX")
  if (( had_before )); then
    /bin/cp -p "$backup" "$rollback"
    /bin/mv -f "$rollback" "$target"
    rollback=''
    /bin/sync
    /usr/bin/cmp -s "$backup" "$target"
  else
    /bin/rm -f "$rollback" "$target"
    rollback=''
    /bin/sync
    [[ ! -e "$target" ]]
  fi
  print 'GUEST_ENV_ROLLBACK=verified'
  exit 92
fi
print 'GUEST_ENV_WRITE=atomic_verified'
GUEST
```

2. 上述命令返回 0 且仅显示安全标记 `GUEST_ENV_WRITE=atomic_verified` 才算原子提交完成；若返回 `92`，必须保存 `GUEST_ENV_ROLLBACK=verified` 并进入恢复矩阵，不能把已还原状态当成功。

3. 建立一条新的、仍显式使用同一私钥的 SSH 连接，必须同时验证：

- guest 共享源与目标 `cmp -s` 一致；
- 宿主文件、guest 共享源、guest 目标的 SHA-256 完全相同；
- 目标文件名仍是 `.env`，权限是 `600`；
- `APP_ID`、`VM_NAME`、`CDP_ENDPOINT` 等必填字段各出现一次；
- 密码、短信 token、代理密码等禁止字段不存在；
- 目标文件在新连接中仍可读取，证明已经持久化。

4. 自动校验全部通过后，再做第二重只读完整内容检查：

```bash
ssh -i "$private_key" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=5 \
  '<vm_name>@<vm-ip>' 'cat /Users/<vm_name>/Downloads/Fire_One_en1.2/.env'
```

自动逐项确认输出与宿主 `.env` 及本次已校验数据一致，顶部、描述、固定值和末尾没有截断。`cat` 输出含联系人信息，只能用于当前检查，不得复制到飞书、外部消息或长期日志。

5. 不打开发布工具，不运行任何提审命令。

## 完成标准

```text
UTM_15=verified
SSH_KEY_AUTH=verified
NOTION_SOURCE=api_unique_matched_and_read
ENV_DATA=validated
ENV_WRITE=changed|unchanged
ENV_READBACK=exact
HOST_ENV=GENERATED_AND_VERIFIED
SSH_PRIVATE_KEY=verified
GUEST_ENV_WRITE=atomic_verified
UTM_ENV=SSH_COPIED
UTM_ENV=HASH_VERIFIED
UTM_ENV=PERSISTED
UTM_ENV=CAT_REVIEWED
PUBLISH_COMMAND=NOT_RUN
UTM_16=verified
```

任一标记必须有当前操作产生的直接证据，不得沿用旧运行结果。
全部完成标记均有当前证据后，立即继续 `utm-17`；不得等待用户确认。阻断、失败或未完成状态不得交接。

## 阻断条件

- `NOTION_TOKEN` / `NOTION_ROOT_PAGE_ID` 缺失、integration 无读取权限，或 `verify-parent` 不匹配。
- 页面、heading、紧随其后的 code block 或任一字段缺失、重复、跨页面或无法唯一映射。
- `APP_ID`、`VM_NAME`、联系人姓名或 URL 格式不合法，或 `应用类型：` 原值不在固定转换表。
- 宿主 `.env` 名称不是精确的 `.env`，内容、权限或哈希校验失败。
- VM/IP/SSH 用户不匹配，BatchMode SSH 不通。
- guest 共享源不可读、目标目录不存在或共享源哈希与宿主不一致。
- `cp`、`chmod`、`sync`、`cmp`、新连接复核或最终 `cat` 检查失败。

发生阻断时立即暂停后续副作用，先按对应 `utm-16-*` stage 执行本技能自动恢复矩阵并独立复验；只有恢复穷尽后才发送最后故障卡并等待，同时保留具体阶段和非敏感证据。不得改用 TextEdit 粘贴、把脚本输入 guest Terminal、猜测目标或运行发布命令。
