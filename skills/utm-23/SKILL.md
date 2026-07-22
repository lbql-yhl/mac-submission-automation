---
name: utm-23
description: Use when the same signed-in UTM guest has completed utm-22 and is ready to prepare the App Store Connect review draft for handoff.
---

# UTM-23：准备审核草稿并移交 UTM-24

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
  --stage 'utm-23:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-23' \
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
| 页面/菜单/IAP 误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图；`Escape`/`Cancel` 回当前页面锚点，确定性恢复到第一个未完成步骤并记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立分类后仍失败才发卡 |
| `Add Build` 暂不可见 | 在 `utm-22 COMPLETE+VALID` 前提下 15/30/60/120 秒只读刷新构建可见性；记录 `ADD_BUILD_VISIBILITY_POLL=exhausted` 后发卡，任何情况不得重复上传 | 不用任何上传动作探测状态 |
| IAP 部分准备 | 对唯一草稿逐项读取 14 项状态，只补未加入项；选错时 Cancel、重新 See More/Edit/Selected(14) | 多草稿/归属不明为 `unrepairable` |
| App Information 删除 | 删除前证据快照，核对删除确认弹窗的应用/区域/精确值，只执行一次；结果不明只读查是否仍存在 | 无唯一 Remove/恢复证据时不删并发卡 |

## 定位

本技能在 `utm-22` 完成后复用同一台 UTM guest 中既有 Microsoft Edge，并先执行只读已准备恢复分支。若现场已满足完整终态，只保存并验证当前 run 的 `02-iap-drafts.png`、`03-app-information.png` 后直接移交；部分准备先建立逐项状态账本，自动恢复到第一个唯一未完成步骤，不能因为流程中断就发卡。只有多草稿、归属冲突或不可逆结果经三轮独立只读核对仍不明确时，才在恢复穷尽后发送最后三按钮故障卡。明确未准备的初始状态进入正常路径，完成构建附加、合规、14 项内购与 App Version 唯一草稿及 App Information 清理。全部复核通过后保留当前 VM、guest Edge 进程、App Store Connect 会话和标签页，立即继续 `utm-24`。

这是对既有 guest Edge 进程的明确复用授权；允许在该进程中打开新标签页，不允许启动、重启或切换到其他浏览器进程，也不得影响宿主 Google Chrome。

## 快速边界

| 允许 | 禁止 |
|---|---|
| 切回同一 guest 的既有 Edge，优先复用已有 App Store Connect 标签页 | 已有页面时仍新开重复标签、启动或重启 Edge |
| 没有已有页面时，原生剪贴板核对后使用高亮的 `Paste and Go` | 键盘逐字输入网址、盲粘贴、复用旧坐标 |
| 点击顶部全局 `Apps`，再点击精确且唯一匹配的应用名 | 登录账号、处理 2FA/CAPTCHA、点击加号或错误应用 |
| `Add Build` 暂不可见时只做有界等待和同一 Build API 查询 | 任何再次上传、重新 Archive、重新构建、重新封装或改传其他 IPA |
| 有界只读恢复穷尽后才向原 `chat_id` 发最后故障卡 | 向日报群发卡、跳过告警或继续盲点页面 |
| 部分准备时建立状态账本并确定性恢复到第一个未完成步骤；真正歧义经三轮独立只读核对后才进入最后三按钮故障卡 | 静默结束技能、要求用户确认/授权、把卡片反馈当成第二次触发，或在歧义现场猜测性补齐 |
| 使用 `See More` 展开 14 项后再 `Edit`；所有内购与版本只加入同一个既有 Draft Submission | 在任何位置选择 `Create New Submission`、重建草稿或写死失败项目名称/数量 |
| 在最终 IAP 与 App Information 页面分别保存 `02-iap-drafts.png`、`03-app-information.png` | 保存或覆盖 `01-media-manager.png`、`04-privacy-agreement.png`、`05-small-business.png` |
| 清除两个 App Information 区域中的实际已配置记录，复核唯一草稿后原样移交现场 | 把 `Get Started`/`Add`/`Declare Regulated Medical Device`/`Set Up URL` 当成已配置数据，或在本技能发送提审确认、等待决定、点击 `Submit for Review` |

## 操作步骤

