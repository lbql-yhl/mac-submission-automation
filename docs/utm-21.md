# UTM-21：拉取代码、替换标识并交接 Xcode workspace

对应技能：`utm-21`。

SSH 直接继承 `utm-p8` 已验证的同一 VM/IP/用户和固定密码身份。连接失效时只对同一精确 VM 自动刷新 IP、修复 Remote Login 并用固定 `1234` 恢复，不得向用户索取密码、SSH Key、IP 或等待 SSH 人工处理。仓库读取和克隆统一由 `scripts/utm_21_clone.py` 完成：代码链接由 Notion API 在脚本内读取，Codeup 凭据只从本机 `.env` 进入内存并通过 SSH stdin 使用，不出现在 URL、argv、日志或仓库配置中。

## 前置检查

- [ ] `utm-p8` 已完成，沿用当前 `app_name`、`vm_name`、原 `chat_id` 和同一 UTM guest。
- [ ] 在项目根目录先运行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，再通过 `read-field --copy` 从唯一 `<app_name>-<vm_name>` 页面实时读取 `代码链接：`、`APP_ID：`、`正式包名: `；不读取 `runtime/feishu-runs.json`，不用旧 run、`.env` 或对话缓存。
- [ ] 复用 `utm-p8` 继承的 VM IP，只做一次固定密码 SSH 用户/home 检查；连接失效时按上面的 SSH 全自动约束恢复。
- [ ] 所有步骤自动继续；最终检查通过后记录 `UTM_21=verified`，由 `utm-22` 接手。

## 操作 Checklist

### 拉取远程 main

- [ ] 只通过 `scripts/notion_api.py` 从 `账号信息` 读取唯一无凭据 HTTPS Codeup `代码链接：` 和纯数字 `APP_ID：`，从 `应用信息` 读取唯一合法 `正式包名: `；每个值从 `pbpaste` 赋给内存变量后立即清空剪贴板，不打印、不持久化，不用宿主浏览器或插件读取 Notion。
- [ ] 仓库目标固定为 `/Users/<vm_name>/StudioProjects/<repo_name>`；`repo_name` 必须由无凭据 HTTPS URL 的最后一个路径段唯一推导，去掉最后的 `.git` 后仍非空，且不得是 `.`、`..` 或含斜杠/控制字符；只可创建 `StudioProjects` 父目录。
- [ ] 目标已存在时不删除、不覆盖、不换目录；先自动分类为 `pristine_complete`、`resumable_current_run` 或 `conflict`。前两类在核对 origin/main/upstream/HEAD、远端 HEAD、fsck 和工作区状态后自动继续或从首个未完成检查点恢复；只有 remote/所有权/历史不匹配的真实冲突才作为 `unrepairable` 进入最后故障卡。
- [ ] 固定 Codeup 凭据仅用于临时 credential helper，不拼入 URL、不写入仓库和日志，结束后立即清除。
- [ ] 执行 `python3 scripts/utm_21_clone.py --run-id '<run_id>' --page-title '<应用名>-<vm_name>'`；脚本在 guest 内等价执行单分支 `main` 克隆，只输出非敏感状态、计数与退出码，绝不回显代码 URL、用户名、密码或 credential helper 内容。新克隆记录 `CLONE_RESULT=created`/`CLONE_EXIT=0`；已验证的同一 pristine 仓库记录 `existing_pristine`/`not_run_existing`；同 run 可续传仓库记录 `resumed`/`not_run_resume`，不伪造克隆退出码。
- [ ] 新 SSH 连接验证 `origin` 无凭据、当前分支为 `main`、upstream 为 `origin/main`、本地/远程 HEAD 一致、工作区干净且 `git fsck --full` 通过。

### 四项不区分大小写替换

- [ ] 用 `git grep -I -i` 只搜索 Git 跟踪文本文件，逐项输出命中数、原始大小写和文件名：
  - `com.example.test.demok1`
  - `com.example.<app_name>`
  - `5372311233`
  - `jltest.test.test`
