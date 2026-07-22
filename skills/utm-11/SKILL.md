---
name: utm-11
description: Use after utm-10 when the same signed-in UTM macOS guest must submit the Apple App Store Small Business Program enrollment questionnaire in the already-open Microsoft Edge session.
---

# UTM-11

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
  --stage 'utm-11:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-11' \
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
| 协议/问卷误点 | 窗口尺寸、焦点或误点后至少 3 秒读最新截图；提交前用 `Back`/`Cancel` 回到问卷锚点并恢复 Yes/No 期望值，记录 `GUI_RECOVERY=verified` | 三轮可逆修复且每轮独立核对后仍无法唯一恢复才发卡 |
| Enrollment Submit 结果不明 | 只点击一次并记录 attempt；只读检查成功文案/已提交页，不再次提交 | 仍 ambiguous 才发卡 |
| 成功截图失败 | 保留成功页，重新获取最新截图并安全保存三轮；不重新提交换证据 | 三轮保存/复验失败才 `exhausted` |
| 已提交现场 | 直接验证成功文案并恢复截图 | 禁止重复提交 |

## Preconditions

- Continue in the same guest, `<vm_name>`, and Microsoft Edge session used by `utm-10`.
- Inherit the current `run_id` created for this submission; never select a latest, old, or different run for screenshot storage.
- Reuse the existing `App Store Small Business Program` tab. Do not open, restart, switch, or launch another browser process.
- The guest is signed in to the intended Apple Developer account.
- Do not open membership, payment, or unrelated developer resources. App Store Connect `Business` may be opened only for the automatic Paid Applications Agreement preflight below.

## GUI discipline

- Use the current Computer Use/sky GUI driver for every guest Edge action; it is not another project workflow skill.
- After every click, scroll, drag, key press, or navigation, wait at least 3 seconds and read a fresh screenshot/state before continuing.
- Scroll slowly in small increments. Prefer a small scrollbar drag after clicking page whitespace; do not use a large `Page Down` that can skip the first question.
- Never press arrow keys while a radio button is focused: `Down` can change the answer instead of scrolling.
- Never reuse coordinates after scrolling or navigation. Re-derive them from the latest screenshot.
- If the page, question text, selected state, or target account is unclear, preserve the latest non-sensitive screenshot/state, return to the last verified page anchor, and re-read the account, page and selections through the bounded `utm-11-page-state` matrix. Only exhausted recovery or a proven external account/schema change may send the last global fault card; never guess or click while unclear.

## Fixed answers

The tested questionnaire has exactly five radio questions. Match the question text before selecting:

1. `Have you reviewed and accepted the latest Paid Applications Agreement (Schedule 2 to the Apple Developer Program License Agreement) in App Store Connect?` -> select `Yes, I have accepted.`
2. `Do you have majority (over 50%) corporate, individual, or partnership interest in the ownership or shares of another Apple Developer Program member account?` -> select `No`.
3. `Does another Apple Developer Program member have majority (over 50%) corporate, individual, or partnership interest in the ownership or shares of your account?` -> select `No`.
4. `Do you have ultimate decision-making authority over another Apple Developer Program member account?` -> select `No`.
5. `Does another Apple Developer Program member have ultimate decision-making authority over your account?` -> select `No`.

If the page shows fewer, more, or materially different questions, do not assume that “all later” still means these answers; preserve the visible mismatch, reload the same page/account read-only and compare the full question set in the `utm-11-small-business-questions` matrix. Only a persistent external schema change after recovery exhaustion may send the last global fault card.

## Workflow

