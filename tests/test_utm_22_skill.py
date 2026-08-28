#!/usr/bin/env python3
from pathlib import Path

import pytest

from scripts import utm_22_upload


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/utm-22/SKILL.md"
ENTRY = "$PROJECT_ROOT/scripts/utm_22_upload.py"


def test_utm_22_skill_is_one_command_only_three_stage_workflow() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert len(skill.split()) <= 220
    assert skill.count(ENTRY) >= 1
    for required in (
        "scripts/preflight.py --project-only --emit-shell",
        "--run-id '<run-id>'",
        "--target '<app-name>-<vm-name>'",
        "--archive-path '<exact-archive>'",
        "## 1. Xcode 配置",
        "scripts/utm_22_archive.py",
        "xcodebuild -list -json",
        "xcodebuild -showBuildSettings",
        "UTM_22_XCODE_CONFIG=verified",
        "## 2. Archive",
        "xcodebuild archive",
        "UTM_22_ARCHIVE=verified",
        "## 3. IPA 打包上传",
        "scripts/utm_22_distribute.mjs upload-config",
        "UTM_22_UPLOAD=verified",
        "BUILD_UPLOAD_FINAL_STATE=COMPLETE",
        "BUILD_PROCESSING_STATE=VALID",
        "UTM_22=verified",
        "utm-23",
    ):
        assert required in skill, required

    for forbidden in (
        "Retry reversible configuration checks",
        "An interrupted or unknown result",
        "Only Apple's exact",
        "Preserve the same VM",
    ):
        assert forbidden not in skill, forbidden


def test_utm_22_upload_requires_one_exact_archive_and_resumes_one_attempt() -> None:
    archive = {
        "app_name": "Example",
        "bundle_id": "com.example.app",
        "path": "/Users/user/Library/Developer/Xcode/Archives/Example.xcarchive",
        "version": "1.2.3",
        "build": "42",
    }

    assert (
        utm_22_upload.choose_archive([archive], "Example", "com.example.app") == archive
    )
    with pytest.raises(utm_22_upload.UploadTargetError, match="ARCHIVE_MATCH_COUNT=2"):
        utm_22_upload.choose_archive(
            [archive, dict(archive)], "Example", "com.example.app"
        )

    assert (
        utm_22_upload.ssh_recovery_action(
            255, attempt_exists=True, remote_process_running=True
        )
        == "wait_same_process"
    )
    assert (
        utm_22_upload.ssh_recovery_action(
            255, attempt_exists=True, remote_process_running=False
        )
        == "resume_attempt"
    )

    args = utm_22_upload._parse_args(
        [
            "--target",
            "Example-user",
            "--archive-path",
            archive["path"],
        ]
    )
    assert args.target == "Example-user"
    assert args.archive_path == archive["path"]
