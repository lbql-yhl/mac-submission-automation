#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/utm-22/SKILL.md"
SCRIPT = ROOT / "scripts/utm_22_distribute.mjs"
DOC = ROOT / "docs/utm-22.md"


def main() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    combined = "\n".join((skill, doc, script))

    for value in (
        "Runner.xcworkspace", "Xcode GUI", "Product", "Archive",
        "ARCHIVE_ATTEMPT_ID", "XCODE_GUI_RECOVERY=verified",
        "UPLOAD_ATTEMPT_ID", "--attempt-file", "prepare", "distribute",
        "buildUploads", "buildUploadFiles", "uploaded=true",
        "5/10/20 秒", "15/30/60/120 秒",
        "BUILD_UPLOAD_FINAL_STATE=COMPLETE", "BUILD_PROCESSING_STATE=VALID",
        "You must add the com.apple.developer.game-center key in Xcode.",
        "SIGNED_GAME_CENTER=verified", "PROFILE_GAME_CENTER=verified",
        "UTM_22=verified", "立即继续 `utm-23`",
    ):
        assert value in combined, value

    for value in (
        "classifyMatchingUploads", "resumePackagedIpa", "loadOrCreateAttempt",
        "ambiguous_existing_upload", "create_result_ambiguous",
        "recovered_after_create_result_unknown", "same-attempt IPA hash mismatch",
    ):
        assert value in script, value

    for forbidden in (
        "upload-existing", "xcodebuild archive", "xcodebuild -exportArchive",
        "git commit", "git push", "/Users/yehailin",
    ):
        assert forbidden not in combined, forbidden

    print("UTM_22_STABLE_ATTEMPTS=verified")


if __name__ == "__main__":
    main()
