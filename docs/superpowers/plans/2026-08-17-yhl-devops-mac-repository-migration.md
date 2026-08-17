# yhl-devops-mac Repository Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `lbql-yhl/yhl-devops-mac` as a private GitHub repository and preserve the current project source, skills, scripts, documentation, tests, tools, shared desktop files, branches, and history without uploading unapproved credentials or machine/runtime data. The source-embedded fixed VM password and Feishu/Notion resource identifiers are explicitly approved for this private backup.

**Architecture:** Create a dedicated local snapshot branch, stage the current filesystem state under hardened ignore rules, and commit one auditable snapshot. Keep the existing `origin` unchanged, add the private repository as `yhl-devops`, publish the snapshot as the new repository's `main`, and preserve the existing local branch tips as archive branches.

**Tech Stack:** Git, GitHub CLI, GitHub private repositories

---

### Task 1: Harden the upload boundary

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add local diagnostics and VM image artifact rules**

Add rules for `.codex_diag/` and VM disks/images/snapshots while retaining automation source, documentation, skills, tests, tools, application artifacts, and `shared-files/` project assets.

- [ ] **Step 2: Verify ignored local data**

Run: `git status --short --ignored`

Expected: `.env`, `runtime/`, caches, `.codex_diag/`, signing material, and VM images are ignored.

### Task 2: Create an auditable project snapshot

**Files:**
- Modify: all current tracked project files
- Create: all current untracked project source, skills, scripts, documentation, tests, and shared project assets

- [ ] **Step 1: Create a dedicated snapshot branch**

Run: `git switch -c codex/yhl-devops-snapshot`

Expected: the active branch is `codex/yhl-devops-snapshot` and the dirty working tree is preserved.

- [ ] **Step 2: Stage the current project state**

Run: `git add -A`

Expected: project source and assets are staged; `.env`, tokens, signing material, runtime data, Notion-derived VM/App records, caches, and VM images remain unstaged. The explicitly approved source-embedded fixed VM password and Feishu/Notion resource identifiers remain part of the source snapshot.

- [ ] **Step 3: Validate the staged snapshot**

Run: `git diff --cached --check && git diff --cached --stat`

Expected: no whitespace errors and no forbidden local/runtime artifacts.

- [ ] **Step 4: Commit the snapshot**

Run: `git commit -m "chore: snapshot complete project for private repository"`

Expected: one commit containing the current project snapshot.

### Task 3: Create and publish the private repository

**Files:**
- Modify: local Git remote configuration

- [ ] **Step 1: Create the private GitHub repository**

Run: `gh repo create lbql-yhl/yhl-devops-mac --private --description "Mac submission automation project"`

Expected: GitHub creates `lbql-yhl/yhl-devops-mac` with private visibility.

- [ ] **Step 2: Add a dedicated remote without replacing the old origin**

Run: `git remote add yhl-devops https://github.com/lbql-yhl/yhl-devops-mac.git`

Expected: the old `origin` remains unchanged and `yhl-devops` points to the new private repository.

- [ ] **Step 3: Push the current snapshot and preserve branch tips**

Run the explicit refspec push for the snapshot as `main`, the snapshot branch, and archive copies of the existing local branch tips; then push all tags.

Expected: the new repository contains the current snapshot on `main`, the full Git history, preserved branch tips, and all tags.

### Task 4: Verify the remote backup

**Files:**
- Verify only

- [ ] **Step 1: Verify repository settings**

Run: `gh repo view lbql-yhl/yhl-devops-mac --json nameWithOwner,visibility,url,defaultBranchRef`

Expected: visibility is `PRIVATE` and default branch is `main`.

- [ ] **Step 2: Verify remote refs and snapshot identity**

Run: `git ls-remote --heads --tags yhl-devops`

Expected: remote `main` resolves to the local snapshot commit and the preserved branches are present.

- [ ] **Step 3: Verify a clean post-commit working tree**

Run: `git status --short --branch`

Expected: no project files remain uncommitted.
