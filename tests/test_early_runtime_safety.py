#!/usr/bin/env python3
import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_writer():
    path = ROOT / "skills" / "utm-5" / "scripts" / "write_socks5_yml.py"
    spec = importlib.util.spec_from_file_location("write_socks5_yml", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path.read_text(encoding="utf-8")


def main() -> None:
    writer, source = load_writer()
    valid = {
        "host": "192.0.2.10",
        "port": "6368",
        "username": "user",
        "password": "pass:word",
    }
    writer.validate_proxy(valid)
    for key, value in (
        ("host", " 192.0.2.10"),
        ("host", "example.com"),
        ("port", "06368"),
        ("username", "user\nname"),
        ("password", " "),
    ):
        broken = dict(valid)
        broken[key] = value
        try:
            writer.validate_proxy(broken)
        except (ValueError, SystemExit):
            pass
        else:
            raise AssertionError(f"unsafe proxy value accepted: {key}")

    assert "请替换" not in writer.render(valid)
    assert "os.fsync" in source
    assert "SOCKS5_WRITE=unchanged" in source
    assert "SOCKS5_WRITE=changed" in source
    assert "SOCKS5_READBACK=exact" in source
    assert "RUN_VM_NAME_INVALID" in source

    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "socks5.yml"
        assert writer.atomic_write(target, "one") == "changed"
        first_inode = target.stat().st_ino
        assert writer.atomic_write(target, "one") == "unchanged"
        assert target.stat().st_ino == first_inode
        assert target.read_text(encoding="utf-8") == "one"
        assert target.stat().st_mode & 0o777 == 0o600

    utm_2 = (ROOT / "skills" / "utm-2" / "SKILL.md").read_text(encoding="utf-8")
    assert "seq 2 30" not in utm_2
    for required in (
        "IP_CANDIDATE_INTERSECTION_COUNT=1",
        "REMOTE_LOGIN=verified",
        "TEMPLATE_GUEST_IDENTIFIERS=verified",
        "GUEST_IDENTITY_DIFF=verified",
    ):
        assert required in utm_2, required

    notion = (ROOT / "skills" / "notion-utm" / "SKILL.md").read_text(encoding="utf-8")
    assert "application_after" in notion
    assert "APPLICATION_INFO=blank" in notion
    assert "if value.strip()" in notion

    print("EARLY_RUNTIME_SAFETY=verified")


if __name__ == "__main__":
    main()