1. 确认已有 `UTM_22=verified`、`BUILD_UPLOAD_FINAL_STATE=COMPLETE` 和 `BUILD_PROCESSING_STATE=VALID`；直接继承当前 `run_id`、原 `chat_id`、App ID、Bundle ID、版本、构建号、同一 `vm_name`、started VM 和既有 Edge。正常入口不重新读取 run，也不预检仅 `Add Build` 缺失恢复才需要的 IPA 路径、IPA SHA-256 或 API Key 元数据；任何动态值不得从旧 run、记忆或“最新 IPA”猜测。先要求当前 `run_id` 匹配 `^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$`，再复用当前 Computer Use 的同一 `node_repl`/`sky` GUI 驱动会话准备截图保存函数；该驱动器不是本项目流程中的额外技能：

   ```javascript
   var reviewRunId = "<当前 run_id>";
   if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(reviewRunId)) throw new Error("invalid run_id");
   var fs = await import("node:fs/promises");
   var path = await import("node:path");
   var { randomUUID } = await import("node:crypto");
   var { execFile } = await import("node:child_process");
   var { fileURLToPath } = await import("node:url");
   var { promisify } = await import("node:util");
   var execFileAsync = promisify(execFile);
   if (!process.env.PROJECT_ROOT) throw new Error("PROJECT_ROOT is not exported");
   var projectRoot = await fs.realpath(process.env.PROJECT_ROOT);
   var reviewRoot = path.join(projectRoot, "runtime", "review-screenshots", reviewRunId);
   var relativeRoot = path.relative(projectRoot, reviewRoot);
   if (!relativeRoot || relativeRoot.startsWith("..") || path.isAbsolute(relativeRoot)) {
     throw new Error("review screenshot path escaped project root");
   }
   await fs.mkdir(reviewRoot, { recursive: true, mode: 0o700 });
   await fs.chmod(reviewRoot, 0o700);
   var allowedReviewNames = new Set(["02-iap-drafts.png", "03-app-information.png"]);
   globalThis.saveReviewScreenshot = async function (name) {
     if (!allowedReviewNames.has(name)) throw new Error("screenshot name not owned by utm-23");
     var state = await sky.get_app_state({ app: "com.utmapp.UTM", disableDiff: true });
     if (!state.screenshot?.url) throw new Error("UTM screenshot unavailable");
     var target = path.join(reviewRoot, name);
     var temporary = path.join(reviewRoot, "." + name + "." + randomUUID() + ".tmp");
     try {
       var old = await fs.lstat(target).catch(error =>
         error.code === "ENOENT" ? null : Promise.reject(error));
       if (old?.isSymbolicLink() || (old && !old.isFile())) {
         throw new Error("invalid existing screenshot");
       }
       await execFileAsync("/usr/bin/sips", [
         "-s", "format", "png", fileURLToPath(state.screenshot.url), "--out", temporary
       ]);
       await fs.chmod(temporary, 0o600);
       var handle = await fs.open(temporary, "r");
       var magic = Buffer.alloc(8);
       await handle.read(magic, 0, 8, 0);
       await handle.sync();
       await handle.close();
       var stat = await fs.lstat(temporary);
       if (!stat.isFile() || stat.isSymbolicLink() || stat.size === 0 ||
           !magic.equals(Buffer.from([137,80,78,71,13,10,26,10]))) {
         throw new Error("invalid PNG screenshot: " + name);
       }
       await fs.rename(temporary, target);
       var directory = await fs.open(reviewRoot, "r");
       await directory.sync();
       await directory.close();
     } finally {
       await fs.rm(temporary, { force: true });
     }
     return target;
   };
   ```

   本技能只能调用该函数保存 `02-iap-drafts.png` 和 `03-app-information.png`。每次保存后都用宿主只读检查确认文件位于当前 run 目录、权限 `600`、非空、可读为 PNG，并记录 SHA-256；不得从旧 run、对话附件或“最新截图”回退。
2. 返回目标 UTM guest，等待至少 3 秒并读取最新画面。确认当前 Microsoft Edge 是该 guest 中已经存在的同一浏览器进程。首次未看到 Edge 时不得立即判 blocked：分别读取 UTM 窗口/前台应用归属和该精确 VM 内现有 Edge PID/启动参数，不做启动或重启；按 0/5/10 秒做满三轮独立只读。进程存在但窗口被遮挡时只激活同一既有进程并重读；三轮都证明进程不存在，或进程身份不属于当前 VM，才记录 `BROWSER_SESSION_RECHECKS=3`、`BROWSER_PROCESS_GUARD=blocked` 并进入自动恢复矩阵。存在并匹配时记录实际完成的轮数和 `BROWSER_PROCESS_GUARD=verified`。
3. 切回该 Edge，等待至少 3 秒并重新读取画面。先检查当前页面和标签栏：
   - 若已有标题为 `App Store Connect` 的标签页，切换到该已有页面，等待至少 3 秒并重新读取画面；必须确认当前 URL 属于 `appstoreconnect.apple.com` 且页面已登录。已有页面时禁止新开重复标签，也不粘贴网址。
   - 若没有任何已有 App Store Connect 页面，才继续第 4 步。
4. 仅在没有已有页面时，点击 `+` 新开一个标签页；等待至少 3 秒并确认新标签页和地址栏已就绪。调用 `OP-BROWSER-URL-NO-SCHEME`，使用统一执行器准备正文批准的裸地址：

   ```bash
   printf '%s' 'appstoreconnect.apple.com' | python3 scripts/shared_operations.py browser-url --allow-bare
   ```

