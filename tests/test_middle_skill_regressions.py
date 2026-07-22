#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def read(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def main() -> None:
    utm_6 = read("utm-6")
    assert "append_once" not in utm_6
    assert "expected_proxy_ip='<proxy-ip" not in utm_6
    for required in (
        "ipaddress.IPv4Address",
        "# >>> submission-automation utm-6 >>>",
        "ZSHRC_WRITE=atomic_verified",
        "ZSHRC_ROLLBACK=verified",
    ):
        assert required in utm_6, required

    for name in ("utm-7", "utm-10"):
        text = read(name)
        for required in (
            'printf \'%s\' "$code" | pbcopy',
            "OTP_CLIPBOARD=verified",
            "pbcopy </dev/null",
            "unset code body SMS_URL",
        ):
            assert required in text, f"{name}: {required}"

    utm_8 = read("utm-8")
    for required in (
        "secrets.choice",
        "PASSWORD_CANDIDATE_ATTEMPTS<=3",
        "NOTION_PASSWORD_WRITE_RECOVERY=verified",
        "immediate/5/10-second",
    ):
        assert required in utm_8, required
    assert "rejected password, or security challenge stops" not in utm_8

    utm_9 = read("utm-9")
    docs_9 = (ROOT / "docs" / "utm-9.md").read_text(encoding="utf-8")
    for required in (
        "CSR_ATTEMPT_ID",
        "CSR_PATH=/Users/<vm_name>/Desktop/CertificateSigningRequest.certSigningRequest",
        "CSR_DISK=verified",
        "openssl req -in",
    ):
        assert required in utm_9, required
    assert "SSH 仅允许执行 `open -a" not in utm_9
    assert "ssh -tt" not in docs_9

    utm_10 = read("utm-10")
    assert "APPLE_ACCOUNT_EMAIL=verified" in utm_10

    utm_11 = read("utm-11")
    assert "`${PROJECT_ROOT}" not in utm_11
    for required in (
        "ENROLLMENT_SUBMIT_ATTEMPT_ID",
        "PAID_APPS_AGREEMENT=accepted",
        "SMALL_BUSINESS_SUCCESS_MESSAGES=verified",
    ):
        assert required in utm_11, required

    utm_12 = read("utm-12")
    assert "执行双击" not in utm_12
    for required in (
        "AGREEMENT_ATTEMPT_ID",
        "APP_ID_REGISTER_ATTEMPT_ID",
        "APP_CREATE_ATTEMPT_ID",
        "APP_STORE_APP=created_or_existing_exact",
    ):
        assert required in utm_12, required
    assert utm_12.count("scripts/notion_api.py verify-parent") >= 3

    utm_13 = read("utm-13")
    assert "按 `Down` 两次" not in utm_13
    for required in (
        "CSR_DISK=verified",
        "CODESIGN_IDENTITY=verified",
        "CERT_DOWNLOAD_NEW_COUNT=1",
        "PROFILE_GENERATE_ATTEMPT_ID",
    ):
        assert required in utm_13, required

    utm_14 = read("utm-14")
    for required in (
        "BROWSER_SESSION_RECHECKS=3",
        "FOREIGN_FORM_SUBMIT_ATTEMPT_ID",
        "W8BEN_SUBMIT_ATTEMPT_ID",
        "FOREIGN_FORM_LEDGER=verified",
        "W8BEN_LEDGER=verified",
        "DATE_KEYSTROKES_VERIFIED",
        "DAC7_READBACK=No_saved",
    ):
        assert required in utm_14, required

    utm_15 = read("utm-15")
    for required in (
        "BROWSER_SESSION_RECHECKS=3",
        "APP_ID_NOTION=equal|written",
        "APP_ID_READBACK=exact",
        "pbcopy </dev/null",
    ):
        assert required in utm_15, required
    assert utm_15.count("scripts/notion_api.py verify-parent") >= 4

    print("MIDDLE_SKILL_REGRESSIONS=verified")


if __name__ == "__main__":
    main()
