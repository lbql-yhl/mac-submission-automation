#!/usr/bin/env python3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
sys.path.insert(0, str(ROOT))

from scripts.utm_16_generate_env import write_env  # noqa: E402


def read(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def sample_env() -> dict[str, str]:
    return {
        "APP_ID": "1234567890",
        "CONTACT_PHONE": "+15551234567",
        "CONTACT_EMAIL": "person@example.com",
        "VM_NAME": "abcd",
        "CONTACT_FIRST_NAME": "Ada",
        "CONTACT_LAST_NAME": "Lovelace",
        "COPYRIGHT": "Example",
        "BUNDLE_ID": "com.example.app",
        "PRIMARY_CATEGORY": "GRAPHICS_AND_DESIGN",
        "DESCRIPTION": "First paragraph.",
        "KEYWORDS": "photo,design",
        "TOP_LEVEL_DOMAIN": "example.com",
        "SUPPORT_URL": "https://example.com/support",
        "PRIVACY_POLICY_URL": "https://example.com/privacy",
        "PRIVACY_CHOICES_URL": "https://example.com/terms",
    }


def main() -> None:
    generator_source = (ROOT / "scripts" / "utm_16_generate_env.py").read_text(encoding="utf-8")
    for required in ("os.fsync", "os.replace", "ENV_WRITE", "ENV_READBACK"):
        assert required in generator_source, required

    with tempfile.TemporaryDirectory() as tmp:
        output = write_env(sample_env(), Path(tmp))
        inode = output.stat().st_ino
        assert output.stat().st_mode & 0o777 == 0o600
        output_again = write_env(sample_env(), Path(tmp))
        assert output_again.stat().st_ino == inode
        assert output_again.read_bytes() == output.read_bytes()

    utm_16 = read("utm-16")
    for required in (
        "GUEST_ENV_WRITE=atomic_verified",
        "GUEST_ENV_ROLLBACK=verified",
        "ENV_READBACK=exact",
        "SSH_PRIVATE_KEY=verified",
    ):
        assert required in utm_16, required

    utm_17 = read("utm-17")
    for required in (
        "read-field --heading '应用信息' --label '研发金币图链接：' --copy",
        "read-field --heading '应用信息' --label '金币表格: ' --copy",
        "pbcopy </dev/null",
        "LINK_CLIPBOARD=cleared",
    ):
        assert required in utm_17, required

    utm_18 = read("utm-18")
    assert "`pkill` 必须返回 `0`" not in utm_18
    assert "幂等，可修复后执行一次新 attempt" not in utm_18
    for required in (
        "UTM_18_ATTEMPT_ID",
        "UTM_18_LOG_PATH=precommitted",
        "EDGE_CDP_HTTP=verified",
        "ZERO_BUSINESS_SIDE_EFFECTS=verified",
    ):
        assert required in utm_18, required

    utm_19 = read("utm-19")
    assert "/usr/bin/zipinfo -1" not in utm_19
    assert "partial_upload" not in utm_19
    for required in (
        "zipfile.ZipFile",
        "PurePosixPath",
        "external_attr",
        "JPEG_MAGIC=verified",
        "JPEG_SET_RECURSIVE=verified",
        "SCREENSHOT_PREUPLOAD_CLASSIFICATION=empty|complete",
    ):
        assert required in utm_19, required

    utm_20 = read("utm-20")
    for required in (
        "BANK_ADD_ATTEMPT_ID",
        "pbcopy </dev/null",
        "unset code body SMS_URL",
        "NOTION_BUSINESS_BEFORE=retained_until_verified",
        "BANK_SUCCESS_STATE=fresh|recovered|processing_resume",
    ):
        assert required in utm_20, required

    utm_21 = read("utm-21")
    assert "perl -pi" not in utm_21
    for required in (
        "repo_name not in {'.', '..'}",
        "CLONE_RESULT=created|existing_pristine|resumed",
        "PLACEHOLDER_STATE=needs_replacement|already_replaced",
        "REPLACEMENT_LEDGER=verified",
    ):
        assert required in utm_21, required

    utm_22 = read("utm-22")
    for required in (
        "ARCHIVE_LEDGER_MODE=600",
        "ARCHIVE_MANIFEST_SHA256",
        "VERSION_BUILD_SOURCE=verified",
        "GAME_CENTER_ARCHIVE_ATTEMPT_ID",
        "UPLOAD_ATTEMPT_MODE=600",
    ):
        assert required in utm_22, required

    utm_23 = read("utm-23")
    assert "/^[A-Za-z0-9._-]+$/" not in utm_23
    assert "var reviewRoot = `${PROJECT_ROOT}" not in utm_23
    for required in (
        "BROWSER_SESSION_RECHECKS=2",
        "PREPARATION_LEDGER_MODE=600",
        "ADD_BUILD_ATTEMPT_ID",
        "IAP_BATCH_ATTEMPT_ID",
        "APP_VERSION_LINK_ATTEMPT_ID",
        "FINAL_STATE_LEDGER=verified",
    ):
        assert required in utm_23, required

    utm_24 = read("utm-24")
    assert "/^[A-Za-z0-9._-]+$/" not in utm_24
    assert "var reviewRoot = `${PROJECT_ROOT}" not in utm_24
    for required in (
        "PRIVACY_CLIPBOARD=cleared",
        "REVIEW_SUBMIT_ATTEMPT_ID",
        "APPROVAL_DECISION_ID=bound",
        "EXPEDITE_SUBMIT_ATTEMPT_ID",
        "SCREENSHOT_RECOVERY=handoff_to_owner",
    ):
        assert required in utm_24, required

    utm_25 = read("utm-25")
    for required in (
        "BROWSER_SESSION_RECHECKS=2",
        "P8_CANDIDATE_COUNT=1",
        "P8_PAYLOAD=verified",
        "NOTION_EQUAL_READBACK=verified",
        "SECURE_TEMP_RETENTION=rollback_failure_only",
        "LEGACY_APPROVAL_MIGRATION=independently_verified",
    ):
        assert required in utm_25, required

    print("LATE_SKILL_REGRESSIONS=verified")


if __name__ == "__main__":
    main()