5. 只有 `BROWSER_URL_CLIPBOARD=verified` 才继续。重新确认目标仍是 guest Edge 新标签页的地址栏；右键打开当前菜单，等待至少 3 秒并读取最新画面，只有可见、可用且蓝色高亮的 `Paste and Go` 才点击。不得键入网址、盲按快捷键或添加协议头。
6. 点击后立即执行 `pbcopy </dev/null` 并确认 `pbpaste` 为空。等待至少 3 秒并重新读取页面。无论复用已有标签还是新打开页面，都必须确认：当前页面属于 `appstoreconnect.apple.com`，可见 App Store Connect 已登录页面，页面已稳定且没有登录表单、安全验证或错误提示。
7. 重新读取最新画面，只定位页面最上方全局导航中的 `Apps`；不得把应用名、页面标题旁的加号或其他局部控件当作目标。点击顶部 `Apps` 一次，等待至少 3 秒并重新读取页面。
8. Apps 列表成功必须同时满足：当前 URL 为 `appstoreconnect.apple.com/apps`，页面主标题显示 `Apps`，应用列表已稳定可见且没有错误或安全提示。
9. 从当前流程继承并重新确认目标应用名。在最新 Apps 列表中，应用名必须精确匹配且只出现一次；点击该应用名一次，等待至少 3 秒并重新读取页面。不得点击应用图标旁的加号、更多菜单或近似名称。
10. 应用详情页必须同时满足：当前 URL 含 `/apps/<纯数字 App ID>/`，页面页头显示精确匹配的应用名，应用详情内容已稳定显示且没有错误或安全提示。
11. 在判定 `Add Build` 前先建立并读取**持久状态账本**。固定路径为 `${PROJECT_ROOT}/runtime/utm-23-attempts/<current-run-id>/preparation.json`；父目录 mode 700，账本通过同目录 mode-600 临时文件、文件/目录 `fsync` 和原子替换写入，每次写后由新进程回读 JSON/权限。固定 schema 含 run/原 chat/host/VM/IP、App 数字 ID/Bundle ID/版本/构建号、Edge PID/标签 URL，以及下列有序步骤对象：`build_attached`、`compliance_cleared`、`game_center_unchecked`、`version_saved`、`one_draft`、`iap_14_linked`、`app_version_linked`、`screenshot_02`、`regulations_empty`、`server_notifications_empty`、`screenshot_03`；每项只有 `not_started|in_progress|verified|ambiguous`、证据 hash、更新时间和可选 stable attempt ID。已有账本必须与当前身份字段完全一致，冲突不得覆盖；成功记录 `PREPARATION_LEDGER_MODE=600`。

    然后执行**只读已准备恢复分支**。聚焦主内容的非控件空白处，每次只移动一页；每次移动或切换页面后等待至少 3 秒并重新读取最新画面。只有当前 run/原 `chat_id`、同一 `vm_name`/started VM、既有 guest Edge、应用名/数字 App ID/版本和构建号均唯一且无歧义时，才按实时页面走一个分支，并把每项最新分类原子写回同一账本：
    - 若精确构建已附加且记录 `BUILD_ATTACHED=verified`、`Missing Compliance 已清除`并可记录 `EXPORT_COMPLIANCE_STATUS=cleared`、`Game Center` 明确未勾选并可记录 `GAME_CENTER_CHECKBOX=unchecked`、版本页已保存并可记录 `VERSION_PAGE=saved`，同时恰好一个 `Draft Submissions (1)` 包含当前 App Version 与 `In-App Purchases (14)`、左侧为 `Ready for Review`、两个 App Information 目标分别为 `APP_STORE_REGULATIONS_PERMITS=empty` 和 `APP_STORE_SERVER_NOTIFICATIONS=empty`，且 `SUBMIT_FOR_REVIEW=not_clicked`：记录 `PREPARATION_STATE=complete`。在这次只读检查已经到达的 IAP 列表顶部，必要时只点击 `See More`，确认 `Drafts (14)`、14 项全部可见且可见状态均为 `Ready for Review`，执行 `await saveReviewScreenshot("02-iap-drafts.png")` 并通过文件检查后记录 `REVIEW_SCREENSHOT_02=verified`；在已经到达的 App Information 顶部确认同一应用、左侧版本 `Ready for Review`、主标题、Name、Bundle ID 和 Category 同时可见，执行 `await saveReviewScreenshot("03-app-information.png")` 并通过文件检查后记录 `REVIEW_SCREENSHOT_03=verified`。两张图均验证后记录 `ALREADY_PREPARED_CHECK=verified`，直接进入最终移交复核，即第 32 步从“重新核对当前 run”开始的部分。此分支不得点击 `Add Build`、不得重新组织内购、不得重新添加 App Version、不得清理 App Information，也不得点击任何保存或提交控件。
    - 若现场明确仍是从 `utm-22` 首次进入、尚未开始上述准备的初始状态：记录 `PREPARATION_STATE=untouched` 和 `ALREADY_PREPARED_CHECK=not_present`，完整检查当前应用版本页直到预期的 `Build` 区域或页面稳定底部；不得把顶部 `Add for Review` 当作目标。只有 URL、应用名、版本页均匹配，页面无加载中、网络错误或安全提示，并且已完成这次逐页检查，才允许进入第 12 步判定 `Add Build` 是否存在。
    - 若现场是部分准备：按固定顺序建立账本 `build attached → compliance cleared → Game Center unchecked → version saved → one draft → 14 IAP linked → App Version linked → screenshot 02 → App Information cleanup → screenshot 03`。每项只允许 `verified`、`not_started`、`in_progress`、`ambiguous`；用最新页面与当前 run 证据交叉验证。所有已验证项原样保留，唯一 `not_started`/可判定 `in_progress` 项作为第一个未完成步骤，从对应正文步骤继续，记录 `PREPARATION_STATE=partial_recoverable` 和 `DETERMINISTIC_RESUME_STEP=<n>`。误开弹窗先 `Cancel`，误入页面先 `Back` 到账本锚点，再重读后继续；不得上传、重新建草稿或重复已完成的不可逆动作。
    - 只有某项为 `ambiguous`、多个草稿/候选归属冲突或不可逆点击结果不明时，才暂停副作用并在 5、15、30 秒后三轮独立重新读取同一页面及 API 状态。仍不明确时记录 `PREPARATION_STATE=ambiguous`、`AUTO_RECOVERY_ATTEMPTS=3`、具体 `AUTO_RECOVERY_ACTIONS`、`AUTO_RECOVERY_RESULT=unrepairable` 和 `FEISHU_FAULT_STAGE=utm-23-partial-preparation`，进入共享合同的最后故障卡。`manual_continue` 或 `retry_skill` 都重新执行本步骤状态账本；卡片反馈只用于故障恢复，不是确认、授权或第二次人工触发。
