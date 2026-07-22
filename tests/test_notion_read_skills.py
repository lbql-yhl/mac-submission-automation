#!/usr/bin/env python3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PROJECT_ROOT / "skills"

EXPECTED_LABELS = {
    "notion-utm": ("账号信息", "应用信息"),
    "notion-utm-1": ("应用信息", "研发金币图链接"),
    "utm-7": ("邮箱：", "修改后的密码：", "初始密码：", "电话：", "电话短信接收平台："),
    "utm-8": ("用户名：", "生日：", "修改后的密码："),
    "utm-9": ("邮箱：",),
    "utm-10": ("邮箱：", "修改后的密码：", "初始密码：", "电话：", "电话短信接收平台："),
    "utm-12": ("team ID:", "Renewal date："),
    "utm-13": ("应用名: ",),
    "utm-14": ("生日：",),
    "utm-15": ("APP_ID：",),
    "utm-16": (
        "用户名：", "邮箱：", "电话：", "APP_ID：",
        "应用名: ", "顶级域名: ", "正式包名: ", "隐私协议: ",
        "用户协议: ", "支持链接: ", "应用类型：", "应用描述：", "关键词: ",
    ),
    "utm-17": ("研发金币图链接：", "截图链接: ", "金币表格: "),
    "utm-18": (),
    "utm-19": ("截图链接: ",),
    "utm-20": ("商务", "ABA Routing Number：", "Account Number："),
    "utm-21": ("代码链接：", "APP_ID：", "正式包名: "),
    "utm-24": ("隐私协议: ",),
    "utm-25": ("更新信息", "退款回调及p8", "issuer id: ", "key id:", "p8文件内容："),
}

REQUIRED_API_ONLY_GUARDS = {
    "utm-24": (
        "Notion 只通过项目 `scripts/notion_api.py` 读取；不得用宿主 Chrome、Notion 插件、"
        "Playwright、CUA、坐标或浏览器剪贴板读取 Notion。"
    ),
    "utm-25": (
        "Notion 只通过项目 `scripts/notion_api.py` 读写；不得用宿主 Chrome、Notion 插件、"
        "Playwright、CUA、坐标或浏览器剪贴板读写 Notion。"
    ),
}

FORBIDDEN_UI_READS = {
    "notion-utm": ("latest Feishu bot registration data",),
    "utm-7": ("local Chrome Notion session",),
    "utm-9": ("宿主机 Google Chrome",),
    "utm-16": ("browser.user.openTabs()", "[data-block-id]", "--json"),
    "utm-17": ("Chrome Notion", "宿主机已有 Chrome"),
    "utm-19": ("宿主 Chrome",),
    "utm-21": ("用 Chrome 插件", "已打开的宿主 Chrome"),
}

DOC_EXPECTATIONS = {
    "docs/utm-9.md": ("scripts/notion_api.py", "verify-parent", "邮箱："),
    "docs/utm-13.md": ("scripts/notion_api.py", "verify-parent", "应用名: "),
    "docs/utm-14.md": ("scripts/notion_api.py", "verify-parent", "生日："),
    "docs/utm-16.md": (
        "scripts/notion_api.py", "verify-parent", "python3 -m scripts.utm_16_generate_env",
        "应用名: ", "关键词: ",
    ),
    "docs/utm-17.md": ("scripts/notion_api.py", "研发金币图链接：", "截图链接: ", "金币表格: "),
    "docs/utm-18.md": ("scripts/notion_api.py", "verify-parent", "utm-10"),
    "docs/utm-19.md": ("scripts/notion_api.py", "verify-parent", "截图链接: "),
    "docs/utm-21.md": ("scripts/notion_api.py", "verify-parent", "正式包名: "),
    "docs/utm-24.md": ("scripts/notion_api.py", "verify-parent", "隐私协议: "),
    "docs/utm-25.md": (
        "scripts/notion_api.py", "verify-parent", "write-toggle-code", "read-toggle-code", "退款回调及p8"
    ),
}


def main() -> None:
    notion_utm = (SKILL_ROOT / "notion-utm" / "SKILL.md").read_text(encoding="utf-8")
    assert "same current Feishu submission run" in notion_utm
    assert "verify-parent --title '<宿主机名称>'" in notion_utm
    assert "银行区块可省略，两项银行号码也可留空" in notion_utm
    for stale in ("fixed `海淋`", "permanently assigned to `海淋`", "verify-parent --title '海淋'", "PARENT_PAGE=海淋_verified"):
        assert stale not in notion_utm, stale

    for skill_name, labels in EXPECTED_LABELS.items():
        text = (SKILL_ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")
        assert "scripts/notion_api.py" in text, skill_name
        assert "verify-parent" in text, skill_name
        for label in labels:
            assert label in text, f"{skill_name}: {label!r}"
        for stale in FORBIDDEN_UI_READS.get(skill_name, ()):
            assert stale not in text, f"{skill_name}: {stale}"
        guard = REQUIRED_API_ONLY_GUARDS.get(skill_name)
        if guard:
            assert guard in text, f"{skill_name}: missing API-only guard"

    for relative_path, expected in DOC_EXPECTATIONS.items():
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        for value in expected:
            assert value in text, f"{relative_path}: {value!r}"

    agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "existing guest Edge plus already-open host Chrome workflow" not in agents
    assert "using native clipboard and the current right-click `Paste` menu" not in agents
    assert "update only Notion `APP_ID：` through `scripts/notion_api.py`" in agents
    api_rule = next(line for line in agents.splitlines() if line.startswith("- Notion API 硬规则："))
    for skill_name in EXPECTED_LABELS:
        assert f"`{skill_name}`" in api_rule, skill_name

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    bot_doc = (PROJECT_ROOT / "docs/utm-feishu-bot.md").read_text(encoding="utf-8")
    for value in ("utm-7", "utm-9", "utm-10", "utm-13", "utm-14", "utm-16", "utm-17", "utm-18", "utm-19", "utm-21"):
        assert value in readme
        assert value in bot_doc
    assert "通过 Notion API" in readme
    assert "scripts/notion_api.py" in bot_doc
    utm_24_lines = [
        line for line in readme.splitlines()
        if line.startswith("→ utm-24：") or line.startswith("30. `utm-24`：")
    ]
    assert len(utm_24_lines) == 2
    assert any("Notion API" in line for line in utm_24_lines)
    assert any("record-auto-review-approval" in line for line in utm_24_lines)
    utm_25_lines = [
        line for line in readme.splitlines()
        if line.startswith("→ utm-25：") or line.startswith("31. `utm-25`：")
    ]
    assert len(utm_25_lines) == 2
    assert all("Notion API" in line for line in utm_25_lines)

    print("NOTION_READ_SKILLS=verified")


if __name__ == "__main__":
    main()
