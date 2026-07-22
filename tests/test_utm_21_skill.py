#!/usr/bin/env python3
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/utm-21/SKILL.md"
HELPER = ROOT / "scripts/utm_21_clone.py"
DOC = ROOT / "docs/utm-21.md"


def main() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    helper = HELPER.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    combined = "\n".join((skill, doc, helper))

    for value in (
        "scripts/utm_21_clone.py", "CODEUP_USERNAME", "CODEUP_PASSWORD",
        "stdin_memory_only", "REPO_STATE=existing_pristine_verified",
        "resumable", "unrepairable", "origin/main", "git fsck --full",
        "PLACEHOLDERS_ALREADY_REPLACED=verified", "com.example.test.demok1",
        "com.example.<app_name>", "5372311233", "jltest.test.test",
        "git grep -I -i", "git grep -Ilz", "git diff --check",
        "env -u PUB_HOSTED_URL -u FLUTTER_STORAGE_BASE_URL flutter pub get",
        "pod install", "UTM_21=verified",
    ):
        assert value in combined, value

    for value in (
        "clone --branch main --single-branch", "credential.helper",
        "git remote get-url origin", "git rev-parse refs/remotes/origin/main",
        "git fsck --full", "unset CODEUP_USERNAME CODEUP_PASSWORD",
    ):
        assert value in helper, value

    assert not re.search(r"CODEUP_(?:USERNAME|PASSWORD)\s*=\s*['\"][^'\"]+['\"]", skill)
    assert not re.search(r"https://[^\s/]+:[^\s@]+@", combined)
    assert "runtime/feishu-runs.json" not in skill
    assert "docs/superpowers" not in combined
    assert "目标已存在时不删除、不覆盖、不换目录；向原" not in doc
    assert "四项总命中为 0 时禁止替换和继续，向原" not in doc

    print("UTM_21_SECURE_RECOVERY=verified")


if __name__ == "__main__":
    main()
