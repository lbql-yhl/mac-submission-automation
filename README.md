# mac 提审自动化

项目采用 16 个主线技能。项目内 `skills/` 是唯一技能源，Codex 技能目录只保留发现 symlink。

每段可单独运行，每个技能可人工单独指定执行。执行时打开对应 `skills/<skill>/SKILL.md`，只运行其中唯一宿主入口，不读取或解释脚本内容。

## 四段顺序

1. 虚拟机准备：utm-vm-clone
2. 环境准备：utm-notion → utm-clash-ip → utm-login → utm-edit → utm-key → utm-apps → utm-business
3. 脚本准备、执行：utm-env → utm-script → utm-image → utm-p8
4. 代码处理：utm-21 → utm-22 → utm-23 → utm-24

段内成功后按顺序交接；段尾可以结束，也可继续下一段。技能失败并修复后重新运行同一唯一入口。

## 文档索引

- 总流程：[project-workflow.md](docs/project-workflow.md)
- 飞书运行：[utm-feishu-bot.md](docs/utm-feishu-bot.md)
- 宿主路由：[feishu-host-routing.md](docs/feishu-host-routing.md)
- 每个技能：`skills/<skill>/SKILL.md`

`utm-vm-clone` 由独立工作维护；`utm-21`～`utm-24` 当前可正常使用，其专属文档保持现状。

## 安装与检查

```bash
/bin/zsh /Users/yehailin/Documents/mac提审自动化/scripts/install_project_skills.sh --install
/bin/zsh /Users/yehailin/Documents/mac提审自动化/scripts/install_project_skills.sh --check
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/preflight.py --project-only
```

## 启动

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 -u /Users/yehailin/Documents/mac提审自动化/services/feishu_supervisor.py
curl http://127.0.0.1:8787/health
```

飞书提审启动当前禁用；普通 Codex 对话和已有运行的状态能力保留。

## 配置

复制 `.env.example` 为 `.env`，填写当前宿主机的飞书、Notion、Codeup 与 UTM 路径配置。禁止复制旧宿主机运行历史、凭据或第二份技能正文。

## 输出

技能运行期间，Codex 用户可见消息与终端摘要均只允许以下三类输出，不得发送技能读取提示、规则说明、执行计划、内部检查、重试、步骤过程、等待提示或复述。用户明确要求耗时等附加结果时，只在最终成功或报错行追加。

```text
开始执行：<skill>
执行成功：<skill>；<marker>
执行报错：<skill>；<原因>
```