12. 根据最新画面只走一个分支：
    - `Build` 区域内蓝色 `Add Build` 清晰可见：记录 `ADD_BUILD_FIRST_CHECK=visible`、`REBUILD=no`、`DUPLICATE_UPLOAD=forbidden`、`ADD_BUILD_VISIBILITY_POLL=not_needed` 和 `FEISHU_FAULT_CARD=not_needed`，继续第 14 步。
    - 页面仍加载、Build 区域未稳定或暂时找不到 `Add Build`：不得把“暂不可见”解释成上传失败。进入第 13 步的有界只读可见性恢复。
13. `utm-22` 已经提供 `BUILD_UPLOAD_FINAL_STATE=COMPLETE` 与 `BUILD_PROCESSING_STATE=VALID`，因此本技能严禁通过再次上传探测页面。保持同一 App/版本页，执行以下恢复：
    1. 在 15、30、60、120 秒四个等待点分别读取最新页面；每轮重新核对 URL 中数字 App ID、应用名、版本、构建号、登录状态、加载/错误提示和 Build 区域。
    2. 每轮同时只读查询 App Store Connect API 中同一版本/构建号；只能确认既有 Build 的处理/可用状态，不创建新的上传记录、不重新封装、不重新 Archive。
    3. 页面明确显示唯一 `Add Build` 时记录 `ADD_BUILD_VISIBILITY_POLL=visible` 并继续第 14 步。
    4. 四轮结束仍无按钮，但 API 仍证明同一 Build 为 VALID 时，记录 `ADD_BUILD_VISIBILITY_POLL=exhausted`、`DUPLICATE_UPLOAD=forbidden`、`AUTO_RECOVERY_ATTEMPTS=4`、`AUTO_RECOVERY_ACTIONS=wait,reload-readonly,api-build-query,reverify`、`AUTO_RECOVERY_RESULT=exhausted`，再进入共享合同的最后故障卡。卡片继续决定只能重新执行本段只读检查，任何决定都不得上传、重建、重新 Archive 或改用其他 IPA。
    5. 若 API 查询显示 Build 已失效或归属冲突，记录权威非敏感错误并以 `AUTO_RECOVERY_RESULT=unrepairable` 进入最后故障卡；不得在本技能修复上传。

14. `Build` 区域内蓝色 `Add Build` 必须在最新画面中清晰可见。点击前在 preparation ledger 的 `build_attached` 项生成稳定 `ADD_BUILD_ATTEMPT_ID`，写入精确 App/版本/构建号、按钮前截图 hash 和 `state=prepared`；独立回读后才更新为 `opening_dialog` 并只点击该 `Add Build` 一次。等待至少 3 秒并重新读取画面，弹窗出现后更新为 `dialog_open`；已有 `opening_dialog/dialog_open/selection_done/done_result_unknown` 的 attempt 禁止另建 ID 或重新点击入口。不得点击顶部 `Add for Review` 或上传工具链接。