- [ ] 单项允许 0 命中；四项总命中为 0 时先自动读取当前 Bundle ID、App ID 及 Android/iOS 实际声明位置，比较权威目标值与仓库现状。若所有实际声明已经等于目标值，记录 `PLACEHOLDERS_ALREADY_REPLACED=verified` 并继续；若可证明是不同模板或无可替换声明，才作为不可安全修复的代码合同冲突进入最后故障卡。不得为了制造命中而插入占位符。
- [ ] 将三个包名占位符替换为 API 实时读取的 `正式包名: `，将 `5372311233` 替换为实时 `APP_ID：`；数字旧值无命中时不得主动插入 APP ID。先对旧值做 Unicode `casefold` 去重；同一旧值若映射到不同目标立即停止，不得按顺序覆盖。
- [ ] 只修改 `git grep -Ilz -i -F` 得到的 Git 跟踪文本文件。用一个 Python 字面量、不区分大小写的合并替换事务：先保存每个文件的 before 字节/模式/SHA-256 与命中计数，再临时文件 + `fsync` + 原子替换，写后独立回读。任一文件失败必须用 ledger 将本轮已更改文件全部还原并复验，不得留下半替换状态。
- [ ] 替换前后计算全部目录名的排序 SHA-256，必须一致；禁止 `mv`、`git mv`、IDE Refactor/Rename 或创建包目录。
- [ ] 新 SSH 连接确认四个旧值按大小写不敏感搜索均无残留，新值增量与旧值原命中数一致。
- [ ] 不得出现新增、删除、重命名、复制或未跟踪路径；`git diff --check` 必须通过。

### 既有 Xcode workspace

- [ ] 新 SSH 连接只读验证 `/Users/<vm_name>/StudioProjects/<repo_name>/ios/Runner.xcworkspace` 是当前用户所有的既有非符号链接目录，真实路径仍位于本轮 `REPO_PATH/ios` 下，且唯一 `contents.xcworkspacedata` 是非空普通非符号链接文件。
- [ ] 不生成、修复、复制或改选其他 workspace；缺失或不安全时三轮只读复核同一目标，仍不符合才进入最后故障边界。
- [ ] 记录 `RUNNER_WORKSPACE_SOURCE=existing_verified` 和 `DEPENDENCY_INSTALL_COMMANDS=not_run`。本技能不执行安装、更新、缓存、生成或锁文件命令，也不修改 shell PATH。

### 最终检查与 UTM-22 交接

- [ ] 新 SSH 连接确认分支仍为 `main`/`origin/main`，四个旧值无残留，目录树哈希一致。
- [ ] 允许修改的跟踪文件仅为 replacement ledger 记录的替换文件并集；无任何非预期路径状态。
- [ ] 输出克隆、替换、Git 状态和 workspace 摘要；全部验证通过后记录 `UTM_21=verified` 并结束，不启动任何 IDE，不等待用户确认。
- [ ] 把已验证的 VM IP、SSH 用户/home 和 `REPO_PATH` 直接移交 `utm-22`；下一步只做一次身份/workspace 存活检查后确认 Xcode。

## 完成标准

```text
UTM_19=verified
NOTION_PAGE=api_unique_matched
CODE_LINK=live_notion_api_verified
BUNDLE_ID=live_notion_api_verified
APP_ID=live_notion_api_verified
REPO_PATH=/Users/<vm_name>/StudioProjects/<repo_name>
REMOTE_MAIN=verified
CLONE_RESULT=created|existing_pristine|resumed
CLONE_EXIT=0|not_run_existing|not_run_resume
PLACEHOLDER_STATE=needs_replacement|already_replaced
CASE_INSENSITIVE_REPLACEMENTS=verified
REPLACEMENT_LEDGER=verified
PACKAGE_DIRECTORY_TREE=unchanged
RUNNER_WORKSPACE_SOURCE=existing_verified
DEPENDENCY_INSTALL_COMMANDS=not_run
GIT_DIFF_CHECK=passed
SSH_PASSWORD_AUTH=verified
UTM_21=verified
```

## 风险点

- 不读取旧运行记录，不重新选择分支，不提交、不推送、不发布、不提审、不修改 Notion。
- 不删除已有目标仓库，不修改目录包路径，不生成或修复 workspace，不运行任何依赖安装命令。
- 任一数据不能唯一匹配、workspace 缺失或不安全、残留旧值、目录树变化或非预期 Git 状态时先执行三轮恢复/只读复核；恢复穷尽后才发最后故障卡。
