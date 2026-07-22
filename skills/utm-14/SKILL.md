---
name: utm-14
description: Use after utm-13 when the same UTM macOS guest's existing Microsoft Edge session must handle App Store Connect Business-page compliance, agreement, or tax-form follow-up including W-8BEN date fields.
---

# UTM-14

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
  --stage 'utm-14:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-14' \
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
| 表单/日期/声明误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图；提交前使用 `Escape`/`Back`/`Cancel` 回到本表单锚点，只恢复错误字段并逐项回读，记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立核对后仍无法恢复才发卡 |
| CEO/生日粘贴错误 | 只清目标字段，实时权威源重读，剪贴板哨兵后重贴并回读 | 三轮安全重贴且每轮独立回读后仍不符才 `exhausted` |
| 每份最终 Submit 结果不明 | 每表单稳定 attempt 只点击一次；只读检查 Business 返回、协议状态和表单是否仍 pending | 仍 ambiguous 发卡，绝不第二次提交 |
| 未知税务/安全页面 | 只读分类账号、表单和错误，不猜选项 | 外部未知状态 `--unrepairable` |

## 前置检查

- 当前运行已完成 `utm-13`，并确认 `UTM_13=verified`、`PROVISIONING_PROFILE_DOWNLOAD=ready`。
- 当前仍是同一台 guest、同一个 Edge 进程和同一组已有标签页；无法确认时暂停 GUI 操作，先按 `utm-14-session-identity` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定，不用新浏览器补救。
- 已有 App Store Connect 标签页应可见。首次找不到时不立即报告：保持同一 guest/Edge，做三轮相隔至少 3 秒的独立只读进程、窗口标题、标签列表、账号会话和 VM 归属检查；仅在 `BROWSER_SESSION_RECHECKS=3` 后仍不存在才记录 `appstoreconnect_tab_missing`，且规则仍禁止启动新浏览器。
- 当前账号/主体与 App Store Connect 页面一致；主体、协议或税务问题不明确时暂停 GUI 操作，先按 `utm-14-business-context` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
- `${PROJECT_ROOT}/.env` 已配置当前父页面的 Notion API 访问；Notion 生日只通过项目 `scripts/notion_api.py` 读取。

## 硬性规则

- 不启动、重启或切换新的浏览器进程；“切回”只表示激活已有 guest Edge 和已有标签页。
- 每次切换窗口、标签页、滚动、点击、右键或粘贴后等待至少 3 秒，再读取最新截图和页面状态。
- 页面变化后重新定位目标，不复用旧坐标；优先使用页面中当前可见且文字明确的目标。
- 不刷新、不新开标签页、不改 URL 来猜测页面；找不到目标或结果不明确时先按 `utm-14-page-state` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
- 不猜主体、税务答案、手机号或验证码；已知 2FA 调用 `OP-APPLE-PHONE-OTP`，未知或不唯一状态先按本技能矩阵完成三轮独立只读复核，仍不可安全归类才进入最后故障卡。
- 两次最终 `Submit` 都在各自页面完成全部字段、声明、按钮和账号自检后自动点击一次，不等待用户确认；前一次页面证据不得复用于后一次。
- 不得用宿主 Chrome、Notion 插件、Playwright、CUA、坐标或浏览器剪贴板读取 Notion。

## 操作步骤

1. 获取 guest 最新截图，激活当前 Microsoft Edge 窗口，在已有标签页中确认页面属于 App Store Connect 且账号会话有效。
2. 等待至少 3 秒后重新读取截图，重新定位并点击当前页面的 `Business`；确认它不是浏览器菜单、其他标签页内容或普通文本。
3. 等待至少 3 秒并确认已进入 Business 相关页面；点击反馈或 URL 变化本身不算完成。
4. 若出现 `Complete Compliance Requirements`：打开 DSA 弹窗，选择 `I'm not a trader under the DSA or I don't plan to distribute in the EU`，确认选中后点击 `Done`，等待并确认绿色完成提示。若已显示绿色完成提示，只记录该证据，不重复提交；目标缺失且没有已完成证据时先按 `utm-14-dsa-state` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
5. 若出现 `Sign the Paid Apps Agreement`：打开协议，勾选协议确认框，确认 `Agree` 已启用后点击 `Agree`，等待并确认协议结果或 2FA 处理完成；不能仅凭弹窗消失认定已接受。若入口已隐藏，必须看到协议已接受/完成的页面证据；否则先按 `utm-14-paid-agreement-state` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定。
   - 若出现 `Two-Factor Authentication Required`，自动复用 `utm-10` 的实时尾号匹配和宿主终端取码路径；不得打开短信浏览器标签页。零/多匹配或验证码被拒绝时重新读取实时电话/SMS 响应三轮并核对提示归属；未知安全提示或三轮仍无唯一当前验证码时才作为外部不可修复状态进入最后故障卡。验证完成后确认回到 Business 页面。
