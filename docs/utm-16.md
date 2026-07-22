# UTM-16：生成并 SSH 写入提审环境文件

## 定位

`utm-16` 接在 `utm-15` 后。它只通过 `scripts/notion_api.py` 读取匹配 `<应用名>-<vm_name>` 的 `账号信息` 和 `应用信息`；字段校验通过后，立即由宿主脚本原子生成共享目录 `.env`，再通过 SSH 在匹配 guest 内执行带 before/rollback 的原子替换并验证。全流程自动执行，不设置用户审核或确认节点。

Notion 阶段只发 GET 请求，不修改 Notion，不使用 Chrome、Notion 插件、Playwright、CUA、坐标、DOM 或浏览器剪贴板读写 Notion，不把脚本文本输入 guest Terminal，不运行提审或发布命令。

SSH 直接继承 `utm-15` 已验证的同一 VM、IP、用户和宿主公钥认证。所有连接固定使用 `BatchMode=yes`；如果连接失效，只对该精确 VM 自动刷新 IP、修复 Remote Login 并恢复 `${SUBMISSION_SSH_PUBLIC_KEY}`，不得向用户索取密码、SSH Key、IP 或等待 SSH 人工恢复。

## 固定路径

```text
宿主输出：${SUBMISSION_SHARED_DIR}/.env
guest 共享源：/Volumes/My Shared Files/共享文件/.env
guest 目标：/Users/<vm_name>/Downloads/Fire_One_en1.2/.env
```

文件名必须始终是 `.env`，禁止追加 VM 名。

## 操作步骤

1. 从当前运行上下文取得唯一 `<宿主机名称>` 与 `<应用名>-<vm_name>`，先验证 API 根页面：

   ```bash
   python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'
   ```

2. `verify-parent` 成功后运行固定宿主生成器。它会再次校验父页面，只通过 Notion API GET 读取唯一页面中 heading 后紧邻的 `账号信息` 和 `应用信息` code block；不打印区块内容，不把字段放进命令参数：

   ```bash
   python3 -m scripts.utm_16_generate_env \
     --parent-title '<宿主机名称>' \
     --page-title '<应用名>-<vm_name>'
   ```

3. 生成器精确读取账号标签 `用户名：`、`邮箱：`、`电话：`、`APP_ID：`，以及应用标签 `应用名: `、`顶级域名: `、`正式包名: `、`隐私协议: `、`用户协议: `、`支持链接: `、`应用类型：`、`应用描述：`、`关键词: `；所有匹配必须唯一。描述读取到 `关键词: ` 之前，真实换行写入 `.env` 时转换为字面量 `\n`。
4. 校验 `APP_ID`、四位小写 `VM_NAME`、联系人姓名、正式包名、顶级域名、描述、关键词和三个 URL；`PRIMARY_CATEGORY` 必须按下表转换或保持已规范化枚举。成功后记录 `NOTION_SOURCE=api_unique_matched_and_read` 和 `ENV_DATA=validated`。
5. 生成器必须以 mode-600 同目录临时文件写入、`fsync`、`os.replace` 并同步目录；未变化时保持 inode。重新读取宿主 `.env`，验证字段唯一、类别、禁止字段、权限、字节数/行数/SHA-256，记录 `ENV_WRITE=changed|unchanged` 与 `ENV_READBACK=exact`；写后失败则恢复旧字节/权限并独立回读。
6. 直接继承 `utm-15` 的当前 VM/IP/SSH 身份，先验证 `${SUBMISSION_SSH_PRIVATE_KEY}` 为非符号链接普通文件并记录 `SSH_PRIVATE_KEY=verified`；每条 SSH 都显式带 `-i "$private_key" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=5`。只有继承 IP 不可达时才恢复同一精确 VM。
7. 确认 guest 共享源可读、目标目录存在，并记录覆盖前源/目标状态。
8. 从宿主通过 SSH 执行匹配技能正文的固定原子替换：拒绝 symlink/非普通目标；旧目标先复制到同目录随机 before；新内容写入 mode-600 临时文件并 `cmp` 后原子 `mv`。提交后内容或权限不符时立即用 before 原子还原并回读，记录 `GUEST_ENV_ROLLBACK=verified` 后失败退出；只有新目标与源一致且 mode 600 才记录 `GUEST_ENV_WRITE=atomic_verified`。
9. 使用新的、仍显式带同一私钥的 SSH 连接验证 `cmp -s`、目标权限、必填/禁止字段和持久化状态；宿主、guest 共享源、guest 目标的 SHA-256 必须完全一致。
10. 自动检查全部通过后执行第二重只读检查，并自动核对完整输出：

   ```bash
   ssh -i "$private_key" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=5 \
     <vm_name>@<vm-ip> 'cat /Users/<vm_name>/Downloads/Fire_One_en1.2/.env'
   ```

   `cat` 输出含联系人信息，只用于当前检查，不转发到飞书、外部消息或长期日志。

