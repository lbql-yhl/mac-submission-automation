# 项目总流程

每段可单独运行，每个技能可人工单独指定执行。具体命令只查看项目内 `skills/<skill>/SKILL.md`，不读取或解释脚本内容。

## 四段顺序

1. 虚拟机准备：utm-vm-clone
2. 环境准备：utm-notion → utm-clash-ip → utm-login → utm-edit → utm-key → utm-apps → utm-business
3. 脚本准备、执行：utm-env → utm-script → utm-image → utm-p8
4. 代码处理：utm-21 → utm-22 → utm-23 → utm-24

段内成功后交接下一技能。段尾可以结束；需要继续时交接下一段入口：

- 虚拟机准备结束后：`utm-notion`
- 环境准备结束后：`utm-env`
- 脚本准备、执行结束后：`utm-21`
- 代码处理结束后：主线结束

`utm-vm-clone` 由独立工作维护；`utm-21`～`utm-24` 当前可正常使用，其专属文档保持现状。

## 执行规则

- 只运行技能文档中的唯一宿主入口。
- 人工单独执行传入技能文档要求的精确参数。
- 失败修复后重新运行同一入口，不直接运行中间步骤。
- 连续交接保持同一 run、应用、VM、IP、SSH 身份、浏览器会话和工作目录。
- 终端只输出开始、成功或非敏感报错。

## 验收

```bash
python3 /Users/yehailin/Documents/mac提审自动化/tests/test_detailed_skill_contract.py
/bin/zsh /Users/yehailin/Documents/mac提审自动化/scripts/install_project_skills.sh --check
```
