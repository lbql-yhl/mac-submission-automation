#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/utm-11/SKILL.md"


def main() -> None:
    text = SKILL.read_text(encoding="utf-8")
    operation = text.split("## Workflow", 1)[1].split("## Completion", 1)[0]

    success = operation.index("We've received your App Store Small Business Program enrollment")
    capture = operation.index('saveReviewScreenshot("05-small-business.png")', success)
    assert success < capture

    for value in (
        "Paid Applications Agreement",
        "PAID_APPS_AGREEMENT=accepted",
        "automatically complete any known 2FA",
        "current `run_id`",
        "both success messages are already visible",
        "do not reopen or resubmit the enrollment form",
        'path.resolve(projectRoot, "runtime", "review-screenshots")',
        "reviewRoot.startsWith(screenshotBase + path.sep)",
        "sky.get_app_state",
        "com.utmapp.UTM",
        'execFileAsync("/usr/bin/sips"',
        "0o600",
        "REVIEW_SCREENSHOT_05=verified",
        "automatically click `Submit` once",
    ):
        assert value in text, value

    for name in (
        "01-media-manager.png",
        "02-iap-drafts.png",
        "03-app-information.png",
        "04-privacy-agreement.png",
    ):
        assert f'saveReviewScreenshot("{name}")' not in operation, name


if __name__ == "__main__":
    main()
