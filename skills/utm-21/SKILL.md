---
name: utm-21
description: Use after utm-20 when the matching UTM macOS guest needs Codeup Flutter project preparation.
---

# UTM-21：拉取 Flutter 代码、替换标识并安装依赖

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
  --stage 'utm-21:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-21' \
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
| 仓库目录已存在 | 只读验证 origin/main/HEAD、当前 run 的 Bundle/App ID 替换、依赖产物和结构；全部匹配则幂等恢复到第一个未完成步骤 | 非空不匹配/所有权不明为 `unrepairable`，不删除 |
| 四项总命中为零 | 检查是否已替换为目标值；目标增量和旧值为零且结构一致则视为已完成 | 旧/新均无证据为代码语义故障，发卡 |
| pub/pod 失败 | 解析明确错误，自动处理网络瞬态、Pods Manifest/lock 一致性等已知可逆问题一次，再用唯一进程重跑 | 无确定修复或再次失败才 `exhausted` |
| SSH/残留进程 | 同一 VM 恢复；只终止能证明属于本轮误启动的重复进程 | 所有权不明不终止，发卡 |

## 定位

`utm-21` 直接继承 `utm-20` 的当前 `app_name`、四位小写 `vm_name`、原 `chat_id`、同一 UTM guest 和匹配 Notion 页面。不得重新读取运行记录文件，不得用旧 run、`.env`、对话缓存或旧截图代替实时页面。

本技能自动完成代码拉取、全局替换、`flutter pub get` 和 `pod install`。所有检查和操作自动继续；最终检查通过后记录 `UTM_21=verified`，结束本技能并交给 `utm-22`。

本技能不提交、不推送、不发布、不提审，不修改 Notion，也不得重命名、移动或创建包目录。

## SSH 全自动约束

- 直接继承 `utm-20` 的同一精确 VM/IP、`<vm_name>` 和 `SSH_KEY_AUTH=verified`；本技能每条宿主 SSH 调用都必须带 `-o BatchMode=yes -o ConnectTimeout=5`，不重复配置 SSH。
- SSH 连接失败时自动按同一 VM 的精确 MAC 刷新 IP、检查 Remote Login/端口，并用固定 `1234` 恢复 `${SUBMISSION_SSH_PUBLIC_KEY}`；不得向用户索取密码、SSH Key 或 IP。自动恢复仍失败时记录 `SSH_AUTO_RECOVERY=blocked`，先按 `utm-21-ssh-auto-recovery` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
- 目标路径已存在或四项总命中为零是代码现场安全边界，不是 SSH 认证问题；其现有决定流程不得被用来要求用户修 SSH。

## Codeup 认证边界

Codeup 凭据只存在于迁移后本机的 `${PROJECT_ROOT}/.env`：`CODEUP_USERNAME` 与 `CODEUP_PASSWORD`。技能、README、docs、Git URL、运行记录和日志中都不得保存凭据值。完整主机预检只输出两项是否非空，不输出值；任一为空时先重载同一项目 `.env` 并复验，仍为空属于权威凭据缺失，完成恢复证据后才允许发最后故障卡。

克隆时关闭 shell xtrace，用 zsh 内建 `printf` 把用户名、密码、无凭据 URL 和目标路径作为四个 NUL 分隔字段经当前 SSH 的标准输入发送；远端只在该 SSH 进程内存中读取并 `export`，credential helper 只从环境读取。值不得进入本地或远端 argv、临时文件、`.git/config`、终端输出或飞书；命令结束后立即 `unset`。

## 操作步骤

### 一、继承 UTM-20 并实时读取 Notion

1. 沿用 `utm-20` 的 `app_name`、`vm_name`、原 `chat_id` 和 guest；禁止启动、重启或切换新浏览器进程。`${PROJECT_ROOT}/.env` 必须已配置当前父页面的 Notion API 访问。
2. 在 `${PROJECT_ROOT}` 执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，再仅用 `scripts/notion_api.py read-field --copy` 从唯一标题 `<app_name>-<vm_name>` 实时读取：
   - `账号信息` 中唯一的 `代码链接：`；
   - `账号信息` 中唯一的纯数字 `APP_ID：`；
   - `应用信息` 中唯一的 `正式包名: `。
