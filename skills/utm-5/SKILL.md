---
name: utm-5
description: Use after utm-4, before utm-clash, when the host Mac must generate or overwrite ${SUBMISSION_SHARED_DIR}/socks5.yml from the current Feishu submission proxy data.
---

# UTM-5

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
  --stage 'utm-5:<fault-stage>' \
  --fault '<non-sensitive-fault>' \
  --suggested-action '<safe-next-action>' \
  --failure-action '自动恢复穷尽后暂停副作用并等待故障卡决定' \
  --evidence '<non-sensitive-evidence>' \
  --completed-steps '<verified-completed-steps>' \
  --recovery-skill 'utm-5' \
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
| 当前 run 读取失败 | 只按精确 `run_id` 重读三次，禁止 latest/VM 名/消息历史回退 | 权威 proxy 仍缺失为 `unrepairable` |
| 输出目录缺失 | 从动态 `SUBMISSION_SHARED_DIR` 创建精确目录并验证，不猜宿主用户名 | 无权限才发卡 |
| 原子写入/哈希失败 | 保存旧文件 before；重新生成一次并校验 YAML，失败则自动恢复 before | 还原后仍无法写为 `exhausted` |
| 已有相同文件 | 比较当前 run 数据生成哈希，完全一致直接幂等完成 | 不重复覆盖 |

## Overview

Generate `socks5.yml` on the host Mac at `${SUBMISSION_SHARED_DIR}/socks5.yml`. This skill only writes the host file; it does not open Clash Verge, SSH into the VM, or change UTM sharing settings.

## Preconditions

- Run from the project root: `${PROJECT_ROOT}`.
- Directly inherit `UTM_4=verified`, the current Feishu `run_id`, and `vm_name`; read only that run's `submission_data.proxy` from `runtime/feishu-runs.json`.
- If the exact run or its proxy fields are missing, reload the same run atomically from the Feishu bot runtime/API at immediate/5/10-second intervals and verify its host ownership and immutable `vm_name` each time. If any required field remains absent, preserve the run, record only the non-sensitive missing-field list and mark `utm-5-proxy-data` unrepairable; only then send the last global fault card and wait. Do not fall back to latest Feishu history, manually supplied proxy values, examples, or another run.
- Output path is always `${SUBMISSION_SHARED_DIR}/socks5.yml`.
- Do not generate a new VM name or change `${SUBMISSION_VM_IMAGES_DIR}/<vm_name>.utm`.

## Workflow

1. Run the preflight command from the file header and require `PROJECT_ROOT`, `PROJECT_SKILLS_DIR` and `SUBMISSION_SHARED_DIR` to be non-empty absolute paths; shared dir and output must not be symlinks. Re-read only the inherited exact `run_id`; require one runtime record, exact local-host ownership, an unchanged `^[a-z]{4}$` `vm_name`, and proxy fields without leading/trailing whitespace or control characters. `host` must be canonical IPv4, `port` canonical decimal 1–65535, username/password non-empty. Record only invalid/missing field names, never values.
2. Before changing the output, run the writer's non-mutating self-check and require `self-test ok` with exit code `0`:

```bash
python3 "${PROJECT_SKILLS_DIR}/utm-5/scripts/write_socks5_yml.py" \
  --run-id '<current_run_id>' --self-test
```

3. Resolve the only target as `${SUBMISSION_SHARED_DIR}/socks5.yml`. If it exists, record its type, mode, byte count and SHA-256 without printing its contents; reject a symlink or non-regular file. Generate the current run's file atomically:

```bash
python3 "${PROJECT_SKILLS_DIR}/utm-5/scripts/write_socks5_yml.py" \
  --run-id '<current_run_id>'
```

4. Require exit code `0` and exact non-sensitive markers: `SOCKS5_RUN_ID=exact_matched`, `SOCKS5_RUN_HOST=verified`, exactly one of `SOCKS5_WRITE=changed|unchanged`, `SOCKS5_READBACK=exact`, `SOCKS5_OUTPUT=verified`, and `SOCKS5_MODE=600`. `unchanged` means identical bytes and mode 600 were preserved without replacing the inode. A changed write must use temp+fsync+atomic replace; any verification failure restores the captured before bytes/mode and independently rereads them before reporting failure.
5. Open the dynamic output path, never a hard-coded Desktop path. Verify it is a regular non-symlink file with mode `600`, contains exactly one SOCKS5 proxy definition, and contains every required routing anchor. Print only byte count and SHA-256:

```bash
python3 - <<'PY'
import hashlib
import os
from pathlib import Path

p = Path(os.environ["SUBMISSION_SHARED_DIR"]) / "socks5.yml"
assert p.is_file() and not p.is_symlink(), p
assert p.stat().st_mode & 0o777 == 0o600
text = p.read_text(encoding="utf-8")
assert text.count('name: "My-SOCKS5-Proxy"') == 1
for needle in (
    "mode: rule", "type: socks5", "server:", "port:", "username:",
    "password:", "DOMAIN-SUFFIX,apple.com,PROXY", "- MATCH,PROXY",
):
    assert needle in text, needle
raw = text.encode("utf-8")
print(f"SOCKS5_BYTES={len(raw)}")
print(f"SOCKS5_SHA256={hashlib.sha256(raw).hexdigest()}")
PY
```

6. The writer re-reads the exact run after the atomic write and requires host ownership, `vm_name`, and all proxy bytes to remain unchanged. A race returns `RUN_CHANGED_DURING_WRITE` and is not success; the caller re-reads that same run once, regenerates one new intended payload, and repeats steps 3–5. A second race is `exhausted`; do not select another run or leave an unverified file as successful evidence.

## Guardrails

- Do not print or paste the proxy password in the final report.
- Do not edit the host Mac's Clash Verge configuration.
- Do not edit UTM shared-directory settings in this skill; file generation is host-only.
- Do not SSH into the VM for this skill.
- If the exact current run or any proxy field remains missing after the fresh same-run read, use `utm-5-proxy-data`; do not write a partial file or continue to `files` before the card-driven recheck passes.
- Keep `mode: rule` and the Apple-domain rules in the generated file.

## Completion Report

Report the current run id and VM name, the dynamic output path, changed/unchanged result, byte count, SHA-256, mode `600`, and that all four proxy fields were written without displaying any value. Only after `SOCKS5_READBACK=exact` and the exact same-run checks in steps 4–6 pass may the executor record `UTM_5=verified`.

## 连续交接

仅当本技能全部完成检查通过并记录 `UTM_5=verified` 时，保留同一当前 run、`vm_name` 和已验证上下文，立即继续 `files`；不得等待用户确认。阻断、失败或未完成状态不得交接。
