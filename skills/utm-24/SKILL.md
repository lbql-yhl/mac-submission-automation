---
name: utm-24
description: Use when utm-23 has just finished and the same guest Edge remains on the verified Ready for Review state.
---

# UTM-24：最终取证、确认并提交审核

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
  --stage 'utm-24:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-24' \
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
| 截图/标签/下拉误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图；关闭仅本轮错误新标签或 `Back` 到对应锚点，重新采集允许的 01/04，记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立取证后仍不能唯一确认才发卡 |
| 系统自检授权 | 五图哈希、15 项、版本/构建/14 IAP 全部通过后调用 `record-auto-review-approval`，记录 `AUTOMATIC_REVIEW_APPROVAL=verified` 和 `AUTOMATIC_REVIEW_SUBMIT=enabled`；不发提审交互卡 | 任一证据缺失才进入恢复/最后故障卡 |
| Submit 结果不明 | 自动授权后只点击一次；只读等待 5/10/20/40 秒检查 Waiting/15 Items，不再次点击 | 仍 ambiguous 才发卡 |
| 加急 Send 结果不明 | pristine form 才单击一次；只读检查精确成功文案 | 仍 ambiguous 才发卡，禁止第二次 Send |

## 定位

`utm-24` 紧接 `utm-23` 立即执行。入口已有 `UTM_23=verified`，因此直接继承 `utm-23` 刚刚确认的当前 `run_id`、原 `chat_id`、应用名、`vm_name`、版本、构建号和仍然打开的 Ready for Review 页面。

无需重新检查 VM、Edge、Build、Game Center、审核草稿或 App Information，也不得重新组稿、重新清理或改变已准备状态。`utm-11` 已保存 `05-small-business.png`，`utm-23` 已保存 `02-iap-drafts.png`、`03-app-information.png`。本技能只采集 `01-media-manager.png` 和 `04-privacy-agreement.png`，随后校验当前 run 的全部五张图与 15 项范围，由运行时写入系统自检授权并立即执行一次提交。App Store Connect 明确成功后，本技能继续在同一 guest Edge 完成加急审核表单，不发送成功通知；原 App Store 成功标签页必须始终保留，只能在同一 guest Edge 进程中新开标签页。

Notion 只通过项目 `scripts/notion_api.py` 读取；不得用宿主 Chrome、Notion 插件、Playwright、CUA、坐标或浏览器剪贴板读取 Notion。`read-field --copy` 只把 API 返回值放入已验证的宿主剪贴板，供同一 guest Edge 打开隐私协议网站。

每次 GUI 操作后等待至少 3 秒并重新读取最新画面，确认目标控件、当前高亮和操作结果后才能继续。正常主线不发送需要回复的卡片；成功通知由 `utm-25` 负责。只有共享合同规定的最后故障出口才向当前 run 的原 `chat_id` 发送三按钮故障卡，所有卡片都严禁发送到 `AI-Infra业务团队`。

## 操作步骤

1. 确认已有 `UTM_23=verified`、`REVIEW_SCREENSHOT_02=verified`、`REVIEW_SCREENSHOT_03=verified` 和 `REVIEW_SCREENSHOT_05=verified`，且从 `utm-23` 到当前步骤没有任务中断或现场切换。直接继承当前 run、应用、VM、版本和构建号，不得改用最新 run、旧 run、记忆或对话中的值。只读确认三个继承文件都位于当前 run 目录、权限 `600`、非空、可读为 PNG，且 SHA-256 与所属技能记录一致。任一不合格时记录 `SCREENSHOT_RECOVERY=handoff_to_owner`：`05` 只交回 `utm-11`，`02/03` 只交回 `utm-23`，由所属技能在同一 run/VM/会话的精确页面恢复并重做其完成检查，然后返回本步骤；`utm-24` 自己绝不采集这三张图。确认原 Ready for Review 标签页仍在同一 guest Edge 中并保留该标签页。

