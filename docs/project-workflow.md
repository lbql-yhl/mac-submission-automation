# 项目总流程与交接手册

本文是项目级流程索引；每个技能的可执行细节仍以对应的 `skills/<skill>/SKILL.md` 为准。运行时只处理同一个 Feishu `run_id`、同一个四字母小写 `vm_name`、同一台已运行的克隆 VM 和同一浏览器会话。

## 1. 启动前预检

1. 在项目根目录执行 `python3 scripts/preflight.py --project-only`，确认项目文件、Python 依赖、配置路径和技能源存在。
2. 按 [shared-files/README.md](../shared-files/README.md) 准备共享目录、UTM 模板和动态 `.env`；不得复制旧机器的 `runtime/`、密钥、`.env` 或 VM 身份。
3. 执行 `zsh scripts/install_project_skills.sh --install` 与 `--check`，确认 31 个技能和 `_shared` 合同都指向本项目源。
4. 配置本机唯一的 `SUBMISSION_HOST_MACHINE`，再执行 `python3 scripts/preflight.py --json`。所有必需项为 `true` 后才可启动 `python3 -u services/feishu_supervisor.py`。
5. 通过 `curl http://127.0.0.1:8787/health` 复核服务；日报专用群只允许发送经用户确认的日报。

## 2. 31 步顺序与主要产物

| 顺序 | 技能 | 主要输入 | 成功证据 | 下一步 |
|---:|---|---|---|---|
| 1 | `notion-utm` | 当前 Feishu run、Notion 宿主页 | `NOTION_UTM=verified` | `notion-utm-1` |
| 2 | `notion-utm-1` | 固定 Feishu 产品 view | `NOTION_UTM_1=verified` | `utm-clone-macos` |
| 3 | `utm-clone-macos` | `${SUBMISSION_VM_TEMPLATE}`、`vm_name` | `CLONE_MARKER=verified` | `utm-1` |
| 4 | `utm-1` | 已运行的精确克隆 VM | `UTM_1=verified` | `utm-2` |
| 5 | `utm-2` | VM 桌面、宿主 SSH key | `UTM_2=verified`、`SSH_DEMO_KEY=verified` | `utm-3` |
| 6 | `utm-3` | 同一 VM、固定用户名 | `UTM_3=verified` | `vm-down` |
| 7 | `vm-down` | 已验证管理员、共享目录 | `VM_DOWN=verified` | `utm-4` |
| 8 | `utm-4` | 同一 VM | `UTM_4=verified` | `utm-5` |
| 9 | `utm-5` | 当前 run 代理字段 | `UTM_5=verified` | `files` |
| 10 | `files` | guest 共享挂载 | `FILES=verified` | `utm-clash` |
| 11 | `utm-clash` | guest `Downloads/socks5.yml` | `UTM_CLASH=verified` | `utm-6` |
| 12 | `utm-6` | 代理出口、guest shell | `UTM_6=verified` | `utm-7` |
| 13 | `utm-7` | Notion Apple 账号字段 | `UTM_7=verified` | `utm-8` |
| 14 | `utm-8` | Apple 个人信息页 | `UTM_8=verified` | `utm-9` |
| 15 | `utm-9` | Notion 邮箱、Keychain Access | `UTM_9=verified` | `utm-10` |
| 16 | `utm-10` | 同一 guest Edge | `UTM_10=verified` | `utm-11` |
| 17 | `utm-11` | Small Business 页面 | `UTM_11=verified` | `utm-12` |
| 18 | `utm-12` | Membership、App ID | `UTM_12=verified` | `utm-13` |
| 19 | `utm-13` | Certificates/Profiles | `UTM_13=verified` | `utm-14` |
| 20 | `utm-14` | Business、税务表单 | `UTM_14=verified`、`DAC7_INFO=No_saved` | `utm-15` |
| 21 | `utm-15` | App Store Connect Apps | `UTM_15=verified` | `utm-16` |
| 22 | `utm-16` | Notion 账号/应用区块 | `UTM_16=verified` | `utm-17` |
| 23 | `utm-17` | Notion 两个素材链接 | `UTM_17=verified` | `utm-18` |
| 24 | `utm-18` | guest Edge/CDP、代码项目 | `UTM_18=verified` | `utm-19` |
| 25 | `utm-19` | 截图 ZIP、Media Manager | `UTM_19=verified` | `utm-20` |
| 26 | `utm-20` | Business 银行页、Notion 银行字段 | `UTM_20=verified` | `utm-21` |
| 27 | `utm-21` | Codeup、`.env`、Flutter 项目 | `UTM_21=verified` | `utm-22` |
| 28 | `utm-22` | Xcode、Build 上传 | `UTM_22=verified` | `utm-23` |
| 29 | `utm-23` | App Version、IAP、App Information | `UTM_23=verified` | `utm-24` |
| 30 | `utm-24` | 五图、版本/构建、范围自检 | `UTM_24=verified`、自动授权 | `utm-25` |
| 31 | `utm-25` | 唯一 Active Key 与 P8 | `UTM_25=verified`、成功卡最多一张 | 结束 |

## 3. 每一步的通用执行模板

1. 从上一技能继承 run、`vm_name`、VM/IP、SSH 身份、浏览器和工作目录；只做一次轻量存活/身份检查。
2. 读取本技能“输入来源”，锁定精确对象；禁止按“最新”重新选择 VM、run、页面或文件。
3. 执行“精确动作”。每个 GUI 动作后至少等待 3 秒，读取最新截图/状态，再进行下一动作。
4. 执行“动作后复验”：回读页面、文件、哈希、权限、退出码或状态标记；敏感值只在安全临时文件或 stdin 内存通道中流转。
5. 记录技能成功标记后立即按“连续交接”进入下一技能；正常主线不等待用户确认。

## 4. 故障与安全边界

- 先暂停新的副作用。可逆故障按共享合同完成三轮“自动诊断 → 实际修复 → 独立复验”；不可逆或外部状态做三轮独立只读复核。
- 只有恢复穷尽后才允许 `notify-fault`；故障卡必须带真实 `recovery_attempts>=3`、动作和 `exhausted|unrepairable` 证据。
- 不启动、打开、重启或切换克隆 VM；`utm-1` 只接管开始前已经运行的精确 VM。浏览器只复用已有宿主 Chrome，`utm-18` 才允许重启同一 guest Edge。
- Notion 只用 `scripts/notion_api.py`；Feishu 数据只来自 bot API/runtime；不把 `.env`、密码、P8、验证码或代理密钥放入日志、argv、剪贴板或公开文档。
- `utm-24` 通过自动自检授权后只提交一次；`utm-25` 只在 Notion P8 独立回读成功后发送绿色成功卡。

## 5. 交接检查

```bash
python3 tests/test_detailed_skill_contract.py
python3 scripts/preflight.py --project-only
git ls-tree -r --name-only origin/main skills | rg '/SKILL\\.md$' | wc -l  # 应为 31
```

交接记录必须同时包含当前 `run_id`、`vm_name`、本技能成功标记、关键哈希/截图证据和下一技能名称；缺任何一项都不得继续。