3. 每个字段在即将赋给 `CODE_LINK`、`APP_ID`、`BUNDLE_ID` 时单独执行一次 `read-field --copy`，从 `pbpaste` 赋值后立即清空剪贴板；不得打印或持久化字段值。不得用宿主 Chrome、Notion 插件、Playwright、CUA、坐标或浏览器剪贴板读取 Notion。`代码链接：` 必须是无凭据的 HTTPS Codeup Git 地址，主机严格为 `codeup.aliyun.com`，路径以 `.git` 结束；正式包名必须符合包名格式且不以 `com.example.` 开头。只保留上述三个内存变量，不得输出其他账号字段。

### 二、锁定 guest 与固定路径

4. 直接复用 `utm-20` 继承的 VM IP 和 SSH 身份，用一次 `BatchMode=yes` 只读 SSH 确认用户为 `<vm_name>`、home 为 `/Users/<vm_name>`。正常路径不得重新扫描 VM、MAC 或 ARP；只有继承 IP 已不可达时，才允许按该 `<vm_name>.utm` 的精确配置 MAC 刷新一次 IP，自动恢复同一宿主公钥后重复身份检查，禁止选择其他或“最新”VM。
5. 从 `CODE_LINK` 末段只删除 `.git` 得到 `repo_name`。仓库名必须满足 `re.fullmatch(r"[A-Za-z0-9._-]+", repo_name)` 且 `repo_name not in {'.', '..'}`；URL 解码前后名称必须相同，禁止斜杠、反斜杠、NUL、百分号编码路径分隔符或空名称。
6. 目标固定为 `/Users/<vm_name>/StudioProjects/<repo_name>`。只允许创建父目录 `/Users/<vm_name>/StudioProjects`；不得删除、覆盖、移动、重命名目标或改用其他目录。
7. 对目标路径先做只读分类，不得因为“已存在”就立刻发卡：
   - 不存在：记录 `REPO_STATE=absent`，进入第 8 步安全克隆。
   - 是 Git 仓库，origin 与实时 `CODE_LINK` 逐字一致且无凭据，分支/upstream 为 `main`/`origin/main`，HEAD 与远端 main 一致、工作树为空：记录 `REPO_STATE=existing_pristine_verified`，把克隆视为幂等完成，直接进入第 10 步。
   - 是同一仓库且 diff 只包含本技能规定的占位符替换、依赖锁文件或已验证生成物：按完成标记与 diff 对账，记录 `REPO_STATE=resume_current_run`，确定性恢复到第一个未完成步骤；不得重新替换已成功内容或重新安装已验证依赖。
   - 不是仓库、origin/分支/远端身份不同，或存在无法归属于本技能的改动：用三个新的只读 SSH 会话分别核对路径、owner、origin、HEAD 和 diff。三轮仍冲突时记录 `AUTO_RECOVERY_ATTEMPTS=3`、`AUTO_RECOVERY_ACTIONS=repo-identity+origin+head+diff-recheck-three-rounds`、`AUTO_RECOVERY_RESULT=unrepairable`，才以 `utm-21-repo-path-existing` 进入文件开头的最后故障卡；禁止自动删除或重置用户代码。

### 代码现场自动恢复边界

目标路径冲突或占位符总命中为零时，先执行上述仓库分类及第 10 步的最终值/声明位置对账。只有不同仓库、用户改动冲突或无法唯一确定替换位置这类智能体不能安全修复的状态，才使用文件开头统一的 `notify-fault`（必须带恢复次数、动作、结果和必要时 `--unrepairable`）并等待同一张卡。`manual_continue`、`retry_skill` 都必须重新从只读分类开始，不能直接重复发卡。

### 三、明确拉取远程 main

8. 仅当 `REPO_STATE=absent` 时重新确认目标不存在，再调用项目的安全克隆入口；参数中只允许当前 run、VM、IP 和 Notion 页面身份，不得传入代码链接或凭据。`existing_pristine_verified`/`resume_current_run` 分支禁止调用克隆入口：

   ```zsh
   python3 scripts/utm_21_clone.py \
     --run-id '<current_run_id>' \
     --vm-name '<vm_name>' \
     --vm-ip '<vm-ip>' \
     --parent-title '<宿主机名称>' \
     --page-title '<应用名>-<vm_name>'
   ```

   该入口重新通过 Notion API 读取唯一无凭据 Codeup URL、重新核对 run 宿主机和 `vm_name`，从本机 `.env` 读取凭据，并把凭据与 URL 作为 NUL 分隔数据直接送到 SSH stdin。它不会把值放进 argv、文件或日志；远端只在单个进程内存中使用，退出即清空。目标已存在时入口在 `git clone` 前退出，绝不删除、覆盖、移动或改名。
