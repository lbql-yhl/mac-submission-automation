# UTM-13：证书与 App Store Provisioning Profile

## 定位

`utm-13` 接在 `utm-12` 后，继续使用同一台 UTM guest 和同一个 Microsoft Edge，完成 Certificates 页面、Apple Distribution 证书导入，以及 App Store Connect Provisioning Profile 生成。`utm-12` 仍在验证 `iOS App Version 1.0` 后结束。

## 操作 Checklist

### 1. Certificates 页面

- [ ] 切换已有 `Certificates, Identifiers & Profiles` 标签页。
- [ ] 确认 Apple Developer 账户、Team ID 和 `developer.apple.com/account/resources/` URL 正确。
- [ ] 点击左侧 `Certificates`。
- [ ] 确认 `developer.apple.com/account/resources/certificates/list` 和页面标题 `Certificates`。

### 2. Apple Distribution 证书

- [ ] 没有可用 Distribution 证书时点击 `Create a certificate`。
- [ ] 勾选 `Apple Distribution`，确认后点击 `Continue`。
- [ ] `Choose File` → guest Desktop → `CertificateSigningRequest.certSigningRequest` → `Open`。
- [ ] 确认 CSR 文件名后点击 `Continue`，再点击 `Download` 下载 `distribution.cer`。
- [ ] 打开 `distribution.cer`，在 `Add Certificates` 中将钥匙串切到 `System`。
- [ ] 切换 System 的稳定方法：下拉框打开后 `Down` 两次，等待 3 秒确认 `System` 高亮，再按 `Return`；不要直接点击嵌套菜单中的 System。
- [ ] 点击 `Add`；Keychain 授权提示确认归属后调用 `OP-FIXED-PASSWORD-1234`。未知或归属不明时重读进程、窗口、证书动作三轮，仍不明确才发最后故障卡。
- [ ] 在 Keychain Access 的 `System` 中确认当前 Team 的 `Apple Distribution` 证书行存在。

### 3. Profiles 与类型

- [ ] 返回 Edge，点击 `All Certificates`，确认回到 Certificates 列表。
- [ ] 点击 `Profiles` → `Generate a profile`。
- [ ] 在 `Distribution` 中勾选 `App Store Connect`。
- [ ] 重新截图确认单选框已选中，再点击右上角 `Continue`。

### 4. App ID 与 Distribution 证书

- [ ] 在 `Select an App ID` 中打开下拉框，选择当前应用唯一 App ID。
- [ ] 确认 App ID 字段正确、Continue 变蓝后点击 Continue。
- [ ] 在 `Select Certificates` 中选择当前 Team 的 Distribution 证书。
- [ ] 确认单选框和 Continue 状态后点击 Continue。

### 5. 命名、生成与下载

- [ ] 在项目根目录执行 `python3 scripts/notion_api.py verify-parent --title '<宿主机名称>'`。
- [ ] 紧接粘贴前执行 `python3 scripts/notion_api.py read-field --title '<应用名>-<vm_name>' --heading '应用信息' --label '应用名: ' --copy`；要求父页面、页面、heading、code block 和字段都唯一，且安全元数据表明值非空。
- [ ] 不用宿主浏览器或插件读取 Notion；在 `Review, Name and Generate` 的 `Provisioning Profile Name` 中粘贴 API 读取的应用名。
- [ ] 所有字段完整调用 `OP-NATIVE-PASTE`；随机哨兵与来源 hash 通过后，输入框右键菜单中 `Paste` 必须在新截图里蓝色高亮，禁止手动输入或未验证快捷键。
- [ ] 确认字段完整、大小写正确且 `Generate` 为蓝色，点击 `Generate`。
- [ ] 等待 `Processing` 完成。
- [ ] 在 `Download and Install` 页面确认 Name、Type `App Store`、App ID、到期日和 `Download` 按钮。

## 完成标准

```text
UTM_13=verified
CERTIFICATES_PAGE=opened
APPLE_DISTRIBUTION_CERT=installed
PROVISIONING_PROFILE=generated
PROVISIONING_PROFILE_DOWNLOAD=ready
```

## 风险点

- 每个 GUI 动作后至少等待 3 秒并读取最新截图；页面变化后重新定位坐标。
- 不启动新的浏览器进程，不切换到宿主机浏览器。
- `System` 直接坐标点击可能回退到 `login`，必须用“Down 两次 + 高亮确认 + Return”。
- 证书导入只以 Keychain Access 的 `System` 证书行作为成功依据；红色不受信任文字不等于证书未导入。
- Profile 名称若出现多余字符，先全选并用右键 `Paste` 替换，确认完全等于应用名后再 Generate。
- 页面、账户、CSR、App ID 或 Distribution 证书不匹配时回到最近验证锚点并重读权威来源三轮；仍冲突才发最后故障卡，不猜测或改选对象。
