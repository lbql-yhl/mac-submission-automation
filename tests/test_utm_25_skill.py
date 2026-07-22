#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/utm-25/SKILL.md"
DOC = ROOT / "docs/utm-25.md"


def main() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    combined = "\n".join((skill, doc))

    for value in (
        "UTM_24=verified", "同一 guest Edge",
        "appstoreconnect.apple.com/access/integrations/api", "Team Keys",
        "ACTIVE_API_KEY_COUNT=1", "不得按 `NAME`", "Revoked",
        "随机哨兵", "与随机哨兵不同", "从页面再复制一次",
        "AuthKey_<当前 Key ID>.p8", "prod.yml",
        "始终扫描完整 Downloads", "规范化真实路径去重",
        "不得因候选只有一个就直接采用",
        "-----BEGIN PRIVATE KEY-----", "-----END PRIVATE KEY-----",
        "write-toggle-code", "read-toggle-code", "退款回调及p8",
        "secure-before-file", "secure-rollback-file", "NOTION_ROLLBACK=verified",
        "NOTION_REFUND_CALLBACK_P8=verified", "API_CREDENTIALS_REGISTRATION=verified",
        "review_submission_approval", "status=approved", "decision=submit_review",
        "source=automatic_self_check", "operator_id=automation:self-check",
        "review_success", "status=sending", "message_uuid", "status=sent",
        "python3 services/feishu_bot.py notify-review-success",
        "不得生成新 UUID", "用户可见成功卡最多一张",
        "REVIEW_SUCCESS_NOTIFICATION=sent", "UTM_25=verified",
        "最终技能", "不再调用或交接其他技能",
    ):
        assert value in combined, value

    for value in (
        "0 条或多于 1 条时重新读取同一 Team Keys 页面、加载/权限、表格和筛选状态三轮",
        "零/多候选时做三轮完整重扫",
        "恢复穷尽", "最后三按钮故障卡",
    ):
        assert value in doc, value

    utm_24 = (ROOT / "skills/utm-24/SKILL.md").read_text(encoding="utf-8")
    assert "notify-review-success" not in utm_24
    assert skill.count("python3 services/feishu_bot.py notify-review-success") == 1
    assert skill.index("NOTION_REFUND_CALLBACK_P8=verified") < skill.index(
        "python3 services/feishu_bot.py notify-review-success"
    )

    print("UTM_25_SECURE_IDEMPOTENT_SUCCESS=verified")


if __name__ == "__main__":
    main()
