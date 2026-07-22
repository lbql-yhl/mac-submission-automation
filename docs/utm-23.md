# UTM-23：准备审核草稿并移交 UTM-24

对应技能：`utm-23`。接着 `utm-22`，只复用同一台 UTM guest 中既有 Microsoft Edge，并先按有序状态账本执行只读恢复分类。若现场已满足完整终态，只保存并验证当前 run 的 `02-iap-drafts.png`、`03-app-information.png` 后直接移交；部分准备从第一个未完成且可安全恢复的步骤自动续跑，状态不明确时先重读、回到最近验证锚点并复验。只有恢复穷尽或不可逆结果仍无法判定时才发送最后三按钮故障卡。完整路径完成构建附加、合规、14 项内购与 App Version 唯一草稿，并以 before/after 证据清理 App Information 两个目标。复核唯一草稿、两张当前-run截图和当前现场后，以 `SUBMIT_FOR_REVIEW=not_clicked`、`UTM_23=verified` 结束并立即移交 `utm-24`。

## Checklist

- [ ] `utm-22` 已验证 `BUILD_UPLOAD_FINAL_STATE=COMPLETE` 和 `BUILD_PROCESSING_STATE=VALID`。
- [ ] 正常入口直接继承当前 run 的原 `chat_id`、App ID、Bundle ID 和版本/构建号，不重新选择 run。`Add Build` 暂不可见时只读取 `utm-22` 的稳定 upload attempt、同一版本/构建的 Build Upload 与 Build 状态；不得读取密钥值，也不得用任何再次上传动作探测可见性。
- [ ] 当前 `run_id` 已通过安全目录名校验，截图保存函数只允许写入宿主 `runtime/review-screenshots/<run_id>`，不使用旧 run、guest Downloads 或对话附件。
- [ ] 当前 `vm_name`、started VM 和 guest 画面与前序流程一致。
- [ ] guest Edge 是既有进程；分别读取 UTM 窗口/前台应用归属与该精确 VM 内 Edge PID/启动参数，5 秒后再做第二次独立读取；匹配时记录 `BROWSER_SESSION_RECHECKS=2`，没有启动、重启或切换浏览器进程。
- [ ] 已先检查当前页面和标签栏；已有 App Store Connect 页面时已直接切回且未新开重复标签。
- [ ] 只有没有已有页面时，才新开标签并确认地址栏；调用 `OP-BROWSER-URL-NO-SCHEME`，执行 `printf '%s' 'appstoreconnect.apple.com' | python3 scripts/shared_operations.py browser-url --allow-bare`。只在 `BROWSER_URL_CLIPBOARD=verified` 后用蓝色高亮的 `Paste and Go` 打开网站，随后清空剪贴板。
- [ ] 页面属于 `appstoreconnect.apple.com`，已登录且稳定显示。
- [ ] 已点击页面最上方全局导航的 `Apps`，没有点击应用名或其他局部控件。
- [ ] 当前 URL 为 `appstoreconnect.apple.com/apps`，主标题和应用列表稳定显示。
- [ ] 当前流程应用名已重新确认，并在列表中精确且唯一匹配。
- [ ] 已点击匹配应用名；当前 URL 含 `/apps/<纯数字 App ID>/`，页头显示同一应用名。
- [ ] 在判定 `Add Build` 前已执行只读已准备恢复分支：只有当前 run/原 `chat_id`、同一 VM/既有 Edge、应用/版本/构建均无歧义时才检查。
- [ ] 若精确构建已附加、合规已清除、Game Center 未勾选、版本已保存、唯一草稿包含当前 App Version + 14 项内购、左侧 Ready for Review、两个 App Information 目标为空且未提交，已在只读检查经过的对应页面保存并验证 `02/03`，记录 `ALREADY_PREPARED_CHECK=verified` 后直接进入最终移交复核。
- [ ] 已准备恢复分支不得点击 `Add Build`、不得重新组织内购、不得重新添加 App Version、不得清理 App Information 或点击保存/提交。
- [ ] 判定现场前必须建立持久账本 `${PROJECT_ROOT}/runtime/utm-23-attempts/<run-id>/preparation.json`：父目录 mode 700，文件通过 mode-600 同目录临时文件、文件/目录 `fsync` 和原子替换写入，每次写后新进程回读身份与权限，记录 `PREPARATION_LEDGER_MODE=600`。若只是部分准备，按固定有序项保留已 `verified` 的当前证据，从第一个未完成项继续，不回退或重做前面的不可逆动作。
- [ ] 状态不明确时暂停新副作用，用最新页面、同一 Build API 状态、草稿范围和前后证据重读三轮；可逆误点回到最近验证锚点。仍无法唯一分类才记录恢复证据并进入最后故障卡。卡片反馈不是确认或授权，继续后仍从同一账本重新分类。
- [ ] 已聚焦主内容空白处，并逐页向下移动；每次移动后等待至少 3 秒并重读页面。
- [ ] 已完整逐页检查当前应用版本页并记录 `ADD_BUILD_FIRST_CHECK=visible|missing`；加载中、错误页或应用/版本不匹配未被误判为按钮缺失。
- [ ] 若首次找不到 `Add Build`，在 `utm-22 COMPLETE+VALID` 前提下按 15/30/60/120 秒有界只读刷新同一页面，并查询同一稳定 upload attempt、App ID、版本和构建号的 Build 可见性；每轮都确认没有切换应用、版本或浏览器。任何情况下都不得再次上传、Archive、构建或封装。
- [ ] 有界检查后出现唯一精确构建则自动继续；仍不可见时记录 `ADD_BUILD_VISIBILITY_POLL=exhausted`、最后 Build API 状态和页面证据，再以 `utm-23-add-build-missing` 发送最后故障卡。`manual_continue`/`retry_skill` 只能再次只读核对同一 Build，不得创建上传。
- [ ] 找到时，页面底部 `Build` 区域内蓝色 `Add Build` 已清晰可见。点击前在账本生成稳定 `ADD_BUILD_ATTEMPT_ID`，绑定 App/版本/构建与按钮前截图 hash，独立回读 `prepared`后再持久化 `opening_dialog`并只点击一次；后续状态不明只恢复同一 ID。
- [ ] `Add Build` 弹窗和构建列表稳定显示；候选版本/构建号与 `utm-22` 一致且只匹配一项。
- [ ] 唯一候选已勾选，`Done` 已启用并且只点击一次。
- [ ] 弹窗已关闭，Build 区域显示匹配构建号、版本和状态。
- [ ] Build 行状态为 `Missing Compliance`，已点击其右侧唯一 `Manage`。
- [ ] `App Encryption Documentation` 弹窗和四个算法选项已完整显示。
- [ ] 只选择了 `None of the algorithms mentioned above`，其他三项未选，弹窗内 `Save` 已启用。
- [ ] 核对无误后只点击一次弹窗内 `Save`，并等待至少 3 秒重新读取页面。
- [ ] 合规弹窗已关闭；同一构建号和版本仍在，`Missing Compliance` 与 `Manage` 已消失。
- [ ] 已逐页向下定位同一应用版本页的 `Game Center` 标签及其左侧复选框；每次移动后等待至少 3 秒并重读页面。
- [ ] `Game Center` 左侧复选框为空且未勾选。若意外已勾选且页面尚未保存，先确认该切换可逆、只取消一次并重新读取；保存结果不明时不得再次切换，以同一页面/版本状态只读恢复。
- [ ] 完成 `Game Center` 未勾选确认后，页面右上角 `Save` 已启用且只点击一次；等待至少 3 秒后显示带勾的灰色已保存状态。
- [ ] 构建号和版本未变化，没有错误提示，已进入同一应用的 `In-App Purchases`。
- [ ] 新组稿时先点击 `See More`，确认 14 项完整显示后，把 14 个唯一产品和现有草稿身份的非敏感 hash 写入稳定 `IAP_BATCH_ATTEMPT_ID`。经 `prepared -> selected_14 -> clicking_add_for_review -> result_unknown -> verified` 只点击一次批量 `Add for Review`；已出现完整 14 项既有草稿时没有重复组稿。
- [ ] 已选择全部 14 项并看到 `Selected (14)`，再点击批量 `Add for Review`。
- [ ] 批量操作零失败时直接复核；有一个或多个失败项时，已按弹窗实时列表逐个打开并加入同一个既有 Draft Submission，没有写死失败名称或数量。
- [ ] 内购详情及 App Version 页面均未选择 `Create New Submission`；页面没有唯一既有草稿时已暂停新的副作用，按草稿归属/范围矩阵重读三轮并尝试恢复同一 run 草稿，只有仍无法唯一归属时才记录证据进入最后故障卡。
- [ ] 14 项内购全部为 `Ready for Review`，`Draft Submissions (1)` 唯一且包含 `In-App Purchases (14)`。
- [ ] IAP 列表顶部显示 `Drafts (14)`，14 项全部可见且为 `Ready for Review`；已保存、校验 `02-iap-drafts.png` 并记录 `REVIEW_SCREENSHOT_02=verified`。
- [ ] App Version 页面级 `Add for Review` 点击前必须生成稳定 `APP_VERSION_LINK_ATTEMPT_ID`，绑定 App ID/版本/构建/唯一草稿 ID；只选择已有 `Draft Submission (14)` 一次，结果不明只读恢复。只有草稿同时显示当前 App Version + `In-App Purchases (14)` 且左侧为 `<版本号> Ready for Review` 才将 attempt 标记 `verified`。
- [ ] 已点击 `General` 下的 `App Information`；顶部同时显示同一应用、版本 Ready for Review、Name、Bundle ID 和 Category 后，保存、校验 `03-app-information.png` 并记录 `REVIEW_SCREENSHOT_03=verified`，再逐页定位两个清理区域。
- [ ] 清理前已保存两个区域的精确 before 证据；Regulations & Permits 仅保留默认说明及 `Get Started`/`Add`/`Declare Regulated Medical Device` 未配置入口。只有真实许可证、声明或记录存在且删除目标唯一时才移除一次；结果不明只读核对 before/after，禁止重复删除。
- [ ] Production/Sandbox Server URL 均只显示 `Set Up URL`；实际 URL 清空前后均有字段级证据，没有点击 `App-Specific Shared Secret` 的 `Manage`。误入编辑页先 `Cancel`/`Back` 回到 App Information 锚点并确认没有保存。
- [ ] 如发生清理，App Information 页面已保存并重读；返回与当前任务实时版本一致的 `<版本号> Ready for Review` 后，版本、构建和唯一草稿保持不变。
- [ ] 已重新核对当前 `run_id` 和原 `chat_id`、同一 `vm_name`、started VM、既有 guest Edge 进程、App Store Connect 会话/标签页、同一应用/数字 App ID/版本/构建号。
- [ ] 唯一 `Draft Submissions (1)` 仍同时包含当前 App Version 与 `In-App Purchases (14)`，两个 App Information 区域仍为空。
- [ ] 当前 run 的 `02-iap-drafts.png`、`03-app-information.png` 均为权限 `600`、非空、PNG 可读且 SHA-256 未变化；本技能没有保存 `01`、`04` 或 `05`。
- [ ] 最后不使用“曾点击过”作为成功证据：以新截图/API/文件进程独立重建当前 11 项有序状态，全部为 `verified` 后用第二个进程回读 ledger 及 mode 600，再记录 `FINAL_STATE_LEDGER=verified`、`SUBMIT_FOR_REVIEW=not_clicked`、`UTM_23=verified`；没有发送提审确认、等待决定或点击最终按钮。
- [ ] 已保留当前 VM、guest Edge 进程、App Store Connect 会话和标签页，并立即继续 `utm-24`。

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
TOP_APPS=clicked
APPS_PAGE=verified
APP_NAME=matched
APP_DETAIL=verified
BUILD_SECTION=located
ADD_BUILD_FIRST_CHECK=visible|missing
ADD_BUILD_VISIBILITY_POLL=not_needed|verified_visible
SECOND_UPLOAD=forbidden
REBUILD=no
FEISHU_FAULT_CARD=not_needed|sent
FEISHU_FAULT_DECISION=not_needed|manual_continue|retry_skill
ADD_BUILD_BUTTON=visible
ADD_BUILD=clicked
ADD_BUILD_DIALOG=open
BUILD_CANDIDATE=matched
BUILD_SELECTED=verified
ADD_BUILD_DONE=clicked
BUILD_ATTACHED=verified
MISSING_COMPLIANCE=visible
COMPLIANCE_MANAGE=clicked
ENCRYPTION_DIALOG=open
ENCRYPTION_NONE=selected
COMPLIANCE_SAVE_READY=verified
COMPLIANCE_SAVE=clicked
EXPORT_COMPLIANCE_STATUS=cleared
GAME_CENTER_SECTION=located
GAME_CENTER_CHECKBOX=unchecked
GAME_CENTER_ACTION=none
PAGE_SAVE_READY=verified
PAGE_SAVE=clicked
VERSION_PAGE=saved
PREPARATION_LEDGER_MODE=600
PREPARATION_STATE=untouched|complete
ALREADY_PREPARED_CHECK=not_present|verified
IAP_BATCH_ACTION=required|skipped_existing
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

