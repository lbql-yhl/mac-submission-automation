# UTM-24：最终取证、自动自检并提交审核

对应技能：`utm-24`。紧接 `utm-23` 立即执行，直接继承当前 run、原 `chat_id`、Ready for Review 页面、`utm-11` 的 `05-small-business.png` 和 `utm-23` 的 `02-iap-drafts.png`、`03-app-information.png`。本技能只采集 `01-media-manager.png`、`04-privacy-agreement.png`。五图、版本/构建、14 个 IAP 和 15 项范围全部通过后，由系统写入完整自动自检授权并自动提交一次；正常主线不发提审确认卡、不等待任何回复。

飞书故障卡功能继续保留，但只在自动诊断、自动修复和自动复验穷尽，或 CAPTCHA、账号锁定、权威数据缺失、所有权冲突、不可逆结果仍不明确等智能体确实不能修复时使用。兼容旧 run 的 review-card/callback 能力由运行时保留，不得成为新 run 的正常节点。绿色成功通知和 API 信息登记仍由 `utm-25` 完成。

## Checklist

- [ ] 已有同一 run 的 `UTM_23=verified`、`REVIEW_SCREENSHOT_02=verified`、`REVIEW_SCREENSHOT_03=verified`、`REVIEW_SCREENSHOT_05=verified`；两个技能之间没有任务、VM、Edge 或页面现场切换。
- [ ] 直接使用继承的 `run_id`、原 `chat_id`、应用、VM、App ID、版本和构建号，不选择“最新”或旧 run。
- [ ] `02`、`03`、`05` 位于当前 run 目录，权限 `600`、非空、PNG 可读且 SHA-256 与所属技能记录一致。缺失/损坏时只记录 `SCREENSHOT_RECOVERY=handoff_to_owner` 并回到所属技能的同一精确页面恢复，补拍后再由 `utm-24` 独立验证；`utm-24` 不越权伪造。
- [ ] 原 Ready for Review 标签页保持打开；只在同一 guest Edge 新标签采集 `01` 和 `04`，不启动、重启或切换浏览器进程。
- [ ] Media Manager 页面精确匹配当前应用、数字 App ID、版本和 `6.9" Display`；完整缩略图与 `N of 10 Screenshots` 同时可见后保存 `01`。导航误点关闭本轮新标签并回到原 Ready for Review 锚点，再重新定位。
- [ ] 先运行 `scripts/notion_api.py verify-parent`，再用同一脚本唯一读取 `隐私协议: `；调用 `OP-BROWSER-URL-NO-SCHEME`，执行 `pbpaste | python3 scripts/shared_operations.py browser-url`，只删除最前面的一个协议头并逐字节保留 `//` 后全部内容。只在统一执行器验证、随机哨兵回读和蓝色高亮 `Paste and Go` 均通过后打开；页面标题和 `Effective Date` 验证后保存 `04` 并清空剪贴板。
- [ ] 五张 PNG 均属于当前 run，权限 `600`、非空、可读，SHA-256 与各自记录一致，记录 `REVIEW_SCREENSHOTS=verified_5`。
- [ ] 切回原 Ready for Review 标签页，重新确认 run、应用、App ID、VM、版本、构建均未变化；唯一 `Draft Submissions (1)` 同时显示当前 App Version、`In-App Purchases (14)` 和 `Items Ready to Submit (15)`，且 `Submit for Review` 尚未点击。
- [ ] 调用 `record-auto-review-approval`，传入版本、构建号、`iap-count=14`、五张截图和 `REVIEW_SCREENSHOTS=verified_5;ITEMS_READY=15`。运行时必须原子写入并回读顶层 `review_submission_approval`：`kind=review_submit`、`source=automatic_self_check`、`status=approved`、`decision=submit_review`、稳定 `decision_id`、版本/构建、14 个 IAP、五图路径/哈希、15 项证据、`answered_at`、`operator_id=automation:self-check`。
- [ ] 若已有 waiting review 决定、显式 rejected/malformed 授权，或任何证据不完整，自动授权命令必须拒绝；先只读恢复同一现场，禁止点击提交。故障 `pending_decision` 和故障回调不得生成或覆盖送审授权。
- [ ] 授权写入后再次读取原标签页。现场变化会使本次授权作废：重新完成五图/范围检查并写入新的自动授权；不能恢复唯一状态时才进入最后故障卡。
- [ ] `Submit for Review` 暂时灰色时按 5/10/20/40 秒有界只读等待，每轮复核应用、版本、构建和 15 项范围。首次可能点击前生成稳定 `REVIEW_SUBMIT_ATTEMPT_ID`，用 `record-review-submit-attempt` 将 `prepared` 与当前 `decision_id`/15 项证据绑定；当状态依次原子推进为 `clicking -> result_unknown -> verified`，只点击一次。已有 attempt 只恢复同一 ID，不允许换 ID、跳级或回退。若有确认弹窗，只有应用、版本、当前 App Version + 14 个 IAP 和唯一提交按钮都匹配时才确认一次。
- [ ] 点击后结果不明时只读轮询同一 attempt 的页面/状态，禁止第二次点击。只有 `15 Items Submitted` 或 `Waiting for Review` 才记录精确 `APP_REVIEW_STATUS`。
- [ ] 保留 App Store 成功标签页，在同一 guest Edge 新标签通过剪贴板闭环打开裸地址 `developer.apple.com/contact/app-store/?topic=expedite`。
- [ ] 加急页先生成并原子保存稳定 `EXPEDITE_SUBMIT_ATTEMPT_ID`，绑定 run/App/`REVIEW_SUBMIT_ATTEMPT_ID` 与当前 review 成功状态。精确显示 `We’ll expedite review for <当前应用名>.` 时将 ledger 标记 `verified_existing_success`；只有完整 pristine form 且 ledger 为 `prepared` 才选择唯一应用和 `iOS`，持久化 `clicking`后只点击一次 `Send`，随即记录 `result_unknown`。partial/ambiguous 或结果不明只读恢复同一 ID，禁止第二次发送。
- [ ] 精确成功文案出现后记录 `EXPEDITED_REVIEW_RESULT=verified`、`API_CREDENTIALS_REGISTRATION=pending`、`REVIEW_SUCCESS_NOTIFICATION=not_sent`、`UTM_24=verified`，保留同一现场并立即交接 `utm-25`。

## 自动恢复与最后故障卡

- 每个 GUI 动作后等待至少 3 秒并读取新状态。菜单/下拉误点用 `Escape`，本轮错误新标签关闭后回到原锚点，字段误填只清目标字段并重读权威来源；每种可逆误点完整恢复三轮且每轮独立复验。
- 五图或 15 项证据不完整、自动授权写入/回读失败、已有 waiting/rejected 决定、授权后现场变化，都先按本技能矩阵自动恢复；恢复穷尽后才携带恢复证据发最后故障卡，未授权时不得点击。
- 提交 attempt 或加急 `Send` 一旦执行，结果不明只能查询同一 attempt，任何故障卡决定都不能授权第二次点击。
- 故障卡只发当前 run 原非日报 `chat_id`；运行时校验宿主机所有权并拒绝缺少 `recovery_attempts`、`recovery_actions`、`recovery_result` 的请求。

## 完成标记

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
EXPEDITED_REVIEW_SEND=clicked_once|skipped_existing_success
EXPEDITED_REVIEW_RESULT=verified
API_CREDENTIALS_REGISTRATION=pending
REVIEW_SUCCESS_NOTIFICATION=not_sent
UTM_24=verified
```

`UTM_24=verified` 后立即交接 `utm-25`；本技能不发送成功通知。
