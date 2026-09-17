# 项目文档导航

本目录采用“逻辑分层、保持现有路径”的文档架构。不要把附件中的概念模型直接当成实现事实；当前实现的架构总览见 [`project-architecture.md`](project-architecture.md)。

## 推荐阅读路径

### 1. 先理解项目边界

1. 根目录 [`README.md`](../README.md)：快速入口、运行主线和关键红线。
2. [`AGENTS.md`](../AGENTS.md)：项目级不可违反的执行规则。
3. [`project-architecture.md`](project-architecture.md)：Agent、Skills、MCP 数量，当前单机架构，以及扩展到 10 台以上机器的方法。

### 2. 再理解一次提审如何运行

4. [`project-workflow.md`](project-workflow.md)：31 步固定顺序、每步输入、成功证据和交接。
5. [`feishu-host-routing.md`](feishu-host-routing.md)：多宿主机如何根据 `SUBMISSION_HOST_MACHINE` 接取任务。
6. [`utm-feishu-bot.md`](utm-feishu-bot.md)：飞书机器人入口、部署和故障通知约束。

### 3. 执行或修改单个步骤

7. `skills/_shared/AUTOMATION_CONTRACT.md`：共享重复动作、恢复门禁和交接合同。
8. `skills/<skill>/SKILL.md`：对应技能的唯一可执行正文。
9. `docs/utm-*.md`：对应技能的对外说明和验收口径。
10. `scripts/`：被技能调用的 API、SSH、状态、构建和文件辅助脚本。
11. `tests/`：技能合同、解析器、恢复、卡片和回归测试。

## 权威关系

```text
AGENTS.md
  ├─ 约束项目级硬规则
  ├─ skills/_shared/AUTOMATION_CONTRACT.md
  │    └─ 约束 31 个技能共同动作
  └─ skills/<skill>/SKILL.md
       └─ 约束单个技能的完整执行步骤

README.md / docs/*.md
  └─ 对外入口、架构、流程、部署和验收说明

scripts/ + tests/
  └─ 将上述合同落到实现与可重复验证
```

## 按职责查找

| 你要回答的问题 | 先看 |
|---|---|
| 这个项目到底是什么架构？ | `project-architecture.md` |
| 31 步按什么顺序跑？ | `project-workflow.md`、`services/feishu_bot.py` |
| 为什么这台机器接这个任务？ | `feishu-host-routing.md`、`AGENTS.md` |
| 飞书入口会不会后台启动 runner？ | `utm-feishu-bot.md`、`services/feishu_bot.py` |
| 某一步怎么做？ | 对应 `skills/<skill>/SKILL.md` |
| 遇到故障先做什么？ | `skills/_shared/AUTOMATION_CONTRACT.md` + 当前技能正文 |
| 能不能把故障卡发出去？ | `services/feishu_bot.py`、`docs/utm-feishu-bot.md`、相关测试 |
| 哪些文件不能进 Git？ | `README.md`、`shared-files/README.md`、`.gitignore` |

## 当前目录结构

```text
docs/
├── README.md
├── project-architecture.md
├── project-workflow.md
├── feishu-host-routing.md
├── utm-feishu-bot.md
└── utm-*.md
```

`utm-*.md` 与 `skills/*/SKILL.md` 暂不物理搬迁；它们被脚本、提示文件、测试和交接流程引用，保持现有路径更安全。后续如需分目录，应先建立兼容链接或批量更新引用，再移动文件。