15. 标题为 `Add Build` 的弹窗、构建列表及 `Cancel`/`Done` 必须稳定显示。用 `utm-22` 已验证的版本和构建号核对列表；候选必须精确匹配且只出现一次。状态为 `Missing Compliance` 可以继续选择，但不得在本步骤处理合规问题。
16. 点击唯一匹配候选左侧单选框一次，等待至少 3 秒并重新读取画面。必须确认该候选已选中、版本/构建号未变化且 `Done` 已启用；不满足时先 `Cancel` 回到版本页，等待至少 3 秒重新验证当前 App/版本/构建号，再打开 `Add Build` 并按最新画面重选一次，记录 `GUI_RECOVERY=verified`。第二轮仍无法唯一选中才按 `utm-23-build-selection` 记录恢复穷尽并发送最后故障卡。
17. 候选验证后先把同一 `ADD_BUILD_ATTEMPT_ID` 更新为 `selection_done`；点击 `Done` 前再原子更新为 `clicking_done`，只点击一次已启用的 `Done`，随即记录 `done_result_unknown`。等待至少 3 秒并重新读取页面。只有弹窗已关闭、`Build` 区域显示刚才匹配的构建号和版本、状态为 `Missing Compliance`、右侧 `Manage` 可见且无错误，才更新为 `verified` 并记录 `BUILD_ATTACHED=verified`。结果不明只读查询页面/API 和同一 attempt，禁止再点 `Done`。
18. 只点击该 Build 行中 `Missing Compliance` 右侧的 `Manage` 一次，等待至少 3 秒并重新读取画面。必须确认弹窗标题为 `App Encryption Documentation`，问题为 `What type of encryption algorithms does your app implement?`，并且四个算法选项全部可见。
19. 只点击精确文本 `None of the algorithms mentioned above` 左侧的单选框一次，等待至少 3 秒并重新读取画面。必须确认只有该项被选中，其他三个算法选项均未选，且弹窗内 `Save` 已启用。
20. 在同一份最新画面中再次确认：只有 `None of the algorithms mentioned above` 被选中，其他三项均未选，且弹窗内 `Save` 已启用。生成稳定 `COMPLIANCE_SAVE_ATTEMPT_ID` 并在 ledger 保存构建身份、四项选择状态、截图 hash 和 `prepared`；点击前更新为 `clicking`，只点击该弹窗内 `Save` 一次并更新为 `result_unknown`。等待至少 3 秒并重新读取页面；结果不明只读核对同一构建的 Missing Compliance 状态，禁止第二次保存。
21. 必须确认 `App Encryption Documentation` 弹窗已关闭，Build 行仍为刚才匹配的构建号和版本，`Missing Compliance` 与其右侧 `Manage` 已消失，并且没有错误提示。
22. 保存合规答案后，聚焦应用版本页主内容的非控件空白处，每次只向下移动一页；每次移动后等待至少 3 秒并重新读取最新画面。持续到 `Game Center` 标签及其左侧复选框同时清晰可见，并确认仍是同一应用、同一版本页面。不得点击 `Game Center` 标签或复选框。
23. 在同一份最新画面中确认 `Game Center` 左侧复选框状态；蓝色说明提示不表示需要勾选。未勾选即记录通过。若明确已勾选，这是可逆误点：先再次核对当前 App/版本和复选框标签，点击一次取消，等待至少 3 秒并用最新截图确认变为空，记录 `GUI_RECOVERY=verified`；状态不明确时先滚离再返回该精确区域并独立重读三轮。只有三轮仍无法确认或点击后状态不唯一，才按 `utm-23-game-center-state` 记录恢复穷尽并进入最后故障卡。
24. 完成 `Game Center` 未勾选确认后，重新定位页面右上角的页面级 `Save`；若当前不可见，只能聚焦非控件空白处每次向上移动一页，并在每次移动后等待至少 3 秒重新读取。确认页面级 `Save` 可见且已启用后，生成稳定 `VERSION_PAGE_SAVE_ATTEMPT_ID`，保存 App/版本/构建、Build/Compliance/Game Center 当前证据和 `prepared`；点击前更新为 `clicking`，只点击一次并更新为 `result_unknown`。等待至少 3 秒并重新读取页面。必须确认该按钮变为带勾的灰色已保存状态、构建号和版本未变化且没有错误提示，才把 attempt 更新为 `verified` 并记录 `VERSION_PAGE=saved`；结果不明只读恢复，禁止重复 Save。
25. 进入同一应用的 `Distribution` → `In-App Purchases`，等待至少 3 秒并重读。先检查实时状态，只走一个分支：
    - 已有且只有一个 `Draft Submissions (1)`，其中 14 项内购均为 `Ready for Review`：不得重新组稿，记录 `IAP_BATCH_ACTION=skipped_existing`，直接进入第 28 步只读展开、核对并保存 `02-iap-drafts.png`。
    - 页面显示 `Drafts (14)` 且尚无完整 14 项审核草稿：记录 `IAP_BATCH_ACTION=required`，继续第 26 步。
    - 数量不是 14、出现多个审核草稿、混有不属于当前应用的项目或状态无法确认：暂停后续点击，先按 `utm-23-iap-draft-state` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
26. 新组稿时必须先点击 `See More`，等待至少 3 秒并重读，直到 14 个 draft consumable 全部可见；不得先点击 `Edit`。把 14 个唯一产品 ID/名称/状态的非敏感清单 hash 和唯一现有 Draft Submission 身份写入新的稳定 `IAP_BATCH_ATTEMPT_ID`，状态为 `prepared`。确认可见项目正好为当前应用的 14 项后才点击 `Edit`，等待至少 3 秒并重读。选择全部 14 项，必须看到 `Selected (14)`，将 attempt 更新为 `selected_14`；点击前更新为 `clicking_add_for_review`，只点击一次批量 `Add for Review` 并立即更新为 `result_unknown`。已有该状态时只读恢复，禁止再次批量点击。
27. 等待至少 3 秒并读取批量结果，不预设是否失败，也不写死失败项目名称或数量：
    - 没有失败：确认 14 项全部进入同一个既有审核草稿，把 batch attempt 更新为 `verified_14`。
    - 出现一个或多个失败项：逐字记录弹窗实际列出的全部失败产品 ID/名称，保留已经成功加入的现有草稿并把 batch attempt 更新为 `partial_classified`。关闭提示后，每个失败项先生成绑定产品 ID、同一草稿 ID 和批量 attempt 的稳定 `IAP_ITEM_ATTEMPT_ID`；打开项目详情页后只选择页面显示的同一个既有 `Draft Submission (当前已成功数量)`。点击前更新为 `clicking`，只点击一次 `Add for Review` 并更新为 `result_unknown`；等待至少 3 秒并由列表/草稿两侧确认该项变为 `Ready for Review` 后更新为 `verified`，再处理下一项。任一 item attempt 结果不明只读恢复，禁止重复点击或创建第二个 ID。
    - **所有位置都禁止选择 `Create New Submission`**。若某个失败项只有 `Create New Submission`、没有唯一既有草稿可选，暂停后续点击，先按 `utm-23-iap-draft-missing` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；不得为了继续而新建草稿。