6. 在 Business 页面使用 `Page Down`（若滚轮未移动，优先用 `Page Down`），每次等待并读取新截图，直到 `Tax Forms` 和 `U.S. Tax Questionnaire` 可见；从最新截图重新定位并打开 `U.S. Tax Questionnaire`。
7. 在 `U.S. Tax Questionnaire` 中：
   - `Are you considered a U.S. resident?` 选择 `No`，确认选中后点击 `Next`。
   - `Do you have any U.S. Business Activities?` 选择 `No`；在点击前重新读取截图确认该 `No` 仍选中且按钮为 `Save`，再点击。此处按钮是 `Save`，不要把它当成 `Next`；等待弹窗关闭并确认 Tax Forms 已更新，出现两个税务表单行后才算保存持久化。
8. 打开 `U.S. Certificate of Foreign Status of Beneficial Owner`。不要自动填写或修改未授权的预填字段；向下滚动到声明区，勾选以 `I declare that the individual or organization...` 开头的声明，并确认复选框已选中。
   - 打开后先在顶部逐项读取所有标记 required 的预填字段，要求每一项非空、无红色错误，账号/主体/国家与 Business 上下文一致；不改名、地址、税号或其他预填值。将字段标签、非空状态、账号/表单 identity 和截图 hash 写入本表单 ledger。
9. 在 `Title` 字段准备剪贴板并确认原生读回值为 `CEO`；先点击当前证书表单的 `Title` 输入框，等待并确认焦点确实在该字段，再右键确认菜单中的 `Paste`，点击该菜单项，等待并确认字段精确显示 `CEO`。不要用 CUA 逐字输入替代原生粘贴。
10. 使用 `Page Up` 回到顶部后，重新读取全部 required 预填状态；把顶部字段、声明、`Title=CEO`、唯一启用 Submit、账号/表单 identity 合并为 `FOREIGN_FORM_LEDGER=verified`。原子持久化稳定 `FOREIGN_FORM_SUBMIT_ATTEMPT_ID` 和 `status=planned`，再从最新截图逐项复验；一致才更新 `clicking` 并点击一次 Submit。结果不明只查询同一表单状态/Business 返回，不重复点击；确认返回且对应表单不再 pending 才更新 `submitted`。
11. 提交当前证书并返回 Business 后，使用 `Page Down` 回到 `Tax Forms`，从最新截图重新定位并打开 `U.S. Form W-8BEN`。
12. 在 `${PROJECT_ROOT}` 先执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，再执行 `python3 scripts/notion_api.py read-field --title '<应用名>-<vm_name>' --heading '账号信息' --label '生日：' --copy`。要求 API 唯一匹配且安全元数据表明值非空；不得输出生日值。若该字段为空，可改从同一 guest Apple Account 设置读取；API 与 guest 都无法确认时先按 `utm-14-birthday-source` 记录故障阶段并执行本技能自动恢复矩阵；恢复穷尽后才发送最后故障卡并等待当前执行器处理决定，不猜日期。打开 `Date of Birth` 字段前确认当前表单标题为 `U.S. Form W-8BEN`。
13. 使用日期选择器填写生日，不在日期输入框右键粘贴：
   - 点击 `Date of Birth` 字段，读取日期选择器当前显示的年份和月份。
   - 点击年份标题打开年份列表。计算当前年与目标年的整数差；每次只按一个 `Up` 或 `Down`，每次等待至少 3 秒并确认高亮正好移动一年、焦点仍在年份列表，再递增已验证计数。计数等于绝对差且高亮等于目标年时才按 `Return` 并重读标题。
   - 月份同理：每次只移动一个月并等待/重读；不能把 N 次按键作为一个操作。目标年月与最终字段格式均闭环后记录 `DATE_KEYSTROKES_VERIFIED`。
   - 在目标年月日历中选择目标日，等待并确认日期选择器关闭；日期字段必须精确显示 `MM-DD-YYYY`，例如 `01-01-2000`。
14. 向下滚动并处理 W-8BEN 的剩余声明：
   - Part II 勾选以 `I certify that the beneficial owner...` 开头的声明；确认 `Income from the sale of applications` 已选中。若未选中，只选择该项，不选择 `Other`。
   - Part III 勾选以 `Under penalties of perjury...` 开头的第一项声明，以及下方以 `I certify that I have the capacity...` 开头的第二项声明。若复选框已选中只记录状态，不重复点击造成取消。
   - 每次勾选或选择后等待并重新读取截图，确认四项状态：Part II 声明、Income from the sale of applications、Part III 第一项、Part III 第二项。
