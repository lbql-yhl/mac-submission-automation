# utm-script Visible Terminal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `utm-script` 通过唯一宿主入口在 UTM 客户机的可见 Terminal 中执行 `cd Downloads/Fire_One_en1.3 && npm run fill:description`，并在 60 分钟内立即识别成功或失败。

**Architecture:** attempt 预提交额外创建一个不位于 Fire_One 目录内的 `.command` 启动器；SSH 只调用一次 `open -a Terminal`。客户机 Terminal 写入 attempt 日志/状态，宿主每 5 秒读取证据，最长 3600 秒。

**Tech Stack:** Python 3.12, zsh, macOS Terminal/open, password SSH, pytest.

---

### Task 1: 锁定可见 Terminal 启动合同

**Files:**
- Modify: `tests/test_utm_18_attempt.py`
- Modify: `tests/test_utm_18_skill.py`

- [ ] **Step 1: Write the failing tests**

断言 attempt 启动器位于 guest `Downloads`、包含精确 `cd Downloads/Fire_One_en1.3 && npm run fill:description`、SSH 只执行 `open -a Terminal <attempt.command>`，且实现文本不包含对 `Fire_One_en1.3` 的写文件命令。

- [ ] **Step 2: Run tests and verify RED**

```bash
python3 -m pytest tests/test_utm_18_attempt.py tests/test_utm_18_skill.py -q
```

Expected: FAIL because the current implementation runs npm inside hidden SSH and the old contract forbids Terminal launch.

- [ ] **Step 3: Implement the minimal launcher**

In `scripts/utm_18_attempt.py`, derive an attempt-specific `.command` path, create it during `precommit_remote()`, and change `run_remote()` to one password-SSH invocation whose guest action is `open -a Terminal <attempt.command>`.

- [ ] **Step 4: Run tests and verify GREEN**

```bash
python3 -m pytest tests/test_utm_18_attempt.py tests/test_utm_18_skill.py -q
```

Expected: PASS.

### Task 2: 加入 60 分钟条件等待和立即失败

**Files:**
- Modify: `tests/test_utm_18.py`
- Modify: `scripts/utm_18.py`

- [ ] **Step 1: Write the failing tests**

覆盖 `launching -> running -> exited_zero`、运行中业务错误立即返回、npm 非零退出立即返回，以及 720 次 5 秒读取后返回 `FILL_DESCRIPTION_TIMEOUT_SECONDS=3600`。

- [ ] **Step 2: Run tests and verify RED**

```bash
python3 -m pytest tests/test_utm_18.py -q -k 'terminal or timeout or incomplete'
```

Expected: FAIL because the current incomplete-process polling is only 600 seconds and cannot handle the launch race.

- [ ] **Step 3: Implement the minimal wait loop**

Update `_classify_with_resident_rechecks()` to poll the same attempt every 5 seconds while its state is `launching` or `running`, stop immediately on a classified error/finished state, and return an explicit 3600-second timeout result after 720 polls.

- [ ] **Step 4: Run tests and verify GREEN**

```bash
python3 -m pytest tests/test_utm_18.py -q
```

Expected: PASS.

### Task 3: 合同验证与实机复验

**Files:**
- Modify if required: `skills/utm-script/SKILL.md`
- Modify if required: `docs/utm-script.md`

- [ ] **Step 1: Run focused and project contract tests**

```bash
python3 -m pytest tests/test_utm_18.py tests/test_utm_18_attempt.py tests/test_utm_18_ssh.py tests/test_utm_18_skill.py -q
python3 tests/test_detailed_skill_contract.py
/bin/zsh scripts/install_project_skills.sh --check
```

Expected: all pass.

- [ ] **Step 2: Run the only real guest entry**

```bash
python3 /Users/yehailin/Documents/mac提审自动化/scripts/utm_18.py \
  --page-title 'PanSwap-CakeBaking-stgf' \
  --vm-name 'stgf' --vm-ip '192.168.64.56' --vm-user 'stgf'
```

Expected: guest Terminal opens visibly, the exact command runs, and the entry returns `执行成功：utm-script；UTM_18=verified` within 60 minutes; any actual error returns immediately and blocks later skills.