28. 返回 `In-App Purchases` 列表并重新读取；回到列表顶部，若显示 `See More`，只点击一次并等待至少 3 秒重读。必须同时满足：页面显示 `Drafts (14)`、14 项全部可见且状态均为 `Ready for Review`、`Draft Submissions (1)` 只有一个、该草稿的 `In-App Purchases` 数量为 14。执行 `await saveReviewScreenshot("02-iap-drafts.png")`；文件检查通过后记录 `REVIEW_SCREENSHOT_02=verified`、`IAP_READY_FOR_REVIEW=14`、`DRAFT_SUBMISSIONS=1` 和 `CREATE_NEW_SUBMISSION=not_clicked`。截图失败或文件不合格时先按 `utm-23-screenshot-02` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定，不进入第 29 步。
29. 返回同一应用的当前 App Version 页面，确认应用名、数字 App ID、版本和构建号仍匹配。点击页面级 `Add for Review` 前生成绑定 App ID/版本/构建号/唯一草稿 ID 的稳定 `APP_VERSION_LINK_ATTEMPT_ID`，状态为 `prepared`；打开菜单后只选择已有 `Draft Submission (14)`，选择前更新为 `clicking`，点击一次后更新为 `result_unknown`。**不得选择 `Create New Submission`**。等待至少 3 秒并重读，只有同一草稿同时包含当前 App Version 与 `In-App Purchases (14)`，且左侧版本状态显示 `<版本号> Ready for Review`，才把 attempt 更新为 `verified` 并记录 `APP_VERSION_DRAFT_LINK=verified`；结果不明禁止再次选择。
30. 在左侧 `<版本号> Ready for Review` 仍清晰可见且版本号与当前任务一致时，点击 `General` 下的 `App Information` 一次。等待至少 3 秒并确认主标题为 `App Information`、仍是同一应用且页面稳定；回到页面顶部，只有左侧版本 `Ready for Review`、Name、Bundle ID 和 Category 同时可见时，执行 `await saveReviewScreenshot("03-app-information.png")`。文件检查通过后记录 `REVIEW_SCREENSHOT_03=verified`；失败时先按 `utm-23-screenshot-03` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。随后聚焦非控件空白处，每次只向下移动一页；每次移动后等待至少 3 秒并读取最新画面，直到分别定位 `App Store Regulations & Permits` 和 `App Store Server Notifications`。
31. 检查 `App Store Regulations & Permits`：
    - 默认说明文字以及 `Get Started`、`Add`、`Declare Regulated Medical Device` 只是未配置入口，出现这些入口即按对应项目为空处理，禁止点击它们。
    - 若显示实际记录，先保存删除前证据快照：最新页面截图、应用/App ID、区域名、记录类型、可见值的 mode-600 临时副本及 SHA-256；禁止把正文写入卡片或日志。只有这些信息唯一匹配当前应用，才打开精确记录。
    - `Edit`/`Manage` 后必须重新核对父区域和同一可见值。点击 `Remove`/`Delete` 前，删除确认弹窗必须逐项显示同一应用、同一区域、同一记录摘要和唯一删除按钮；任何一项缺失都 `Cancel`，回到锚点重新定位，不能猜。
    - 在打开删除确认前先生成绑定 App ID、区域、记录摘要 hash 和 before hash 的稳定 `APP_INFO_DELETE_ATTEMPT_ID`，状态为 `prepared`。确认按钮点击前更新为 `clicking`，只执行一次并更新为 `result_unknown`；结果不明时只读检查原记录是否仍存在：已消失表示成功并更新为 `verified_absent`；仍存在时必须结合页面事件/attempt 证明点击未生效，才可在同一 ID 下恢复一次；无法判断则不得第二次删除并进入最后故障卡。
    - 若存在已配置信息却没有清晰可用的移除动作，完成三轮独立重新定位/只读复核后以 `AUTO_RECOVERY_RESULT=unrepairable` 进入最后故障卡；不猜测、不覆盖其他合规状态。最终记录 `APP_STORE_REGULATIONS_PERMITS=empty`。
32. 检查 `App Store Server Notifications`：`Production Server URL` 与 `Sandbox Server URL` 都必须只显示 `Set Up URL`，这才表示为空；禁止点击 `Set Up URL`。若任一位置显示实际 URL：
    - 先把 Production/Sandbox 的当前值、应用/App ID、页面 URL、最新截图和 SHA-256 保存为权限 `600` 的删除前证据快照；这是可逆字段的 before。
    - 只打开该行明确编辑入口，重新核对编辑框值与 before 一致；只清空目标 URL。若误清邻近行，立即 `Cancel`，回到最新页面重新执行。
    - 每个实际 URL 行在清空前生成绑定 App ID、Production/Sandbox 行名和 before hash 的稳定 `SERVER_URL_CLEAR_ATTEMPT_ID`。弹窗内 `Save`/`Done` 点击前更新为 `clicking`，只点击一次并更新为 `result_unknown`；结果不明只读检查两行。若目标行未清空且 attempt/页面共同证明保存未执行，可在同一 ID 下恢复一次；若错误行变化，用 before 自动恢复错误行并回读后再处理目标行。
    - 等待至少 3 秒，直到 Production 与 Sandbox 都恢复为 `Set Up URL`。`App-Specific Shared Secret` 的 `Manage` 不属于本次清理范围，禁止点击。完成所有行级清理后，只有 App Information 页面级 `Save` 已启用时才点击一次并确认变为灰色已保存状态；没有页面级变化则不点击。

    重新逐页核对两个区域，删除安全临时文件并记录 `APP_STORE_SERVER_NOTIFICATIONS=empty`，再点击左侧 `<版本号> Ready for Review` 返回版本页，且版本号必须与当前任务实时值一致。重新核对当前 run 的 `run_id` 和原 `chat_id` 未变化、同一 `vm_name` 的 VM 仍为 `started`、guest Edge 仍为既有进程、App Store Connect 会话和标签页仍可复用、应用名/数字 App ID/版本和构建号仍匹配，并打开唯一 `Draft Submissions (1)` 确认其中仍同时包含当前 App Version 与 `In-App Purchases (14)`。同时要求当前 run 目录中的 `02-iap-drafts.png`、`03-app-information.png` 仍为权限 `600`、非空、可读 PNG，且本次记录的 SHA-256 未变化。

    最终必须丢弃“按钮点过”这一推断，使用新截图/API/文件进程重新构建当前状态：Build 已附加、Compliance 已清、Game Center 未选、版本已保存、唯一草稿、14 项、App Version 已关联、两个 App Information 区域为空、两张 PNG 合格、Submit 未点击。把 11 个有序项全部原子更新为 `verified`，写入各自当前证据 hash 和 `final_verified_at`，再由第二个进程回读整个 ledger 和 mode 600；只有当前权威状态与 ledger 完全一致才记录 `PREPARATION_STATE=complete`、`FINAL_STATE_LEDGER=verified`、`SUBMIT_FOR_REVIEW=not_clicked` 和 `UTM_23=verified`。不得以 attempt 的 `clicked/result_unknown` 代替最终状态，不得发送提审确认、等待提审决定或点击最终按钮。保留当前 VM、guest Edge 进程、App Store Connect 会话和标签页，立即继续 `utm-24`。