15. 在 W-8BEN 顶部先逐项读取所有 required 预填字段，要求非空、无红色错误且账号/主体/国家一致；与生日、Part II declaration、唯一 application-sale income、Part III 两项、唯一启用 Submit 和各自截图 hash 合并成 `W8BEN_LEDGER=verified`。页面位置变化后任何单项过期都必须回到相应区域重读，不能凭记忆。
16. 原子持久化稳定 `W8BEN_SUBMIT_ATTEMPT_ID` 和完整 ledger hash/`status=planned`；独立回读仍一致才更新 `clicking` 并自动点击一次 Submit。等待至少 3 秒，只读确认返回 Business 且该 W-8BEN 不再 pending 后更新 `submitted`；结果不明不得重复提交。若仍有银行或协议提示，只记录状态。
17. 返回 Business 页面后向下滚动；每次滚动后等待至少 3 秒并读取最新截图，直到精确条目 `Directive on Administrative Cooperation - 7th Amendment` 可见。从最新截图确认其右侧 `Add Info` 唯一属于该条目，再点击。
18. 等待至少 3 秒并确认已打开该条目的信息弹窗；勾选 `No`，重新读取截图确认 `No` 已选中且 `Done` 已启用，再点击 `Done`。返回 Business 后重新打开同一唯一条目做只读回读，要求 saved value 仍为 No，再取消/关闭而不改值；记录 `DAC7_READBACK=No_saved`。仅有点击反馈或弹窗消失不算完成。

## 完成检查

```text
UTM_14=verified
APP_STORE_CONNECT=focused
BUSINESS=clicked
BUSINESS_RESULT=verified
DSA_COMPLIANCE=verified
PAID_APPS_AGREEMENT=accepted
US_TAX_QUESTIONNAIRE=No_No_saved
FOREIGN_STATUS_FORM=verified
BUSINESS_RETURN=verified
FOREIGN_FORM_SUBMIT_ATTEMPT_ID=<stable-id>
FOREIGN_FORM_LEDGER=verified
W8BEN_DOB=verified
DATE_KEYSTROKES_VERIFIED
W8BEN_PARTS=verified
W8BEN_SUBMIT_ATTEMPT_ID=<stable-id>
W8BEN_LEDGER=verified
W8BEN_SUBMIT=verified
DAC7_INFO=No_saved
DAC7_READBACK=No_saved
```

## 阻断条件

- `BROWSER_PROCESS_GUARD=blocked`
- `appstoreconnect_tab_missing`
- `appstoreconnect_page_mismatch`
- `account_session_missing`
- `business_target_ambiguous`
- `business_target_missing`
- `business_navigation_not_verified`
- 主体或账号不匹配
- DSA、协议或税务答案不明确
- `Save` 未持久化
- 声明复选框或 `Title` 无法确认
- `Submit` 置灰、所属表单不明确或提交结果不明确
- 生日来源无法确认
- 年份/月列表焦点丢失、差值方向不明确或 `Return` 后未显示目标年月
- 目标日期不存在或最终格式不是 `MM-DD-YYYY`
- Part II/Part III 任一声明未选中、Income 类型错误或无法确认最终状态
- W-8BEN `Submit` 置灰、当前表单不明确或提交后未返回 Business 页面
- `Directive on Administrative Cooperation - 7th Amendment` 条目缺失或不唯一、右侧 `Add Info` 归属不明确
- `No` 未确认选中、`Done` 未启用或点击后无法确认信息已保存

发生阻断时暂停新的副作用，先按对应 `utm-14-*` stage 执行本技能矩阵的回锚、重读、可逆恢复和独立复验；恢复穷尽或不可逆结果仍不明确时才发送最后故障卡。不猜坐标、不启动新浏览器、不把点击本身当作成功。

## 基线防错

| 误区 | 正确做法 |
|---|---|
| “页面布局没变，可复用旧坐标” | 页面变化后从最新截图重新定位 |
| 文字叫 Business，直接点击即可 | 先确认目标属于当前 App Store Connect 页面 |
| `No` 选中后总是点 `Next` | 第二题的最终按钮是 `Save`，必须按可见按钮执行 |
| 声明或 Title 看起来填过了 | 重新确认复选框已勾选、Title 精确为 `CEO` |
| 日期输入框右键粘贴 | 使用日期选择器的年份/月列表、`Up` 差值和 `Return`；右键会打开页面菜单 |
| 2027 到 2004 只凭感觉按键 | 明确计算 `2027-2004=23` 次 `Up`，并在最新截图确认高亮为 2004 |
| 收入类型或声明看起来已选中 | 重新确认 Part II 声明、Income from the sale of applications、Part III 两项声明均已选中 |
| 点击有反馈就是完成 | 每个动作后等待并确认页面/状态结果；W-8BEN Submit 在全部校验通过后自动执行一次，且必须验证返回 Business |
| W-8BEN 返回 Business 就结束 | 继续下滑找到 `Directive on Administrative Cooperation - 7th Amendment`，点击其右侧 `Add Info`，选择 `No` 并确认 `Done` 后已保存 |

## 连续交接

仅当本技能全部完成检查通过时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-15`；不得等待用户确认。阻断、失败或未完成状态不得交接。

任何未知安全提示、2FA 零/多匹配、提交结果不明或页面/主体不一致都先暂停新副作用，回到最近验证的表单/账号锚点，完成本技能矩阵规定的三轮页面分类、实时来源重读和同一 attempt 独立只读复验。恢复成功即自动从失败步骤继续；只有三轮恢复穷尽或证明为外部不可修复状态才进入最后故障卡。`manual_continue` 与 `retry_skill` 都必须先重跑同一恢复矩阵，不得把回复当成成功证据；正常主线不发确认卡。
