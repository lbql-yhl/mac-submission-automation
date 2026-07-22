#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/utm-18/SKILL.md"
UTM19_SKILL = ROOT / "skills/utm-19/SKILL.md"


def main() -> None:
    text = SKILL.read_text(encoding="utf-8")

    required = (
        "/bin/zsh -lic",
        "source /dev/stdin",
        "command -v node",
        "command -v npm",
        "node --version",
        "npm --version",
        "node --version ||",
        "npm --version ||",
        "CDP_ENDPOINT=http://127.0.0.1:9222",
        "/usr/bin/grep -c '^CDP_ENDPOINT=' .env",
        "set -o pipefail",
        "utm-18-fill-description-",
        '/bin/chmod 600 "$log_path"',
        'npm run fill:description 2>&1 | /usr/bin/tee "$log_path"',
        'statuses=("${pipestatus[@]}")',
        "REMOTE_NPM_EXIT=",
        "REMOTE_TEE_EXIT=",
        "RUN_STATE=running",
        "RUN_STATE=finished",
        'status_path="${log_path}.status"',
        "set -o noclobber",
        "RUN_STATE=prepared",
        "UTM_18_LOG_PATH=precommitted",
        "SSH_EXIT=255",
        "ssh_exit=$?",
        "printf 'SSH_EXIT=%s\\n'",
        "wc -c",
        "shasum -a 256",
        '/bin/cat "$log_path"',
        "manual_continue",
        "每个合法新 attempt 都先产生新的固定 ledger/log/status",
        "增强版内购创建完成！",
        "📊 统计信息: 共处理 14 个产品",
        "SSH_LOGIN_SHELL=verified",
        "UTM_18_LOG=verified",
        "REMOTE_NPM_EXIT=0",
    )
    for value in required:
        assert value in text, value

    forbidden = (
        "open -a Terminal",
        "open -na Terminal",
        "Command+N",
        "sky.click",
        "GUEST_TERMINAL=ready",
    )
    for value in forbidden:
        assert value not in text, value

    checklist = (ROOT / "docs" / "utm-18.md").read_text(encoding="utf-8")
    for value in (
        "/bin/zsh -lic",
        "完整实时回传",
        "每个合法新 attempt 都必须先有新 ledger/log/status",
        "REMOTE_NPM_EXIT=",
        "REMOTE_TEE_EXIT=",
        "SSH_EXIT=255",
        "manual_continue",
    ):
        assert value in checklist, value

    synchronized = {
        "README.md": ROOT / "README.md",
        "AGENTS.md": ROOT / "AGENTS.md",
        "docs/utm-feishu-bot.md": ROOT / "docs" / "utm-feishu-bot.md",
    }
    for label, path in synchronized.items():
        content = path.read_text(encoding="utf-8")
        assert "zsh -lic" in content, label
        assert "tee" in content, label
        assert "唯一日志" in content, label

    utm19 = UTM19_SKILL.read_text(encoding="utf-8")
    utm19_doc = (ROOT / "docs" / "utm-19.md").read_text(encoding="utf-8")
    for stale in (
        "保留 `utm-18` 的 guest Terminal",
        "保留 guest Terminal",
        "不操作保留的 guest Terminal",
    ):
        assert stale not in utm19, stale
        assert stale not in utm19_doc, stale


if __name__ == "__main__":
    main()