本轮实际执行过的每个副作用还必须有对应稳定 attempt ID，至少包括 `ADD_BUILD_ATTEMPT_ID`、`IAP_BATCH_ATTEMPT_ID`、`APP_VERSION_LINK_ATTEMPT_ID`；进入时已处于终态的项记录 `not_needed_existing_verified`，不伪造点击标记。

自动恢复穷尽后仍无 `Add Build` 时使用最后故障状态：

```text
ADD_BUILD_FIRST_CHECK=missing
BUILD_UPLOAD_ATTEMPT=verified_same
ADD_BUILD_VISIBILITY_POLL=exhausted
SECOND_UPLOAD=forbidden
REBUILD=no
BUILD_UPLOAD_FINAL_STATE=COMPLETE
BUILD_PROCESSING_STATE=VALID
ADD_BUILD_RECHECK=missing
AUTO_RECOVERY_RESULT=exhausted
FAULT_NOTIFY_EXIT=0
FAULT_NOTIFY_RUN_ID=verified
FAULT_NOTIFY_RUNTIME=verified
FEISHU_FAULT_CARD=sent
FEISHU_FAULT_DECISION=waiting|stop|manual_continue|retry_skill
UTM_23=blocked
```

部分准备或状态不明确时的等待状态：

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

## 风险点

