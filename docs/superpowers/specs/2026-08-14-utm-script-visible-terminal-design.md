# utm-script 可见终端与长耗时执行设计

## 目标

`utm-script` 仍只由 `scripts/utm_18.py` 唯一宿主入口启动，但实际执行改为在已绑定 UTM macOS 客户机中打开可见 Terminal，并执行：

```bash
cd Downloads/Fire_One_en1.3 && npm run fill:description
```

正常耗时约 30–40 分钟，宿主最长等待 60 分钟。不修改 `Fire_One_en1.3` 目录中任何文件。

## 启动方式

1. 现有 attempt 预提交阶段在客户机 `Downloads` 中创建 attempt 专属 `.command`、日志和状态文件；`.command` 不位于 `Fire_One_en1.3` 内。
2. 宿主只发出一次密码 SSH 启动命令：由 macOS `open -a Terminal <attempt.command>` 打开可见 Terminal。不使用键鼠点击，不依赖 AppleScript 自动化授权。
3. `.command` 进入客户机用户主目录后执行上述命令，同时用 `tee` 保留可见输出和 attempt 日志，记录 npm/tee 退出码。
4. 命令完成后留在可见登录 shell，不关闭 Terminal。

## 等待、错误和验证

- 启动后每 5 秒读取一次同一 attempt 的状态、日志和进程，最多 60 分钟。
- 发现明确业务错误、npm 非零退出或 Terminal 命令提前结束时，不再等待，立即停止该技能并输出真实错误。
- 60 分钟内未得到结果则返回明确超时错误，不启动后续技能。
- 仅当日志包含唯一 `增强版内购创建完成！`、唯一 `统计信息: 共处理 N 个产品` 且 `N>=1`，并且 npm/tee 退出码均为 0 时成功。

## 不可变边界

- SSH 仍只使用固定密码 `1234`，不创建 SSH key。
- 不修改、覆盖、删除或格式化 `Fire_One_en1.3` 中的任何源码、配置或资产。
- 不使用视觉、键鼠坐标或关闭浏览器进程。
- 实机测试也只通过 `utm-script` 唯一宿主入口进行。
