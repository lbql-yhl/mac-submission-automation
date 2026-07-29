---
name: utm-clone-macos
description: Run the standalone UTM macOS clone script.
---

# UTM Clone macOS

## 运行

```bash
python3 "/Users/yehailin/Documents/mac提审自动化/scripts/utm_clone_macos.py"
```

只检查模板、不创建克隆：

```bash
python3 "/Users/yehailin/Documents/mac提审自动化/scripts/utm_clone_macos.py" --check-only
```

## 成功确认

脚本返回码必须为 `0`，并且输出同时包含：

```text
CLONE_MARKER=verified
CLONE_CONFIG_IDENTITY=verified
UTM_REGISTRATION_MATCH_COUNT=1
UTM_REGISTRATION_STATE=stopped
UTM_CLONE_MACOS=verified
```

## 失败确认

返回码非 `0`，或输出包含以下内容，即为失败：

```text
UTM_CLONE_MACOS=blocked: ...
```