## `PRIMARY_CATEGORY` 转换表

Notion `应用类型：` 保持原值交给 `scripts/utm_16_generate_env.py`。展示名由脚本统一转换；如果已经是下表右列枚举值，则原样保留：

| Notion 原值 | `.env` 枚举值 |
|---|---|
| `报刊杂志` | `MAGAZINES_AND_NEWSPAPERS` |
| `财务` | `FINANCE` |
| `参考资料` | `REFERENCE` |
| `导航` | `NAVIGATION` |
| `工具` | `UTILITIES` |
| `购物` | `SHOPPING` |
| `健康健美` | `HEALTH_AND_FITNESS` |
| `教育` | `EDUCATION` |
| `旅游` | `TRAVEL` |
| `美食佳饮` | `FOOD_AND_DRINK` |
| `软件开发工具` | `DEVELOPER_TOOLS` |
| `商务` | `BUSINESS` |
| `社交` | `SOCIAL_NETWORKING` |
| `摄影与录像` / `Photo & Video` | `PHOTO_AND_VIDEO` |
| `生活` | `LIFESTYLE` |
| `体育` | `SPORTS` |
| `天气` | `WEATHER` |
| `贴纸` | `STICKERS` |
| `图书` | `BOOKS` |
| `图形和设计` / `图形与设计` / `Graphics & Design` | `GRAPHICS_AND_DESIGN` |
| `效率` | `PRODUCTIVITY` |
| `新闻` | `NEWS` |
| `医疗` | `MEDICAL` |
| `音乐` | `MUSIC` |
| `游戏` | `GAMES` |
| `娱乐` | `ENTERTAINMENT` |

原值既不在映射左列、也不是右列枚举时重新验证父页、页面和字段三轮；仍未知才作为权威分类缺失发最后故障卡，不猜测、自行翻译或写入 `.env`。

## 完成检查

- [ ] `verify-parent` 已证明 `NOTION_ROOT_PAGE_ID` 与当前宿主机名称匹配。
- [ ] API 唯一匹配页面、账号块、应用块和 VM 名，全程未调用 Notion 写入。
- [ ] Notion 必填字段均唯一、映射正确并通过校验。
- [ ] `PRIMARY_CATEGORY` 已由 Notion 原值转换为固定枚举值；`Graphics & Design` 必须生成 `GRAPHICS_AND_DESIGN`。
- [ ] 宿主固定文件 `.env` 已生成，权限和哈希已验证。
- [ ] VM/IP/SSH 用户、共享源和目标目录已确认。
- [ ] SSH `cp` 已完成，目标权限为 `600`。
- [ ] 新 SSH 连接证明三端 SHA-256 一致。
- [ ] SSH `cat` 已显示完整 guest `.env`，自动核对无截断或错项。
- [ ] 未运行任何发布命令。

## 完成标记

```text
UTM_15=verified
NOTION_SOURCE=api_unique_matched_and_read
ENV_DATA=validated
HOST_ENV=GENERATED_AND_VERIFIED
SSH_KEY_AUTH=verified
SSH_PRIVATE_KEY=verified
ENV_WRITE=changed|unchanged
ENV_READBACK=exact
GUEST_ENV_WRITE=atomic_verified
UTM_ENV=SSH_COPIED
UTM_ENV=HASH_VERIFIED
UTM_ENV=PERSISTED
UTM_ENV=CAT_REVIEWED
PUBLISH_COMMAND=NOT_RUN
UTM_16=verified
```

全部完成标记均有当前证据后，立即继续 `utm-17`；不得等待用户确认。

## 阻塞条件

上述配置、Notion、文件、哈希、共享或复制异常都先执行对应矩阵：重载本机配置、三轮只读 API/SSH、同 run 文件再生成/再复制一次并独立比较。可逆写入失败用 before 恢复。恢复穷尽或权威配置缺失时才记录证据并发最后故障卡；不得回退浏览器、让用户修 SSH、改用 TextEdit 或运行发布命令。
