# UTM-14：App Store Connect Business 合规与税务

## 定位

`utm-14` 接在 `utm-13` 后，继续使用同一台 UTM guest 和同一个 Microsoft Edge，会话切回已有 App Store Connect 页面，进入 `Business`，处理本次真实验证的合规、协议和税务表单。

两次最终 `Submit` 都在各自表单完成账号、字段、声明和唯一按钮自检后自动点击一次，不等待用户确认。任何异常先回到当前表单最近验证锚点、重读权威来源并复验；只有未知安全状态、来源仍歧义或不可逆提交结果只读恢复后仍不明确时才进入最后故障卡。

## 前置检查

- [ ] `utm-13` 已完成，确认 `UTM_13=verified` 和 `PROVISIONING_PROFILE_DOWNLOAD=ready`。
- [ ] 仍是同一台 guest、同一个 Edge 进程和同一组已有标签页。
- [ ] 已有 App Store Connect 标签页可见。
- [ ] 当前账号/主体与页面一致；不明确时重新读取当前账号、Business 身份和实时 Notion 来源三轮，仍冲突才作为外部所有权状态进入最后故障卡。
- [ ] 项目 `.env` 已配置当前父页面的 Notion API 访问；先在项目根目录运行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，不得用宿主浏览器或插件读取 Notion。

## 操作 Checklist

- [ ] 激活已有 guest Edge，不启动、重启或切换新的浏览器进程。
- [ ] 在已有标签页中确认当前页面属于 App Store Connect，账号会话有效。
- [ ] 等待至少 3 秒，读取最新截图并重新定位 `Business`。
- [ ] 点击 `Business`，等待至少 3 秒，确认已出现 Business 相关页面。
- [ ] 若有 `Complete Compliance Requirements`，选择 `I'm not a trader under the DSA or I don't plan to distribute in the EU`，确认后点击 `Done`，验证绿色完成提示；入口隐藏时必须有已完成证据。
- [ ] 若有 `Sign the Paid Apps Agreement`，勾选协议确认框并点击 `Agree`；出现已知 2FA 时调用 `OP-APPLE-PHONE-OTP`。未知安全状态先独立只读确认三轮，仍不能归类才发最后故障卡。
- [ ] 向下使用 `Page Down`，直到 `Tax Forms` 可见，打开 `U.S. Tax Questionnaire`。
- [ ] 第一题 `Are you considered a U.S. resident?` 选 `No`，点击 `Next`。
- [ ] 第二题 `Do you have any U.S. Business Activities?` 选 `No`；点击前重新读取截图确认 `No` 仍选中且按钮为 `Save`，再点击；确认弹窗关闭并出现两个税务表单行，证明问卷已保存。
- [ ] 打开 `U.S. Certificate of Foreign Status of Beneficial Owner`。
- [ ] 向下滚动，勾选以 `I declare that the individual or organization...` 开头的声明。
- [ ] `Title` 先确认焦点位于当前证书表单的输入框，再完整调用 `OP-NATIVE-PASTE` 粘贴 `CEO`，确认字段精确显示 `CEO`。
- [ ] `Page Up` 回到顶部，重新确认页面标题为当前证书表单，且声明、Title 和已启用的唯一 `Submit` 均属于该表单；全部核对通过后自动点击一次 `Submit`，不等待人工授权。
- [ ] 等待并确认已返回 Business 页面。
- [ ] 向下滑回 `Tax Forms`，打开 `U.S. Form W-8BEN`。
- [ ] 在项目根目录执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`，再用 `python3 scripts/notion_api.py read-field --copy` 唯一读取 `生日：`；API 字段为空时才允许从同一 guest Apple Account 设置确认。来源不明确时重新读取两种允许来源三轮，仍不唯一才发最后故障卡。
- [ ] 打开 `Date of Birth` 日期选择器，读取当前年份/月；不在日期输入框右键粘贴。
- [ ] 年份：目标年份较早时按 `Up` 年份差；例如 `2027-2004=23` 次；每轮确认焦点仍在年份列表，按 `Return` 确认目标年份。
- [ ] 月份：目标月份较早时按 `Up` 月份差；例如 July 到 January 按 `Up` 6 次；按 `Return` 确认目标月份。
- [ ] 选择目标日，确认日期字段精确显示 `MM-DD-YYYY`，例如 `01-01-2000`。
- [ ] Part II 勾选以 `I certify that the beneficial owner...` 开头的声明，确认 `Income from the sale of applications` 已选中；不要选择 `Other`。
- [ ] Part III 勾选以 `Under penalties of perjury...` 和下方 `I certify that I have the capacity...` 开头的两项声明。
- [ ] 重新读取截图确认 Part II 声明、Income 类型、Part III 两项声明均已选中。
- [ ] `Page Up` 回到 W-8BEN 顶部，重新确认当前表单、生日、Part II/Part III、Income 类型和已启用的唯一 `Submit`；全部核对通过后自动点击一次 `Submit`，不等待人工授权，且前一表单证据不得替代本表单自检。
- [ ] 等待并确认返回 Business 页面，才算 W-8BEN 提交成功。
- [ ] 返回 Business 后向下滚动；每次等待至少 3 秒并读取最新截图，直到精确条目 `Directive on Administrative Cooperation - 7th Amendment` 可见。
- [ ] 确认右侧 `Add Info` 唯一属于该条目后点击；在信息弹窗中勾选 `No`，确认已选中且 `Done` 已启用，再点击 `Done`。
- [ ] 等待并确认返回 Business 页面且该条目信息已保存；仅有点击反馈或弹窗消失不算完成。

## 完成标准

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
W8BEN_DOB=verified
W8BEN_PARTS=verified
W8BEN_SUBMIT=verified
DAC7_INFO=No_saved
```

## 风险点

- 不复用 `utm-13` 的旧坐标；页面变化后必须从最新截图重新定位。
- 每个点击、滚动、粘贴后等待至少 3 秒并读取最新截图；不能复用旧坐标。
- `U.S. Tax Questionnaire` 第二题的按钮是 `Save`，不是 `Next`；保存未确认时只读核对同一问卷结果，不重复点击。
- 复选框、Title、Submit 归属或日期不明确时回到表单锚点重新定位三轮，每轮都独立回读；不可逆提交结果不明时改做三轮独立只读查询，禁止第二次提交。
- 日期输入框不要右键粘贴；使用年份/月列表、差值按键、`Return` 和日历选日。
- Part II/Part III 或 Income 类型无法确认时回到同一表单重读；提交后未返回 Business 时只读核对同一提交 attempt，恢复穷尽后才发卡。
- DAC7 条目/按钮/保存结果不明确时回到 Business 锚点独立重读三轮；仍不唯一才发最后故障卡。
- 找不到 App Store Connect 页面或 `Business` 目标时，完整重查既有标签、登录会话、进程和 VM 归属三轮独立只读；规则禁止新开/重启且三轮均不存在时，才作为外部不可修复状态发卡。
- 仅点击成功、URL 变化或出现短暂反馈都不能代替 Business/表单结果确认。
