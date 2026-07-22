# Fire_One_en1.2

这是 `utm-18` 在 UTM guest 中调用的 App Store Connect 自动化源码。它复用已经登录并开启 CDP 的 Microsoft Edge，执行当前技能合同规定的页面填写和内购创建流程。

## 运行边界

- 唯一业务入口是 `npm run fill:description`。
- 该入口会产生真实 App Store Connect 副作用，不提供 dry-run；不要把命令当测试手动执行。
- 正常流程只能由项目 `skills/utm-18/SKILL.md` 的 attempt ledger、前台 SSH、完整日志和状态复验门禁调用。
- `.env` 由 `utm-16` 从当前匹配的 Notion 页面生成，不能提交到 Git，也不能用示例值替代生产数据。
- P8、`prod.yml`、账号、联系人、代理和 token 都是本机运行数据，不属于源码。

## 目录

- `src/fill-description.ts`：TypeScript 业务入口。
- `.env.example`：无凭据字段清单。
- `package.json` / `package-lock.json`：Node.js 依赖与锁文件。
- `tsconfig.json`：TypeScript 配置。

## 安装依赖

恢复到 `${SUBMISSION_SHARED_DIR}/Fire_One_en1.2` 后执行：

```bash
npm ci
```

运行前仍须由 `utm-18` 验证 Node/npm、`.env`、固定 CDP 地址、Edge 登录状态和唯一 attempt；不要绕过技能正文直接运行。