## 完成标准

```text
UTM_22=verified
VM_TARGET=verified
GUEST_EDGE_PROCESS=existing
BROWSER_SESSION_RECHECKS=2
BROWSER_PROCESS_GUARD=verified
APP_STORE_CONNECT=verified
APP_STORE_CONNECT_SESSION=verified
APP_STORE_CONNECT_TAB=reused|opened
APP_NAME=matched
APP_DETAIL=verified
REBUILD=no
BUILD_ATTACHED=verified
EXPORT_COMPLIANCE_STATUS=cleared
GAME_CENTER_CHECKBOX=unchecked
VERSION_PAGE=saved
PREPARATION_LEDGER_MODE=600
PREPARATION_STATE=complete
IAP_READY_FOR_REVIEW=14
DRAFT_SUBMISSIONS=1
CREATE_NEW_SUBMISSION=not_clicked
APP_VERSION_DRAFT_LINK=verified
APP_VERSION_STATUS=Ready for Review
APP_INFORMATION=verified
APP_STORE_REGULATIONS_PERMITS=empty
APP_STORE_SERVER_NOTIFICATIONS=empty
APP_INFORMATION_CLEANUP=not_needed|saved
REVIEW_SCREENSHOT_02=verified
REVIEW_SCREENSHOT_03=verified
RUN_ID=verified
ORIGINAL_CHAT_ID=verified
VM_NAME=verified
VM_STATE=started
APP_ID=verified
APP_VERSION_BUILD=verified
DRAFT_APP_VERSION=verified
DRAFT_IAP_COUNT=14
APP_STORE_CONNECT_TAB=preserved
SUBMIT_FOR_REVIEW=not_clicked
FINAL_STATE_LEDGER=verified
UTM_23=verified
```

若本轮实际执行了对应副作用，还必须在 ledger 中存在并验证相应稳定 ID：`ADD_BUILD_ATTEMPT_ID`、`COMPLIANCE_SAVE_ATTEMPT_ID`、`VERSION_PAGE_SAVE_ATTEMPT_ID`、`IAP_BATCH_ATTEMPT_ID`（以及每个失败项的 `IAP_ITEM_ATTEMPT_ID`）、`APP_VERSION_LINK_ATTEMPT_ID`、`APP_INFO_DELETE_ATTEMPT_ID`、`SERVER_URL_CLEAR_ATTEMPT_ID`；进入时已处于最终状态的项目记录 `not_needed_existing_verified`，不能伪造点击标记。

成功后必须保留当前页面和进程，立即继续 `utm-24`；不得等待用户确认。阻断、失败或未完成状态不得交接；`utm-23` 不拥有确认或最终提交。

部分准备或状态不明确时先使用有序账本、页面/API 三轮只读分类和可逆锚点恢复。只有恢复穷尽或不可逆结果仍不明确、确实进入最后故障卡等待时，等待状态至少记录：

```text
PREPARATION_STATE=partial|ambiguous
FEISHU_FAULT_STAGE=utm-23-partial-preparation
FAULT_NOTIFY_EXIT=0
FAULT_NOTIFY_RUN_ID=verified
FAULT_NOTIFY_RUNTIME=verified
FEISHU_FAULT_CARD=sent
FEISHU_FAULT_DECISION=waiting|stop|manual_continue|retry_skill
UTM_23=blocked
```

## 阻断条件

