# 共享目录

共享目录保存技能脚本生成或同步的运行资产。具体操作只运行对应 `skills/<skill>/SKILL.md` 的唯一宿主入口，不在本文重复脚本内容。

## 规则

- 共享目录路径从当前宿主机 `.env` 解析。
- 不复制旧宿主机运行历史、凭据或第二份技能正文。
- 不手工修改由技能入口管理的运行资产。
- 迁移后先执行项目预检和技能安装检查。

```bash
/Users/yehailin/.venvs/py312-common/bin/python3 /Users/yehailin/Documents/mac提审自动化/scripts/preflight.py --project-only
/bin/zsh /Users/yehailin/Documents/mac提审自动化/scripts/install_project_skills.sh --check
```
