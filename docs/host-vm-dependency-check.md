# 宿主机与 UTM 虚拟机依赖检查

## 用途

在宿主 macOS 上执行一个检查脚本，同时确认宿主机和指定 UTM macOS 虚拟机的项目依赖是否已经安装。

检查脚本只读取当前环境并输出检查结果，不会安装依赖，也不会启动、停止、重启或切换虚拟机。

## 执行脚本

唯一检查脚本：

```text
/Users/yehailin/Documents/mac提审自动化/scripts/check_host_vm_dependencies.py
```

使用宿主机的公共 Python 虚拟环境执行：

```text
/Users/yehailin/.venvs/py312-common/bin/python3
```

## 执行前提

执行前需要满足以下条件：

1. 命令必须在宿主机终端执行，不能在虚拟机内执行。
2. 待检查的虚拟机必须已经运行；检查脚本不会替你启动虚拟机。
3. 虚拟机名称必须是四位小写英文字母，例如 `stgf`。
4. 虚拟机必须已经登记在项目的 VM inventory 中，而且登记的 bundle、UUID、MAC 地址和当前虚拟机一致。
5. 虚拟机需要能够通过项目固定账号和 SSH 配置连接。

## 通用执行命令

把 `<四位小写虚拟机名>` 替换成实际虚拟机名称：

```zsh
/Users/yehailin/.venvs/py312-common/bin/python3 \
  /Users/yehailin/Documents/mac提审自动化/scripts/check_host_vm_dependencies.py \
  --vm-name '<四位小写虚拟机名>'
```

例如，检查虚拟机 `stgf`：

```zsh
/Users/yehailin/.venvs/py312-common/bin/python3 \
  /Users/yehailin/Documents/mac提审自动化/scripts/check_host_vm_dependencies.py \
  --vm-name stgf
```

`utm-vm-clone` 内部步骤 7 使用同一脚本的 `--active-clone` 只读模式。该模式只接受当前活动克隆，并额外精确核对活动记录、步骤 2 至 6 状态、SQLite bundle/UUID、实时 config MAC；普通人工检查不使用此参数。

## 输出格式

脚本固定检查 26 项。每一行只会使用以下两种格式之一：

```text
检查项已安装
检查项未安装
```

例如：

```text
宿主Python已安装
虚拟机Xcode未安装
```

## 如何确认全部安装成功

同时满足以下两个条件才算完整成功：

1. 输出正好包含 26 个检查项。
2. 26 行全部以 `已安装` 结尾，没有任何一行以 `未安装` 结尾。

完整成功时的输出如下：

```text
宿主Python已安装
宿主Node.js已安装
宿主npm已安装
宿主Git已安装
宿主SSH已安装
宿主UTM已安装
宿主Swift已安装
宿主Pillow已安装
宿主PyObjC已安装
宿主飞书SDK已安装
宿主Playwright已安装
虚拟机连接已安装
虚拟机Python已安装
虚拟机Node.js已安装
虚拟机npm已安装
虚拟机Git已安装
虚拟机Microsoft Edge已安装
虚拟机Clash Verge已安装
虚拟机Xcode已安装
虚拟机PyObjC已安装
虚拟机Playwright已安装
虚拟机Fire One已安装
虚拟机证书工具已安装
虚拟机签名工具已安装
虚拟机打包工具已安装
虚拟机App Store工具已安装
```

不要只根据命令退出状态判断是否成功，应以这 26 行的实际内容为准。

## 出现“未安装”时

- 某个宿主机检查项显示 `未安装`：表示运行该命令所使用的宿主环境没有通过对应检查。
- `虚拟机连接已安装`，但某个虚拟机检查项显示 `未安装`：表示虚拟机已经连接成功，但该项没有通过检查。
- `虚拟机连接未安装`：表示脚本没有完成对这台精确虚拟机的身份、运行状态、IP 或 SSH 连接检查。此时后续虚拟机项目会连带显示 `未安装`，不能直接认定这些依赖在虚拟机中确实缺失。

问题处理完成后，重新执行同一条宿主机命令，直到 26 项全部显示 `已安装`。
