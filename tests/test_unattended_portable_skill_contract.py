#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills"
ORDERED = (
    "notion-utm", "notion-utm-1", "utm-clone-macos", "utm-1", "utm-2", "utm-3",
    "vm-down", "utm-4", "utm-5", "files", "utm-clash", "utm-6", "utm-7", "utm-8",
    "utm-9", "utm-10", "utm-11", "utm-12", "utm-13", "utm-14", "utm-15", "utm-16",
    "utm-17", "utm-18", "utm-19", "utm-20", "utm-21", "utm-22", "utm-23", "utm-24", "utm-25",
)
GUI_SKILLS = {
    "utm-clone-macos", "utm-1", "utm-3", "vm-down", "utm-clash", "utm-7", "utm-8",
    "utm-9", "utm-10", "utm-11", "utm-12", "utm-13", "utm-14", "utm-15", "utm-17",
    "utm-18", "utm-19", "utm-20", "utm-22", "utm-23", "utm-24", "utm-25",
}


def read_skill(name: str) -> str:
    return (SKILL_ROOT / name / "SKILL.md").read_text(encoding="utf-8")


def require_all(text: str, values: tuple[str, ...], source: str) -> None:
    for value in values:
        assert value in text, f"{source}: missing {value}"


def main() -> None:
    assert SKILL_ROOT.is_dir(), "project must own the canonical skill source"
    discovered = tuple(
        sorted(path.parent.name for path in SKILL_ROOT.glob("*/SKILL.md"))
    )
    assert discovered == tuple(sorted(ORDERED)), discovered
    assert len(ORDERED) == len(set(ORDERED)) == 31

    shared = (SKILL_ROOT / "_shared" / "AUTOMATION_CONTRACT.md").read_text(encoding="utf-8")
    require_all(
        shared,
        (
            "自动诊断 → 自动修复 → 自动复验 → 最后才发故障卡",
            "每次 GUI 动作后的固定闭环",
            "窗口尺寸、焦点、菜单或页面布局变化",
            "可逆误点恢复",
            "不可逆动作的两阶段门禁",
            "AUTO_RECOVERY_ATTEMPTS",
            "AUTO_RECOVERY_ACTIONS",
            "AUTO_RECOVERY_RESULT",
            "--recovery-attempts",
            "--recovery-actions",
            "--recovery-result",
            "--unrepairable",
            "OP-NATIVE-PASTE",
            "OP-BROWSER-URL-NO-SCHEME",
            "OP-APPLE-PHONE-OTP",
            "OP-FIXED-PASSWORD-1234",
            "OP-USER-CONFIRMATION",
            "scripts/shared_operations.py browser-url",
        ),
        "shared contract",
    )

    for name in ORDERED:
        text = read_skill(name)
        require_all(
            text,
            (
                "../_shared/AUTOMATION_CONTRACT.md",
                "## 本技能自动恢复矩阵",
                "AUTO_RECOVERY_ATTEMPTS",
                "AUTO_RECOVERY_ACTIONS",
                "AUTO_RECOVERY_RESULT",
                "--recovery-attempts",
                "--recovery-actions",
                "--recovery-result",
                "notify-fault",
                "wait-decision",
                "自动恢复穷尽后",
                "<actual-count-at-least-3>",
                "OP-NATIVE-PASTE",
                "OP-BROWSER-URL-NO-SCHEME",
                "OP-APPLE-PHONE-OTP",
                "OP-FIXED-PASSWORD-1234",
                "OP-USER-CONFIRMATION",
                "少于三轮时运行时拒绝发卡",
            ),
            name,
        )
        assert "异常必须先向当前 run 原" not in text, name
        assert text.count("python3 services/feishu_bot.py notify-fault") == 1, name
        for fault_first in (
            "Immediately send the fault card",
            "任一异常都必须进入统一故障卡流程",
            "发生阻断时立即暂停后续副作用，以对应",
            "immediately use the global fault-card flow",
            "进入统一故障卡流程",
            "uses the existing fault-card path",
            "使用当前 run 的故障卡流程",
            "走当前 run 的故障卡流程",
            "进入 `utm-24` 三按钮故障卡",
            "停在故障卡人工检查循环",
        ):
            assert fault_first not in text, f"{name}: fault-first wording {fault_first}"
        assert "/Users/yehailin" not in text, f"{name}: host-specific path"
        if name in GUI_SKILLS:
            require_all(
                text,
                ("误点", "GUI_RECOVERY=verified", "最新截图", "至少 3 秒"),
                name,
            )

    utm_19 = read_skill("utm-19")
    require_all(
        utm_19,
        (
            "当前数字 App ID",
            "上传前只读分类",
            "已有截图数量",
            "剩余容量",
            "SCREENSHOT_PREUPLOAD_CLASSIFICATION=empty|complete",
            "Cancel",
        ),
        "utm-19",
    )
    assert "partial_upload" not in utm_19
    assert "不核对详情 URL" not in utm_19

    utm_22 = read_skill("utm-22")
    require_all(
        utm_22,
        (
            "UPLOAD_ATTEMPT_ID",
            "有界只读轮询",
            "结果不明",
            "先查询同一版本和构建号",
            "XCODE_GUI_RECOVERY=verified",
        ),
        "utm-22",
    )

    utm_23 = read_skill("utm-23")
    require_all(
        utm_23,
        (
            "ADD_BUILD_VISIBILITY_POLL=exhausted",
            "不得重复上传",
            "删除前证据快照",
            "删除确认弹窗",
            "确定性恢复到第一个未完成步骤",
        ),
        "utm-23",
    )
    assert "upload-existing" not in utm_23

    utm_24 = read_skill("utm-24")
    require_all(
        utm_24,
        (
            "record-auto-review-approval",
            "AUTOMATIC_REVIEW_APPROVAL=verified",
            "AUTOMATIC_REVIEW_SUBMIT=enabled",
            "系统自检授权",
        ),
        "utm-24",
    )
    assert "notify-review" not in utm_24
    assert "--decision-kind review_submit" not in utm_24
    assert "提审确认卡" not in utm_24

    utm_25 = read_skill("utm-25")
    require_all(
        utm_25,
        (
            "复制前清空剪贴板并写入随机哨兵",
            "哨兵不得残留",
            "NOTION_ROLLBACK=verified",
            "before 文件自动还原",
        ),
        "utm-25",
    )

    for required in (
        ROOT / "scripts" / "install_project_skills.sh",
        ROOT / "scripts" / "notion_api.py",
        ROOT / "scripts" / "notion_utm_prepare.py",
        ROOT / "scripts" / "preflight.py",
        ROOT / "scripts" / "shared_operations.py",
        ROOT / "scripts" / "utm_16_generate_env.py",
        ROOT / "scripts" / "utm_21_clone.py",
        ROOT / "scripts" / "utm_22_distribute.mjs",
        ROOT / "services" / "feishu_bot.py",
        ROOT / "services" / "feishu_gateway.py",
        ROOT / "services" / "feishu_supervisor.py",
        ROOT / "services" / "project_paths.py",
        ROOT / "services" / "submission_runner.py",
        ROOT / "config" / "workflow.env.example",
        ROOT / "shared-files" / "README.md",
        ROOT / "shared-files" / "Fire_One_en1.2" / ".env.example",
        ROOT / "shared-files" / "Fire_One_en1.2" / "package-lock.json",
        ROOT / "shared-files" / "Fire_One_en1.2" / "package.json",
        ROOT / "shared-files" / "Fire_One_en1.2" / "src" / "fill-description.ts",
        ROOT / "shared-files" / "Fire_One_en1.2" / "tsconfig.json",
        ROOT / "shared-files" / "apple-store-bm" / "README.md",
        ROOT / "shared-files" / "apple-store-bm" / "apple_store_tools",
        ROOT / "shared-files" / "apple-store-bm" / "config" / "prod.example.yml",
    ):
        assert required.is_file(), required

    shared_files = ROOT / "shared-files"
    forbidden_shared_paths = (
        shared_files / ".env",
        shared_files / "socks5.yml",
        shared_files / "Fire_One_en1.2" / ".env",
        shared_files / "Fire_One_en1.2" / "node_modules",
        shared_files / "apple-store-bm" / "config" / "prod.yml",
        shared_files / "tools" / "flutter",
    )
    for forbidden in forbidden_shared_paths:
        assert not forbidden.exists(), forbidden
    assert not tuple(shared_files.rglob("*.p8")), "shared source must not contain P8 keys"
    assert all(path.stat().st_size < 100 * 1024 * 1024 for path in shared_files.rglob("*") if path.is_file())
    assert (shared_files / "apple-store-bm" / "apple_store_tools").stat().st_mode & 0o100

    fire_package = json.loads(
        (shared_files / "Fire_One_en1.2" / "package.json").read_text(encoding="utf-8")
    )
    assert "test:description" not in fire_package["scripts"], (
        "--dry-run is not implemented and must not be advertised as a safe test"
    )
    fire_tsconfig = json.loads(
        (shared_files / "Fire_One_en1.2" / "tsconfig.json").read_text(encoding="utf-8")
    )
    assert fire_tsconfig["compilerOptions"]["module"] == "NodeNext"
    fire_source = (
        shared_files / "Fire_One_en1.2" / "src" / "fill-description.ts"
    ).read_text(encoding="utf-8")
    assert "const APP_ID = process.env.APP_ID ?? '';" in fire_source
    require_all(fire_source, ("APP_ID 必须为纯数字", "Issuer ID 已读取", "Key ID 已读取"), "Fire_One")
    for forbidden in (
        "已记录 issuer: ${issuer}",
        "已记录 key: ${key}",
        "已记录 p8 文件名: ${p8FileName}",
        "已强制保存 p8 文件到: ${downloadPath}",
    ):
        assert forbidden not in fire_source, f"Fire_One: sensitive log {forbidden}"
    assert not (ROOT / "docs" / "superpowers").exists(), "historical execution contracts must be removed"
    assert not (ROOT / "runtime" / "utm_22_game_center_rebuild.zsh").exists(), "stale executable"

    socks_writer = (ROOT / "skills" / "utm-5" / "scripts" / "write_socks5_yml.py").read_text(encoding="utf-8")
    require_all(socks_writer, ("required=True", "SHARED_DIR", "RUNS_FILE"), "utm-5 writer")
    for forbidden in ("--vm-name", "--latest-feishu-history", "load_latest_history_proxy", "--host", "--password"):
        assert forbidden not in socks_writer, f"utm-5 writer: unsafe fallback {forbidden}"

    generator = (ROOT / "scripts" / "utm_16_generate_env.py").read_text(encoding="utf-8")
    assert "/Users/yehailin" not in generator
    assert "SHARED_DIR" in generator

    runner = (ROOT / "services" / "submission_runner.py").read_text(encoding="utf-8")
    assert 'os.getenv("FEISHU_CODEX_MODEL", "gpt-5.6-sol")' in runner

    installer = (ROOT / "scripts" / "install_project_skills.sh").read_text(encoding="utf-8")
    require_all(
        installer,
        (
            "validate_all_sources",
            "rollback_install",
            "unsafe install root",
            "PROJECT_SKILLS_INSTALLED=31",
            "PROJECT_SHARED_CONTRACT=linked",
        ),
        "installer",
    )

    env_example = (ROOT / "config" / "workflow.env.example").read_text(encoding="utf-8")
    assert "SUBMISSION_HOST_MACHINE=\n" in env_example
    require_all(env_example, ("CODEUP_USERNAME=", "CODEUP_PASSWORD="), "env example")

    portable_sources = (
        ROOT / ".env.example",
        ROOT / "config" / "workflow.env.example",
        ROOT / "services" / "project_paths.py",
    )
    for source in portable_sources:
        text = source.read_text(encoding="utf-8")
        assert "/Volumes/AutoA" not in text, f"{source.name}: copied-host VM path"

    active_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (ROOT / "README.md", ROOT / "AGENTS.md", *sorted((ROOT / "docs").glob("*.md")))
    )
    for path in (ROOT / "README.md", ROOT / "AGENTS.md"):
        text = path.read_text(encoding="utf-8")
        require_all(text, ("skills/<skill>/SKILL.md", "Codex 记忆"), path.name)
    assert "/Users/yehailin" not in active_text
    assert "/Volumes/AutoA" not in active_text
    assert "computer-use/1.0." not in active_text
    for stale_fault_first in (
        "unknown categories stop the workflow",
        "after 5 failures call `notify-fault`",
        "uses the abnormal fault-card path",
        "handled only through the fault card",
        "A known business failure also sends a new fault card",
        "未知分类立即阻断",
        "未知协议/安全异常才发故障卡",
    ):
        assert stale_fault_first not in active_text, stale_fault_first

    print("UNATTENDED_PORTABLE_SKILL_CONTRACT=verified")


if __name__ == "__main__":
    main()