2. 复用当前 Computer Use 的同一 `node_repl`/`sky` GUI 驱动会话准备截图保存函数；该驱动器不是本项目流程中的额外技能。`run_id` 必须先匹配 `^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$`：

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
   var allowedReviewNames = new Set(["01-media-manager.png", "04-privacy-agreement.png"]);
   globalThis.saveReviewScreenshot = async function (name) {
     if (!allowedReviewNames.has(name)) throw new Error("screenshot name not owned by utm-24");
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

3. 在同一 guest Edge 进程中只采集 `01-media-manager.png` 和 `04-privacy-agreement.png`，不得重新采集 `02`、`03` 或 `05`：

   1. 保留原 Ready for Review 标签页，在新标签页调用 `OP-BROWSER-URL-NO-SCHEME`，执行 `printf '%s' 'appstoreconnect.apple.com/apps' | python3 scripts/shared_operations.py browser-url --allow-bare` 后只用高亮 `Paste and Go` 打开 App Store Connect。确认已登录后按 `Apps` -> 当前应用 -> 当前版本进入版本页；必须显示精确的 `iOS App <版本号> Ready for Review`。进入 `View All Sizes in Media Manager` -> `6.9" Display`，只有当前应用名、完整缩略图和 `N of 10 Screenshots` 同时可见且无加载/错误时执行 `await saveReviewScreenshot("01-media-manager.png")`。用宿主只读检查确认当前-run路径、权限 `600`、非空、PNG 可读并记录 SHA-256 和 `REVIEW_SCREENSHOT_01=verified`。

   2. 在宿主项目根目录运行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，再运行 `python3 scripts/notion_api.py read-field --title '<应用名>-<vm_name>' --heading '应用信息' --label '隐私协议: ' --copy`。页面、heading、code block 和标签必须唯一且值非空。立即调用 `OP-BROWSER-URL-NO-SCHEME`，执行 `pbpaste | python3 scripts/shared_operations.py browser-url`；统一执行器只删除最前面的一个 `https://`/`http://` 并逐字节保留 `//` 后全部内容。只有 `BROWSER_URL_CLIPBOARD=verified` 才在同一 guest Edge 新标签页通过蓝色高亮的 `Paste and Go` 打开；粘贴后立即清空剪贴板和 URL 变量，记录 `PRIVACY_CLIPBOARD=cleared`。标题必须包含 `<应用名> Privacy Agreement` 并显示 `Effective Date`。随后执行 `await saveReviewScreenshot("04-privacy-agreement.png")`，验证当前-run路径、权限 `600`、非空、PNG 可读并记录 SHA-256 和 `REVIEW_SCREENSHOT_04=verified`。

4. 立即切回原 Ready for Review 标签页，不关闭或重载。只读验证五张固定 PNG 全部属于当前 `run_id`、权限 `600`、非空、PNG 魔数/解码有效，且当前 SHA-256 与所属技能记录完全一致。`01/04` 缺失可由本技能回到自己的精确页面恢复；`02/03/05` 缺失或损坏必须记录 `SCREENSHOT_RECOVERY=handoff_to_owner` 并按第 1 步交回所属技能，恢复结束再返回本步骤，不能由本技能越权拍摄。顺序/哈希/跨 run 问题重新读取当前 run 元数据三轮；恢复仍失败才记录 `REVIEW_SCREENSHOTS=blocked` 并进入最后故障卡。全部通过后记录 `REVIEW_SCREENSHOTS=verified_5`。

5. 在原 Ready for Review 标签页执行最终自检：当前 run、原 `chat_id`、应用名、`vm_name`、版本、构建号均与 `utm-23` 移交值一致；页面仍显示当前版本 `Ready for Review`；打开右下 `Draft Submissions (1)` 后，抽屉唯一显示 `Draft Submission`、`Items Ready to Submit (15)`、当前 iOS App 和 `In-App Purchases (14)`。全部匹配后记录 `REVIEW_SUBMIT_PRECHECK=verified`，并且证据字符串必须同时包含 `REVIEW_SCREENSHOTS=verified_5` 和 `ITEMS_READY=15`。

6. 五张 PNG 按 `01` 至 `05` 固定顺序交给本机运行时做系统自检授权；不上传图片、不发送需要回复的卡片：

   ```bash
   python3 services/feishu_bot.py record-auto-review-approval \
     --run-id '<run_id>' \
     --chat-id '<original-chat-id>' \
     --app-version '<版本号>' \
     --build-number '<构建号>' \
     --iap-count 14 \
     --evidence 'REVIEW_SCREENSHOTS=verified_5;ITEMS_READY=15' \
     --screenshot '<01-media-manager.png>' \
     --screenshot '<02-iap-drafts.png>' \
     --screenshot '<03-app-information.png>' \
     --screenshot '<04-privacy-agreement.png>' \
     --screenshot '<05-small-business.png>'
   ```

   命令必须在同一次 runtime mutation 写入独立顶层 `review_submission_approval`：`kind=review_submit`、`status=approved`、`decision=submit_review`、稳定 `auto-<uuid>`、版本、构建、`iap_count=14`、完整 evidence、五个当前 PNG 的 SHA-256、非空时间、`operator_id=automation:self-check` 和 `source=automatic_self_check`。幂等规则固定如下：
   - 已有 automatic snapshot 与本次版本/构建/evidence/五个顺序哈希完全相同时，必须原样返回现有 `decision_id`/`answered_at`，不追加事件、不生成新 UUID；
   - 证据发生变化且尚无 `review_submit_attempt` 时，才允许写一个新 automatic snapshot；
   - 已存在任何 submit attempt 后证据变化必须拒绝，不能换授权掩盖已开始的提交；
   - 已有 waiting 交互决定、显式 rejected 快照或非 automatic 的人工批准时都不得自动覆盖。

   命令退出后重新读取同一精确 run，逐项核对快照、五个哈希和当前文件一致，保存其 `decision_id` 并记录 `APPROVAL_DECISION_ID=bound`、`AUTOMATIC_REVIEW_APPROVAL=verified`、`AUTOMATIC_REVIEW_SUBMIT=enabled`。正常运行没有等待节点。

7. 系统自检授权写入后，立即重新读取原 Ready for Review 标签页。若页面、版本、构建、草稿或 15 项范围发生任何变化，且尚无 submit attempt，回到第 4、5 步重新完成全部只读检查并让幂等命令按证据决定复用或更新授权；已有 attempt 时只读分类，不得改授权。页面未变化时才允许提交。

   在首次可能点击前生成稳定 `REVIEW_SUBMIT_ATTEMPT_ID`，并调用运行时把它以 `prepared` 状态绑定当前 approval decision：

   ```bash
   python3 services/feishu_bot.py record-review-submit-attempt \
     --run-id '<run_id>' --chat-id '<original-chat-id>' \
     --attempt-id '<stable-attempt-id>' \
     --decision-id '<APPROVAL_DECISION_ID>' \
     --app-version '<版本号>' --build-number '<构建号>' \
     --items-ready 15 --attempt-status prepared
   ```

   命令必须原子写入顶层 `review_submit_attempt`，且 run/decision/version/build/15 项身份完全一致；已有 attempt 只能复用相同 ID。`Submit for Review` 暂时为灰色时按 5/10/20/40 秒有界只读等待。按钮变蓝且所有身份仍一致时，先以同一命令把状态推进为 `clicking`，再只点击一次；点击动作返回后无论页面是否已变化，都先推进为 `result_unknown`。若出现标准确认弹窗，必须同时核对弹窗属于 App Store Connect、应用名/版本匹配、范围为当前 App Version 加 14 个 IAP、主按钮精确为提交且只有一个；确认前再次核对同一 attempt 仍是 `result_unknown`，只确认一次。页面响应慢或结果不明时禁止第二次点击。

8. 只接受页面明确显示 `15 Items Submitted` 或当前版本状态变为 `Waiting for Review`，并要求 App/版本/构建仍与 attempt 相同。随后以同一运行时命令依次将状态从 `result_unknown` 推进到 `verified`；不能跳级、回退或换 ID。记录 `SUBMIT_FOR_REVIEW=clicked_once` 和精确 `APP_REVIEW_STATUS=Waiting for Review|15 Items Submitted`；保留这个 App Store 成功标签页，不关闭、不重载、不在其中继续导航。此时记录 `REVIEW_SUCCESS_NOTIFICATION=not_sent`，本技能不得发送绿色成功通知。

9. App Store 提交 attempt 已为 `verified` 后，先生成稳定 `EXPEDITE_SUBMIT_ATTEMPT_ID`，在 `${PROJECT_ROOT}/runtime/utm-24-attempts/<run-id>/expedite.json` 以 mode 600 原子保存 run/原 chat、App ID/应用名、`REVIEW_SUBMIT_ATTEMPT_ID`、当前 review 成功状态、`state=prepared` 和时间；已有 ledger 必须身份完全一致并复用同一 ID。记录 `EXPEDITE_SUBMIT_ATTEMPT_ID=<stable-id>`。

   在同一 guest Edge 进程中新建一个标签页。操作前重新确认 UTM/Edge 目标窗口和地址栏；调用 `OP-BROWSER-URL-NO-SCHEME`，执行 `printf '%s' 'developer.apple.com/contact/app-store/?topic=expedite' | python3 scripts/shared_operations.py browser-url --allow-bare`。只有 `BROWSER_URL_CLIPBOARD=verified` 且原生菜单中的 `Paste and Go` 已蓝色高亮时才确认一次；粘贴后立即清空剪贴板。每次 GUI 操作后等待至少 3 秒并重新读取最新画面；不得启动、重启或切换 Edge 进程，也不得影响保留的 App Store 成功标签页。

10. 页面稳定后先做只读分类，不选择下拉项、不滚动点击 `Send`：

    - 若页面已经精确显示动态成功文案 `We’ll expedite review for <当前应用名>.`，必须同时核对本轮 expedite ledger 的 run/App/已验证 review attempt 身份，且 ledger 状态只能是 `prepared|clicking|result_unknown|verified`。全部一致才把同一 ledger 更新为 `verified_existing_success`，记录 `EXPEDITE_PAGE_CLASSIFICATION=existing_success`、`EXPEDITED_REVIEW_APP_NAME=verified`、`EXPEDITED_REVIEW_PLATFORM=iOS`、`EXPEDITED_REVIEW_SEND=skipped_existing_success` 和 `EXPEDITED_REVIEW_RESULT=verified`；没有当前 run ledger 的旧成功页不能快进，按 unknown 分类。
    - 只有页面完整显示加急审核表单、`App Information`、`App Name`、`Platform` 和 `Send`，没有成功文案、没有加载/错误/部分提交状态，且当前执行器能证明此前没有点击过 `Send`，才记录 `EXPEDITE_PAGE_CLASSIFICATION=pristine_form` 并继续。
    - 任一字段或页面结构残缺、状态不明、出现非当前应用的成功文案，或无法排除先前已经点击过 `Send`，统一记录 `EXPEDITE_PAGE_CLASSIFICATION=unknown_prior_send`，执行 `utm-24` 的同一 attempt 只读恢复矩阵；只有恢复穷尽仍不能判定时才进入最后三按钮故障卡，不得用故障决定猜测为 pristine form。

11. 仅在 `EXPEDITE_PAGE_CLASSIFICATION=pristine_form` 时滚动到 `App Information`。打开 `App Name` 下拉框，等待至少 3 秒并重新读取画面；必须在唯一候选中找到逐字符等于当前 run 应用名的选项，移动到该项并确认它已蓝色高亮后才选择一次。重新读取页面确认 `App Name` 回显精确应用名，记录 `EXPEDITED_REVIEW_APP_NAME=verified`。再打开 `Platform` 下拉框，以同样方式只选择唯一且蓝色高亮的 `iOS`，重新读取回显并记录 `EXPEDITED_REVIEW_PLATFORM=iOS`。零个、多个、未高亮或回显不一致时，每轮都先 `Escape` 回到表单锚点，安全重新定位并回读，完整执行三轮；三轮仍不唯一才进入最后故障卡，不点击 `Send`。

12. 再次逐项确认 `App Name` 等于当前 run 应用名、`Platform` 等于 `iOS`、页面仍为同一加急表单、`Send` 是唯一可用提交控件，并确认同一 ledger 尚为 `prepared`。全部通过后先把 ledger 原子更新为 `clicking`，只点击一次 `Send`，动作返回后立即更新为 `result_unknown` 并记录 `EXPEDITED_REVIEW_SEND=clicked_once`；等待至少 3 秒并重新读取最新画面。只有页面精确显示 `We’ll expedite review for <当前应用名>.` 且 App/ledger/review attempt 身份仍一致，才更新为 `verified` 并记录 `EXPEDITED_REVIEW_RESULT=verified`。发送后加载、错误、空白、文案不匹配或结果不明时只读检查同一 `EXPEDITE_SUBMIT_ATTEMPT_ID`，不得再次点击；恢复预算穷尽且仍不明确时才形成新的最后故障事件。`manual_continue` 和 `retry_skill` 也只能重新读取同一加急页面和 ledger 并核对精确成功文案，不得盲目再次点击 `Send`。

13. 确认 `APP_REVIEW_STATUS=Waiting for Review|15 Items Submitted`、`REVIEW_SUBMIT_ATTEMPT_STATUS=verified`、`EXPEDITED_REVIEW_APP_NAME=verified`、`EXPEDITED_REVIEW_PLATFORM=iOS`、`EXPEDITED_REVIEW_SEND=clicked_once|skipped_existing_success`、同一 expedite ledger 为 `verified|verified_existing_success`、`EXPEDITED_REVIEW_RESULT=verified`、`REVIEW_SUCCESS_NOTIFICATION=not_sent` 后记录 `API_CREDENTIALS_REGISTRATION=pending` 和 `UTM_24=verified`。保留同一 run、原 `chat_id`、VM、guest Edge 进程/登录会话、App Store 成功标签页和加急成功页，立即交接 `utm-25`；不等待用户确认。API 信息登记属于 `utm-25`，不得提前在本技能读取或写入。

## 完成标准

```text
UTM_23=verified
REVIEW_SCREENSHOT_01=verified
REVIEW_SCREENSHOT_02=verified
REVIEW_SCREENSHOT_03=verified
REVIEW_SCREENSHOT_04=verified
REVIEW_SCREENSHOT_05=verified
REVIEW_SCREENSHOTS=verified_5
SCREENSHOT_RECOVERY=not_needed|handoff_to_owner
PRIVACY_CLIPBOARD=cleared
REVIEW_SUBMIT_PRECHECK=verified
AUTOMATIC_REVIEW_APPROVAL=verified
AUTOMATIC_REVIEW_SUBMIT=enabled
REVIEW_SUBMISSION_SOURCE=automatic_self_check
APPROVAL_DECISION_ID=bound
REVIEW_SUBMIT_ATTEMPT_ID=<stable-id>
REVIEW_SUBMIT_ATTEMPT_STATUS=verified
SUBMIT_FOR_REVIEW=clicked_once
APP_REVIEW_STATUS=Waiting for Review|15 Items Submitted
EXPEDITE_SUBMIT_ATTEMPT_ID=<stable-id>
EXPEDITED_REVIEW_APP_NAME=verified
EXPEDITED_REVIEW_PLATFORM=iOS
EXPEDITED_REVIEW_SEND=clicked_once|skipped_existing_success
EXPEDITED_REVIEW_RESULT=verified
API_CREDENTIALS_REGISTRATION=pending
REVIEW_SUCCESS_NOTIFICATION=not_sent
UTM_24=verified
```

## 阻断条件

- 缺少前置完成标记，或 `utm-23` 与本技能之间发生任务中断、VM/浏览器/页面切换。
- 当前 `run_id` 不安全，截图无法取得/保存，或继承/新采集图片任一缺失、为空、不可读、权限/哈希/顺序/run 不一致。
- App Store Connect 应用、Ready for Review 版本、Media Manager、隐私协议页、最终 15 项提交范围或保留的提交成功状态任一无法唯一确认。
- Notion 字段缺失、重复、为空，链接字符被改动，剪贴板未核对，或隐私页标题/`Effective Date` 不匹配。
- 五图/15 项证据不完整、系统自检授权写入或回读失败、已有 waiting 决定/显式 rejected 快照、授权后现场变化，或提交后没有明确的 `15 Items Submitted` / `Waiting for Review`，都先按本技能矩阵自动恢复；恢复穷尽后进入最后故障卡，未授权时不得点击。
- 加急页不是精确成功态或 pristine form、无法证明此前未点击 `Send`、选项不唯一、回显不一致，或单次 `Send` 后未出现精确成功文案时，先按矩阵执行可逆导航恢复与同一 attempt 只读复验；恢复穷尽或发送结果仍不明确才进入最后故障卡。

点击提交前发生业务阻断时，不修改已验证草稿、不点击提交；先按矩阵恢复并重新生成系统自检授权。继承截图缺失时只回到所属技能为同一精确 run 恢复，再重新完成 `utm-23` 的最终移交核对；不得由 `utm-24` 越权补拍。点击提交后若结果不明，保留现场并按 5/10/20/40 秒只读核对实际状态，禁止触发第二次提交；仍不明才进入最后故障卡，任何故障回调也只能继续只读核对。加急页点击 `Send` 后同样禁止第二次点击。

## 常见误判

- `utm-11` 保存 `05`，`utm-23` 保存 `02/03`，`utm-24` 只保存 `01/04`；不得把五张图重新集中到本技能。
- 五张截图和最终 15 项范围自检通过后必须写入系统自检授权并自动提交一次，不等待任何回复。
- `record-auto-review-approval` 只写当前 run 的单次授权快照，不发送飞书消息。
- `manual_continue`/`retry_skill` 只用于异常故障恢复，不能替代提审确认或触发第二次提交。
- App Store 明确成功后仍要完成加急审核；`utm-24` 只记录 `REVIEW_SUCCESS_NOTIFICATION=not_sent`，绿色成功通知由 `utm-25` 发送。
- 加急页已存在精确成功文案时只校验并记录 `skipped_existing_success`；没有成功文案但先前 `Send` 是否点击不明时不能当作 pristine form。
- `Send` 只能在两个下拉框回显复核完成后点击一次；任何故障决定都不能授权第二次点击。

## 正常交接

仅当上述提交与加急标记全部成立时记录 `UTM_24=verified` 并立即交接 `utm-25`。只有用户在最后故障出口选择 `stop` 或故障卡等待超时，才保留现场并结束当前 run；`UTM_24=blocked` 只表示自动恢复已穷尽并进入三按钮故障卡等待，不得静默结束执行器。