- guest Edge 不存在或已退出时，禁止为了完成本步骤而启动或重启浏览器。
- 已有 App Store Connect 标签页时禁止再打开重复页面。
- 登录/2FA 的已知恢复路径调用 `OP-APPLE-PHONE-OTP`；CAPTCHA、账号锁定或未知安全挑战经三轮独立只读复核后属于外部 `unrepairable`，才进入最后故障卡。
- 顶部 `Apps`、应用名、App ID、版本或页头不明确时，每轮都回到已验证导航锚点并安全重新定位，完整执行三轮且每轮独立回读；三轮仍不唯一才发最后故障卡。
- 页面加载、网络或证书瞬态错误按 5/10/20 秒只读等待，动作可证明未执行时才允许一次恢复导航；不得把这些状态当成 `Add Build` 缺失。
- 部分准备按状态账本自动续跑；只有无法确定哪个不可逆动作已发生时才发最后故障卡。`manual_continue`/`retry_skill` 重新只读分类，不重做已验证步骤。
- `Add Build` 不可见只允许有界页面/API查询；禁止任何再次上传、重新 Archive/构建、重新封装或改传其他 IPA。
- 故障卡命令只有在退出码为 0、返回当前 `run_id`，且匹配 run 的 `pending_decision.first_notified_at`、`last_notified_at`、`last_message_id` 更新后才算发送成功。未确认送达时保留同一 pending 决定并自动修复/重试同一 run/chat 的卡片服务，不开始 3600 秒用户回复计时、不谎报成功、不结束流程。回调后由当前执行器立即操作，不需要第二次人工触发；所有恢复路径继续禁止第二次上传。
- 点击后弹窗未打开、候选不明确或出现错误时先 `Escape`/`Cancel` 回到版本页锚点，证明未附加后才重新定位一次；结果不明时只读恢复。
- 构建候选不唯一、不匹配，`Done` 未启用，或完成后 Build 区域未显示同一构建时，重新读取弹窗/页面/API；仍不唯一才进入最后故障卡。
- `Manage`/合规弹窗/选项不匹配时回到 Build 锚点重新定位；保存后结果不明只读复验，不重复保存。
- `Game Center` 不可见或状态不明确时重新定位；可证明是未保存的误勾选才自动取消一次，其他歧义按不可逆门禁处理。
- 弹窗内 `Save` 与页面右上角 `Save` 必须区分，并严格按此顺序各点击一次。
- 页面右上角 `Save` 只能在 `Game Center` 未勾选确认完成后点击。
- 页面 Save 结果不明时只读核对同一版本/构建和保存状态，禁止第二次保存；恢复穷尽后才发最后故障卡。
- `See More` 与 `Edit` 顺序不可反；必须先完整展开 14 项再进入批量编辑。
- `02` 或 `03` 截图失败、文件权限/格式/哈希不合格时，在本技能同一页面安全重拍三轮，每轮都独立复核文件和页面归属；三轮恢复穷尽后才发卡，不得把补拍责任推给 `utm-24`。
- 失败项数量可为 0、1 或多个，必须按实时列表逐个补入同一个既有草稿；任何位置都禁止 `Create New Submission`。
- `Get Started`、`Add`、`Declare Regulated Medical Device`、`Set Up URL` 是空状态入口；不得误点。误入时自动 `Cancel`/`Back`；存在实际数据却无法唯一、安全移除时才进入最后故障卡。
- `utm-23` 只负责准备并复核现场；确认和最终提交属于 `utm-24`。移交前不得关闭页面、退出 Edge、切换 VM 或点击 `Submit for Review`。
- 每次 GUI 操作后必须等待至少 3 秒并读取最新状态；不得复用旧坐标。