1. In the existing guest Edge window, select the `App Store Small Business Program` tab and preserve it. Confirm the page/account; record whether both success messages are already visible, but do not branch to screenshot yet.
1a. For every run, including an already-submitted success page, use a new tab in the same Edge process to open App Store Connect `Business` and verify the current account has accepted the latest Paid Applications Agreement. If `Sign the Paid Apps Agreement` is visible, automatically open it, verify the agreement identity, check the agreement box, click the unique enabled `Agree` once, and automatically complete any known 2FA through `utm-10`'s live Notion path. Require accepted/completed evidence and record `PAID_APPS_AGREEMENT=accepted`; close only this preflight tab and return to the preserved Small Business tab. For account mismatch/unknown state/failed 2FA, keep the questionnaire untouched and perform two read-only page/account classifications plus fresh live Notion reads. Only exhaustion/proven external security state reaches the last card.
1b. Back on the preserved tab, if the two exact success messages were already visible, record `SMALL_BUSINESS_SUCCESS_MESSAGES=verified` and continue directly to screenshot step 12; do not reopen or resubmit the enrollment form merely for evidence. Otherwise continue to step 2; the first radio cannot be answered without step 1a evidence.
2. Scroll slowly to `Get started today.`. Confirm the visible `Enroll now` button, then click it.
3. Wait for the page titled `Enroll in the App Store Small Business Program`. Confirm the signed-in account and form before proceeding.
4. Scroll slowly to the first radio question. Select `Yes, I have accepted.`.
5. Scroll in small increments and select `No` for each of the four exact questions listed above. After each selection, confirm the filled radio dot is on `No` before moving on.
6. Scroll slowly to the final attestation. It begins `To the best of your knowledge, you and your Associated Developer Accounts earned no more than 1,000,000 USD...`.
7. Once the current account, exact attestation text, and all five fixed answers match this skill, automatically check the attestation checkbox. Do not infer, alter, or fabricate the income/accuracy claim.
8. Re-read the latest screenshot and confirm the attestation checkbox is visibly checked.
9. Review the whole form slowly in both directions. Confirm exactly: first radio = `Yes`; all four later radios = `No`; attestation checkbox = checked. Fix any mismatch before submission.
10. Once the full-form review in step 9 passes and the unique `Submit` control is visibly enabled, atomically persist a mode-600 current-run ledger with stable `ENROLLMENT_SUBMIT_ATTEMPT_ID`, account/page identity, hashes of the five selected answers plus attestation, `status=planned` and no success claim. Independently re-read the ledger and current form; only when both still match update status to `clicking` and automatically click `Submit` once. If a ledger already exists, inherit the same attempt: `clicking/submitted/unknown` permits read-only result recovery only, never another click.
11. Wait for the result page and confirm both visible messages:

    ```text
    Thank you for your submission.
    We've received your App Store Small Business Program enrollment and will email you about your status soon.
    ```
    Update the same ledger to `status=submitted` and record `SMALL_BUSINESS_SUCCESS_MESSAGES=verified` only after both strings coexist in one fresh page read.
12. Only after both messages are visible in the latest UTM state, save the success-page evidence for this current run. In the same Computer Use `node_repl` session, replace `<current run_id>` only with the inherited current value, validate it, and execute:

    ```javascript
    var reviewRunId = "<current run_id>";
    if (!/^[A-Za-z0-9-]{8,80}$/.test(reviewRunId)) throw new Error("invalid run_id");
    var path = await import("node:path");
    var projectRoot = process.env.PROJECT_ROOT;
    if (!projectRoot || !path.isAbsolute(projectRoot)) throw new Error("PROJECT_ROOT unavailable");
    var screenshotBase = path.resolve(projectRoot, "runtime", "review-screenshots");
    var reviewRoot = path.resolve(screenshotBase, reviewRunId);
    if (!reviewRoot.startsWith(screenshotBase + path.sep)) throw new Error("review path escaped");
    var fs = await import("node:fs/promises");
    var { execFile } = await import("node:child_process");
    var { fileURLToPath } = await import("node:url");
    var { promisify } = await import("node:util");
    var execFileAsync = promisify(execFile);
    await fs.mkdir(reviewRoot, { recursive: true, mode: 0o700 });
    await fs.chmod(reviewRoot, 0o700);
    globalThis.saveReviewScreenshot = async function (name) {
      var state = await sky.get_app_state({ app: "com.utmapp.UTM", disableDiff: true });
      if (!state.screenshot?.url) throw new Error("UTM screenshot unavailable");
      var target = `${reviewRoot}/${name}`;
      await execFileAsync("/usr/bin/sips", ["-s", "format", "png", fileURLToPath(state.screenshot.url), "--out", target]);
      await fs.chmod(target, 0o600);
      var stat = await fs.stat(target);
      if (!stat.isFile() || stat.size === 0) throw new Error(`empty screenshot: ${name}`);
      return target;
    };
    await saveReviewScreenshot("05-small-business.png");
    ```

    Use read-only host checks to confirm the fixed file is under the current run directory, mode `600`, non-empty, readable as PNG, and has a recorded SHA-256. Record `REVIEW_SCREENSHOT_05=verified`. If capture or validation fails, preserve the submitted success page and use the same success page to recapture/validate through the bounded `utm-11-review-screenshot` matrix without resubmission. Only exhausted screenshot recovery may record `REVIEW_SCREENSHOT_05=blocked`, `UTM_11=blocked`, send the last global fault card and wait; never submit the enrollment again merely to recreate the screenshot.

## Completion

Report only:

```text
UTM_11=verified
SMALL_BUSINESS_ENROLLMENT=submitted
QUESTIONNAIRE=verified
PAID_APPS_AGREEMENT=accepted
SMALL_BUSINESS_SUCCESS_MESSAGES=verified
ENROLLMENT_SUBMIT_ATTEMPT_ID=<stable-id>
REVIEW_SCREENSHOT_05=verified
```

Any other blocked state must first run the matching `utm-11-blocked-state` diagnosis, reversible repair and independent recheck. Only recovery exhaustion or a proven external/unrecoverable state may send the last global fault card and wait before reporting `UTM_11=blocked`; include only the non-secret blocker category, such as `page_mismatch`, `question_mismatch`, `attestation_not_confirmed`, `answer_verification_failed`, `submission_error`, or `review_screenshot_failed`.

## 连续交接

仅当本技能全部完成检查通过时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `utm-12`；不得等待用户确认。阻断、失败或未完成状态不得交接。