9. `REPO_STATE=absent` 时保留克隆原始 Git 输出，但不得输出代码链接或凭据；成功必须同时出现 `CLONE_EXIT=0`、`CLONE_VERIFY=verified`、`UTM_21_RUN_HOST=verified` 和 `UTM_21_CODEUP_CREDENTIAL_CHANNEL=stdin_memory_only`。`existing_pristine_verified` 或 `resume_current_run` 不伪造 clone 退出码，分别记录 `CLONE_EXIT=not_run_existing` 或 `CLONE_EXIT=not_run_resume`。三条路径统一用新只读 SSH 验证无凭据 origin、`main`/`origin/main`、本地 HEAD/跟踪 HEAD/远端 main 三者一致、预期工作树状态和 `git fsck --full`，再分别落盘为 `CLONE_RESULT=created|existing_pristine|resumed`；竖线表示三种允许值。

### 四、不区分大小写搜索并替换

10. 四个搜索词统一使用 `git grep -I -i`，只搜索 Git 跟踪文本文件，不区分大小写：

    ```text
    com.example.test.demok1
    com.example.<app_name>
    5372311233
    jltest.test.test
    ```

    第二项用实时 `app_name` 原值拼接。先按 Unicode `casefold` 对四个旧值去重；同一旧值若映射到不同目标立即判定合同冲突，不得替换。逐项记录命中次数、实际命中的原始大小写和文件名，单项允许为 0，但不得输出当前目标值。总命中大于 0 时记录 `PLACEHOLDER_STATE=needs_replacement`。总命中为 0 时不得立刻发卡：先用 `git grep -I -i -F` 搜索最终 `BUNDLE_ID` 与 `APP_ID`，再只读检查 Git 跟踪文件中的 `PRODUCT_BUNDLE_IDENTIFIER`、`applicationId`、manifest/package、Info.plist 与项目既有 App ID 声明位置。若最终值已存在且声明一致，记录 `PLACEHOLDER_STATE=already_replaced` 并幂等继续；只有最终值不存在、声明位置不唯一或存在其他正式标识冲突，经过两条新 SSH 的独立扫描仍无法安全映射时，才记录 `AUTO_RECOVERY_RESULT=unrepairable` 并以 `utm-21-all-zero-match` 进入最后故障卡。

11. 用 `git grep -Ilz -i -F` 取得 NUL 分隔的并集文件清单，只修改该清单内的 Git 跟踪普通文本文件。四项替换规则如下：
    - `com.example.test.demok1` → `BUNDLE_ID`；
    - `com.example.<app_name>` → `BUNDLE_ID`；
    - `5372311233` → `APP_ID`；
    - `jltest.test.test` → `BUNDLE_ID`。

    替换实现固定为 Python 字面量算法，不能使用 shell/正则替换工具：
    1. 通过当前 SSH stdin 先传入 `app_name`、`BUNDLE_ID`、`APP_ID` 三个 NUL 分隔字段，远端 zsh 只在该进程内存中读取并导出；值不得进入 argv、文件或输出。剩余 stdin 是固定 Python 程序。
    2. Python 对旧值执行 `casefold` 去重，按长度降序用 `re.compile("|".join(re.escape(old) ...), re.IGNORECASE)` 构造一次性联合模式；回调按 `match.group(0).casefold()` 查固定映射。这样每个原始区间只替换一次，不发生“第一个目标又被第二条规则再次命中”的级联。
    3. 用 `subprocess.run(["git", "grep", "-Ilz", "-i", "-F", ...], stdout=PIPE, check=False)` 读取 NUL 清单；退出码只允许 0 或 1。每个路径必须是仓库内 Git 跟踪的非符号链接普通文件，UTF-8 严格解码成功。
    4. 在 guest `/tmp/utm-21-replace-<stable-attempt-id>/` 创建 mode-700 before 目录；按相对路径复制全部待改文件并保存原 mode/SHA-256。修改时每个文件都写入同目录 mode 相同的临时文件、`fsync` 后 `os.replace`，不得原地截断。
    5. mode-600 `replacement-ledger.json` 固定记录去重后的每个旧值命中数、每个文件替换数、预期修改路径集合、before/after SHA-256 和状态，不记录当前目标值。任一写入、计数或回读失败时，使用 before 副本逐文件原子还原，并用新进程验证路径集合、mode 和 SHA-256 全部恢复后才退出。

    替换前后对全部仓库目录相对名称排序并计算 SHA-256，两个哈希必须一致。不得执行 IDE `Refactor/Rename`、`mv`、`git mv` 或任何包目录整理。