- `utm-22` 未完成，或 VM、`vm_name`、guest 画面不匹配。
- guest Edge 不存在、不可见、已退出，或需要启动/重启/切换浏览器进程。
- 没有已有 App Store Connect 页面时，宿主剪贴板不可用、`pbpaste` 不一致、目标地址栏未确认，或 `Paste and Go` 未明确高亮。
- 页面不属于 `appstoreconnect.apple.com`，或出现登录、2FA、CAPTCHA、账号锁定、网络/证书错误、未知安全挑战。
- 顶部全局 `Apps` 不唯一、不明确、点击后未进入 `/apps`，或 Apps 列表未稳定显示。
- 当前流程应用名不明确、列表中没有精确匹配、出现多个精确匹配，或点击后 URL/页头未匹配同一应用。
- 页面未稳定、仍在加载、出现网络错误，或未能确认当前 App/版本页时先按 `utm-23-page-state` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定；这些状态不得误判为 `ADD_BUILD_FIRST_CHECK=missing`。
- `Add Build` 首次不可见时必须进入第 13 步四轮有界只读恢复；不得上传、重建或改选文件。
- 有界只读恢复后仍找不到 `Add Build`：按恢复证据进入最后故障卡；继续决定只重查同一页面/API，严禁创建任何新上传。
- 点击后未打开 `Add Build` 弹窗、构建列表不明确，或弹窗显示错误。
- 没有与 `utm-22` 版本/构建号精确匹配的候选、出现多个匹配、选择后 `Done` 未启用，或点击后 Build 区域未显示同一构建。
- Build 状态不是 `Missing Compliance`、`Manage` 不明确、合规弹窗标题/问题不匹配、目标选项文字不完全一致、其他选项已选，或弹窗内 `Save` 未启用。
- 点击弹窗内 `Save` 后弹窗未关闭、构建号/版本变化、`Missing Compliance`/`Manage` 仍可见，或出现错误提示。
- 无法在同一应用版本页定位 `Game Center` 标签及其左侧复选框，复选框已勾选或状态不明确，或需要点击复选框才能确认状态。
- 页面右上角 `Save` 不可见、未启用、点击后未变为带勾的灰色状态，或保存后构建号/版本变化。
- `In-App Purchases` 不是 14 项、`See More` 后仍不能完整显示 14 项、在 `See More` 前误进 `Edit`、`Selected (14)` 未出现，或批量结果无法确认。
- 出现一个或多个失败内购时，没有唯一既有 Draft Submission 可供逐项加入；任何页面只提供 `Create New Submission`，或已出现多个审核草稿。
- 14 项未全部变为 `Ready for Review`、草稿不是唯一一个、App Version 无法加入同一草稿，或左侧未显示与当前任务实时版本一致的 `<版本号> Ready for Review`。
- `App Information` 页面不匹配；两个目标区域无法完整定位；存在实际许可证、声明或 Server URL 却没有明确安全的移除动作；清理后无法确认未配置状态。
- 清理后页面保存失败，返回版本页后版本、构建、`Ready for Review` 或唯一草稿状态发生变化。
- 最终移交复核时，当前 run/原 `chat_id`、`vm_name`、started VM、既有 guest Edge、App Store Connect 会话或标签页、应用/App ID/版本/构建、唯一草稿或两个 App Information 空状态任一项不匹配。
- 页面状态不明确，或任何操作后未等待至少 3 秒并读取最新状态。

本节任一阻断条件出现时，“停止”只表示暂停新的点击、写入、上传或清理，不得静默结束执行器。必须保留现场，先按本技能矩阵完成状态账本、自动修复和独立复验；只有恢复穷尽或不可逆结果仍不明确时，才携带非敏感恢复证据进入文件开头唯一的最后故障卡。`manual_continue` 与 `retry_skill` 都重新从同一状态账本开始，不能绕过恢复或授权任何重复副作用。卡片投递结果不明时只恢复同一 pending/UUID，取得非空 `message_id` 后才开始等待；不得把通知故障转成人工对话，不得输入敏感值或尝试其他浏览器。

## 常见误判

- 已有 App Store Connect 标签页时不要新开重复页面；新标签页只是无已有页面时的后备路径。
- 登录页不算完成：必须看到稳定的已登录 App Store Connect 页面。
- 顶部 `Apps` 是全局导航；进入列表后只点击当前流程中精确且唯一匹配的应用名，不点击加号或近似名称。
- 第一次找不到 `Add Build` 只表示页面可见性未确认；恢复是有界等待和同一 Build API 查询，不是上传动作。
- `BUILD_UPLOAD_FINAL_STATE=COMPLETE` 和 `BUILD_PROCESSING_STATE=VALID` 是禁止重复上传的依据；四轮仍不可见时才向原 `chat_id` 发最后故障卡。
- “发送了飞书告警”不能只凭命令已运行判断；必须同时验证退出码、返回的当前 `run_id` 和对应 run 的 `pending_decision.last_notified_at` 更新。验证后由当前执行器等待三按钮决定并立即处理，不需要第二次人工触发。
- `Missing Compliance` 不等于构建不匹配；本技能只进入其 `Manage`，选择 `None of the algorithms mentioned above`，核对其他三项未选后点击弹窗内 `Save`。
- 弹窗内 `Save` 与页面右上角 `Save` 不是同一控件；必须先保存合规答案并验证提示清除，再点击页面右上角 `Save`。
- `Game Center` 行旁的蓝色说明是信息提示，不代表需要勾选；本技能只确认其左侧复选框未勾选，禁止点击或自动切换。
- 页面右上角 `Save` 必须在 `Game Center` 未勾选确认完成后才能点击。
- 内购列表必须先 `See More`、确认 14 项全部可见，再 `Edit`；顺序不可颠倒。
- 批量 `Add for Review` 可能零失败、一个失败或多个失败；只按实时失败列表逐项补入同一个既有草稿，不写死名称、数量或草稿当前项目数。
- `Create New Submission` 在内购详情和 App Version 页面都禁止选择；没有唯一既有草稿时先按 `utm-23-iap-draft-missing` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
- `Get Started`、`Add`、`Declare Regulated Medical Device` 和 `Set Up URL` 表示尚未配置，不是需要清除的内容；`App-Specific Shared Secret` 的 `Manage` 不属于本次范围。
- `utm-23` 到两个 App Information 区域为空且唯一草稿复核完成为止；确认与最终提交属于 `utm-24`。移交时不得关闭页面、退出 Edge、切换 VM 或点击 `Submit for Review`。
