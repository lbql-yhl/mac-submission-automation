#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.utm_21_clone import build_payload, clone_target, validate_repo_url


def main() -> None:
    url = "https://codeup.aliyun.com/team/example.git"
    assert validate_repo_url(url) == url
    for invalid in (
        "http://codeup.aliyun.com/team/example.git",
        "https://user:secret@codeup.aliyun.com/team/example.git",
        "https://example.com/team/example.git",
        "https://codeup.aliyun.com/team/example",
    ):
        try:
            validate_repo_url(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(invalid)

    assert clone_target("abcd", url) == Path("/Users/abcd/StudioProjects/example")
    payload = build_payload("user", "secret", url, clone_target("abcd", url))
    assert payload.count(b"\0") == 4
    assert payload.endswith(b"\0")

    source = Path("scripts/utm_21_clone.py").read_text(encoding="utf-8")
    assert "shell=True" not in source
    assert "stdout=subprocess.PIPE" not in source
    assert "CODEUP_USERNAME" in source and "CODEUP_PASSWORD" in source
    assert "RUN_HOST_OWNERSHIP_MISMATCH" in source
    print("UTM_21_CLONE_HELPER=verified")


if __name__ == "__main__":
    main()
