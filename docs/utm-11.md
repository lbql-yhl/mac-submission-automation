# UTM-11：Small Business Program 登记

## 前置

继承 `UTM_10=verified`、同一 guest Edge 和 Apple Developer 账号页。当前 Edge 已有成功页时直接复核并截取证据，绝不重新提交。

## 步骤

1. 先检查并自动接受当前账号最新 Paid Applications Agreement；返回固定页面后重新核对账号。
2. 打开 Small Business Program，点击 `Enroll now`；第一题单选 `Yes`，后四题逐项单选 `No`，每次操作后等待至少 3 秒并读取最新状态。
3. 逐项确认题目文本、账户和答案哈希；勾选 attestation checkbox，回读为 checked。任何不确定都回到页面锚点，不盲点。
4. 原子写入 mode-600 `ENROLLMENT_SUBMIT_ATTEMPT_ID` ledger，状态先 `planned`，独立回读页面和 ledger 后才改 `clicking`。
5. 仅当五个答案、attestation 和唯一 enabled `Submit` 全部匹配时点击一次；已有 `clicking/submitted/unknown` ledger 只读恢复，不再点击。
6. 在同一新页面读到两条成功文案：`Thank you for your submission.` 与 `We've received your App Store Small Business Program enrollment...`，才写 `status=submitted`。
7. 保留成功页，保存当前 run 的 `runtime/review-screenshots/<run_id>/05-small-business.png`，校验 PNG、非空、mode 600 和 SHA-256；截屏失败只在成功页复拍，禁止再次提交。
8. 记录 `SMALL_BUSINESS_SUCCESS_MESSAGES=verified`、`REVIEW_SCREENSHOT_05=verified`、`UTM_11=verified`，交接 `utm-12`。

## 恢复边界

协议/答案/attestation 不一致时先回到最后锚点并三轮只读复核；提交结果不明只轮询同一 attempt。只有截图恢复或外部页面状态穷尽才发故障卡；正常主线不发送确认卡、不等待用户。