12. 新建 SSH 连接，用 `git grep -I -i -F` 验证去重后的每个旧值残留均为 0；ledger 中三个包名映射的替换事件总数必须等于其去重后原命中总数，数字映射事件数必须等于数字旧值原命中数，逐文件 after SHA-256 必须匹配当前文件。数字旧值原命中为 0 时不得主动插入 APP ID。全部一致后记录 `REPLACEMENT_LEDGER=verified`；`PLACEHOLDER_STATE=already_replaced` 分支则用两条独立 SSH 验证目标声明，无文件写入，ledger 明确记录 `write_count=0`。
13. 此阶段 `git status --porcelain` 只能出现 ledger 预期已修改的跟踪文件；不得出现新增、删除、重命名、复制或未跟踪路径。执行 `git diff --check`。以上独立验证全部成功后才删除 guest 临时 before 目录；验证失败且还原未确认时必须保留它用于恢复。

### 五、SSH 登录环境执行 Flutter

14. 普通非交互 SSH 不保证加载 `~/.zshrc`，可能找不到 Flutter/Dart。Flutter 命令必须在同一 SSH 调用中使用 `/bin/zsh -lic`，先确认工作目录、`command -v flutter` 和 `command -v dart`。
15. zsh 中 `path` 会联动覆盖 `PATH`，`status` 是只读特殊变量。脚本变量只能使用 `cmd_path`、`cmd_rc`、`git_state` 等普通名称，禁止把 `path` 或 `status` 当临时变量。
16. 为避免 `PUB_HOSTED_URL` 把 `pubspec.lock` 的来源从 `pub.dev` 改成镜像，本次命令只临时取消镜像变量，不修改 `~/.zshrc`：

    ```zsh
    /bin/zsh -lic 'cd /Users/<vm_name>/StudioProjects/<repo_name> && env -u PUB_HOSTED_URL -u FLUTTER_STORAGE_BASE_URL flutter pub get'
    ```

17. 只启动一个 `flutter pub get`。使用可持续轮询的同一宿主执行会话等待，不得因长时间无输出再启动第二个命令。首次运行可能执行 Flutter SDK `git fetch --tags`；出现 `Waiting for another flutter command to release the startup lock...` 时先检查进程，禁止删除 Flutter lockfile。只有明确属于本次误启动的重复等待进程才允许温和终止，主进程必须保留。
18. 将 `flutter pub get` 原始终端输出和宿主 SSH 退出码输出到对话。成功必须同时满足：
    - 输出包含 `Got dependencies!`；
    - 退出码为 0；
    - `.dart_tool/package_config.json` 存在；
    - 没有残留 `flutter_tools.snapshot pub get` 或 `dart pub ... get` 进程；
    - `pubspec.lock` 不含 `https://pub.flutter-io.cn`；
    - `git diff --check` 通过。

    `packages have newer versions incompatible with dependency constraints` 和 `flutter pub outdated` 只是版本提示，不是错误。`pubspec.lock` 合法的依赖版本/校验值更新可以保留，但必须输出差异摘要；镜像 URL 改写必须消除。

### 六、在 ios 目录执行 CocoaPods

19. 使用同一登录环境进入精确目录并执行一次：

    ```zsh
    /bin/zsh -lic 'cd /Users/<vm_name>/StudioProjects/<repo_name>/ios && printf "PWD=%s\n" "$PWD" && command -v pod && pod install'
    ```

