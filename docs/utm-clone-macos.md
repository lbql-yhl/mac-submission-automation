# utm-clone-macos：无视觉外接盘克隆

## 输入

从当前 run 继承四位小写 `vm_name` 和 `run_id`，从 `preflight.py` 读取 `${SUBMISSION_VM_TEMPLATE}` 与 `${SUBMISSION_VM_IMAGES_DIR}`。目标只能是 `${SUBMISSION_VM_IMAGES_DIR}/<vm_name>.utm`；模板与目标均不可为符号链接。

## 执行

1. 两次读取 `utmctl list`，要求模板为 `stopped`。
2. 在目标包中原子建立 mode `600` 的当前 run marker，再以 `ditto` 复制完整 `.utm` 包。
3. 原子改写目标 `config.plist` 的名称、UUID、MAC 和 Apple MachineIdentifier/ECID；保留 HardwareModel，保存 before bytes 并回读。
4. 通过递归 SHA-256 manifest 证明除 config 与 marker 外包内容一致。
5. 用 `utmctl list` 与 `defaults read com.utmapp.UTM Registry` 按目标 UUID、名称、规范 bundle 路径和 stopped 状态回读注册。仅零条时才允许一次 `open "$dst"` 系统注册调用。

## 成功证据

```text
CLONE_MARKER=verified
CLONE_CONFIG_IDENTITY=verified
UTM_REGISTRATION_MATCH_COUNT=1
UTM_REGISTRATION_STATE=stopped
UTM_CLONE_MACOS=verified
```

guest 三码不在此阶段读取；由 `utm-2` 通过 SSH 与模板基线比较。所有操作均使用命令、UTM CLI/Registry 与文件回读，不以屏幕内容判断。

## 恢复边界

模板、目标卷、marker、manifest 或 Registry 不一致时，对同一模板/目标/attempt 做三轮独立只读复核。归属不明、路径冲突或身份冲突不得覆盖、删除或改名，按技能最后故障卡规则停止。