20. 将 `pod install` 原始终端输出和宿主 SSH 退出码输出到对话。成功必须同时满足：
    - `PWD` 严格等于 `/Users/<vm_name>/StudioProjects/<repo_name>/ios`；
    - `pod` 路径非空；
    - 输出包含 `Pod installation complete!`；
    - 退出码为 0；
    - `ios/Pods` 与 `ios/Podfile.lock` 存在；
    - 没有残留 CocoaPods 进程；
    - `git diff --check` 通过。

21. `[!] Automatically assigning platform iOS ...` 与 `[!] CocoaPods did not set the base configuration ...` 是警告，不单独判失败，但必须原样输出并在最终结果中说明；不得自动修改 Podfile 或 Xcode base configuration。`ios/Podfile.lock` 中 CocoaPods 版本变化可以保留并报告。

### 七、最终检查与 UTM-22 交接

22. 最终新建 SSH 连接验证：
    - 四个旧值按不区分大小写搜索均无残留；
    - 分支仍为 `main`，upstream 仍为 `origin/main`；
    - 目录树哈希与替换前一致；
    - 允许的已修改跟踪文件仅为替换文件并集、`pubspec.lock` 和 `ios/Podfile.lock`；
    - 无新增、删除、重命名、复制或未跟踪路径；
    - `git diff --check` 通过；
    - Flutter 与 CocoaPods 命令均无残留进程。
23. 输出克隆、替换、Flutter、CocoaPods 与警告摘要。全部验证通过后记录 `UTM_21=verified`，把已验证的 VM IP、SSH 用户/home 和 `REPO_PATH` 直接交给 `utm-22`；本技能不启动任何 IDE，不得等待用户确认。阻断、失败或未完成状态不得交接。

## 完成标准

```text
UTM_20=verified
SSH_KEY_AUTH=verified
NOTION_PAGE=api_unique_matched
CODE_LINK=live_notion_api_verified
BUNDLE_ID=live_notion_api_verified
APP_ID=live_notion_api_verified
VM_SSH=verified
REPO_PATH=/Users/<vm_name>/StudioProjects/<repo_name>
REMOTE_MAIN=verified
CLONE_RESULT=created|existing_pristine|resumed
CLONE_EXIT=0|not_run_existing|not_run_resume
PLACEHOLDER_STATE=needs_replacement|already_replaced
CASE_INSENSITIVE_REPLACEMENTS=verified
REPLACEMENT_LEDGER=verified
PACKAGE_DIRECTORY_TREE=unchanged
PUB_GET_EXIT=0
PUB_GET_OUTPUT=Got dependencies!
PUBSPEC_MIRROR_RESIDUAL=0
POD_INSTALL_EXIT=0
POD_INSTALL_OUTPUT=Pod installation complete!
GIT_DIFF_CHECK=passed
UTM_21=verified
```

## 阻断条件

- UTM-20 上下文、guest、Notion API 父页面、匹配页面或三个字段无法唯一匹配。
- 目标路径已存在时先自动分类为同一 pristine、同 run resumable 或外部 conflict；前两类自动验证/续跑。只有所有权证据三轮仍冲突且不能安全修复时才阻断并进入最后故障卡，卡片决定后仍重新执行同一分类。
- 克隆退出码非 0、输出含错误、origin/远程 main/本地 HEAD 不一致或初始工作区不干净。
- 四项总命中为 0 时先自动对账实际声明是否已经等于目标值，并按模板合同/目标值/路径账本三轮复验；已完成则继续。只有外部模板合同冲突或恢复穷尽才进入最后故障卡等待。替换后有旧值残留、目标增量不符、目录树变化或非预期路径状态时先执行同一账本回滚、重读和独立复验，仍不一致才阻断。
- SSH 登录环境中 Flutter、Dart 或 CocoaPods 不可用。
- `flutter pub get` 或 `pod install` 退出码非 0、缺少成功文本、生成物缺失、进程残留或 `git diff --check` 失败。
- `pubspec.lock` 仍含镜像 URL，或命令产生无法解释的跟踪文件变化。

阻断时保留现场与非敏感原始输出，先按本技能矩阵自动诊断、修复和复验；恢复穷尽或所有权/模板合同冲突不可安全修复时，才向继承的原 `chat_id` 发送最后故障卡。不得删除仓库、删 Flutter lockfile、回滚用户修改、自动修警告、提交、推送或越过阻断进入 `utm-22`。
