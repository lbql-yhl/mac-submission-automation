#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import sys
import tempfile
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SOURCE_ROOT))

from services.project_paths import PROJECT_ROOT, SHARED_DIR  # noqa: E402


RUNS_FILE = PROJECT_ROOT / "runtime" / "feishu-runs.json"
OUTPUT_FILE = SHARED_DIR / "socks5.yml"


def q(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def validate_proxy(proxy: dict[str, str]) -> None:
    for key in ("host", "port", "username", "password"):
        value = proxy.get(key, "")
        if not isinstance(value, str) or not value or value != value.strip():
            raise ValueError(f"Invalid proxy field: {key}")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError(f"Control character in proxy field: {key}")

    try:
        parsed_host = ipaddress.IPv4Address(proxy["host"])
    except ipaddress.AddressValueError as exc:
        raise ValueError("Proxy host must be a canonical IPv4 address") from exc
    if str(parsed_host) != proxy["host"]:
        raise ValueError("Proxy host must be a canonical IPv4 address")

    if not re.fullmatch(r"[1-9][0-9]{0,4}", proxy["port"]):
        raise ValueError("Proxy port must be canonical decimal")
    port = int(proxy["port"])
    if not 1 <= port <= 65535 or str(port) != proxy["port"]:
        raise ValueError("Proxy port out of range")


def load_run_proxy(run_id: str) -> tuple[dict[str, str], dict]:
    if not re.fullmatch(r"[A-Za-z0-9-]{8,80}", run_id):
        raise SystemExit("RUN_ID_INVALID")
    if not RUNS_FILE.is_file() or RUNS_FILE.is_symlink():
        raise SystemExit("RUNS_FILE_MISSING")
    data = json.loads(RUNS_FILE.read_text(encoding="utf-8"))
    matches = [run for run in data.get("runs", []) if str(run.get("id") or "") == run_id]
    if len(matches) != 1:
        raise SystemExit(f"RUN_ID_MATCH_COUNT={len(matches)}")

    run = matches[0]
    submission_data = run.get("submission_data") or {}
    local_host = os.getenv("SUBMISSION_HOST_MACHINE", "").strip()
    run_host = str(submission_data.get("host_machine") or run.get("host_machine") or "").strip()
    if not local_host or run_host != local_host:
        raise SystemExit("RUN_HOST_OWNERSHIP_MISMATCH")

    vm_name = str(run.get("vm_name") or "")
    if not re.fullmatch(r"[a-z]{4}", vm_name):
        raise SystemExit("RUN_VM_NAME_INVALID")

    proxy = {
        key: str(((submission_data.get("proxy") or {}).get(key)) or "")
        for key in ("host", "port", "username", "password")
    }
    missing = [key for key, value in proxy.items() if not value]
    if missing:
        raise SystemExit("RUN_PROXY_FIELDS_MISSING=" + ",".join(missing))
    try:
        validate_proxy(proxy)
    except ValueError as exc:
        raise SystemExit("RUN_PROXY_FIELDS_INVALID") from exc
    return proxy, run


def render(proxy: dict[str, str]) -> str:
    validate_proxy(proxy)
    port = int(proxy["port"])

    return f"""port: 7890
socks-port: 7891
allow-lan: false
mode: rule
log-level: info

dns:
  enable: true
  listen: 0.0.0.0:53
  enhanced-mode: fake-ip
  fake-ip-range: 198.18.0.1/16
  nameserver:
    - 8.8.8.8
    - 1.1.1.1
  fallback:
    - https://dns.google/dns-query
    - https://cloudflare-dns.com/dns-query

proxies:
  - name: "My-SOCKS5-Proxy"
    type: socks5
    server: {q(proxy["host"])}
    port: {port}
    username: {q(proxy["username"])}
    password: {q(proxy["password"])}

proxy-groups:
  - name: "PROXY"
    type: select
    proxies:
      - "My-SOCKS5-Proxy"

rules:
  - DOMAIN-SUFFIX,apple.com,PROXY
  - DOMAIN-SUFFIX,icloud.com,PROXY
  - DOMAIN-SUFFIX,mobileme.icloud.com,PROXY
  - DOMAIN-SUFFIX,me.com,PROXY
  - DOMAIN-SUFFIX,mzstatic.com,PROXY
  - DOMAIN-SUFFIX,itunes.apple.com,PROXY
  - DOMAIN-SUFFIX,apps.apple.com,PROXY
  - DOMAIN-SUFFIX,appstoreconnect.apple.com,PROXY
  - DOMAIN-SUFFIX,testflight.apple.com,PROXY
  - DOMAIN-SUFFIX,developer.apple.com,PROXY
  - DOMAIN-KEYWORD,apple,PROXY
  - DOMAIN-KEYWORD,icloud,PROXY
  - DOMAIN-KEYWORD,appstore,PROXY

  - GEOIP,CN,DIRECT

  - MATCH,PROXY
"""


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _replace_payload(path: Path, payload: bytes, mode: int = 0o600) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            os.fchmod(handle.fileno(), mode)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        os.chmod(path, mode)
        _fsync_directory(path.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def atomic_write(path: Path, text: str) -> str:
    path = path.expanduser()
    if not path.is_absolute():
        raise RuntimeError("Output path must be absolute")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink() or (path.exists() and not path.is_file()):
        raise RuntimeError("Unsafe output path")

    payload = text.encode("utf-8")
    before = path.read_bytes() if path.exists() else None
    before_mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    if before == payload and before_mode == 0o600:
        return "unchanged"

    try:
        _replace_payload(path, payload)
        if path.is_symlink() or not path.is_file():
            raise RuntimeError("Output is not a regular file")
        if path.stat().st_mode & 0o777 != 0o600:
            raise RuntimeError("Output mode mismatch")
        if path.read_bytes() != payload:
            raise RuntimeError("Output readback mismatch")
    except BaseException:
        if before is None:
            if path.exists() and not path.is_symlink() and path.is_file():
                path.unlink()
                _fsync_directory(path.parent)
        else:
            _replace_payload(path, before, before_mode)
            if path.read_bytes() != before:
                raise RuntimeError("Output rollback mismatch")
        raise
    return "changed"


def self_test() -> None:
    proxy = {"host": "192.0.2.10", "port": "6368", "username": "user", "password": "pass:word"}
    text = render(proxy)
    assert "mode: rule" in text
    assert 'server: "192.0.2.10"' in text
    assert "port: 6368" in text
    assert 'password: "pass:word"' in text
    assert "  - MATCH,PROXY" in text


def main() -> None:
    parser = argparse.ArgumentParser(description="Write the UTM shared socks5.yml proxy profile.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        print("self-test ok")
        return

    proxy, run = load_run_proxy(args.run_id)
    text = render(proxy)
    if not SHARED_DIR.is_absolute() or SHARED_DIR.is_symlink():
        raise SystemExit("SUBMISSION_SHARED_DIR_UNSAFE")
    if OUTPUT_FILE.parent != SHARED_DIR or OUTPUT_FILE.name != "socks5.yml":
        raise SystemExit("SOCKS5_OUTPUT_PATH_MISMATCH")

    write_state = atomic_write(OUTPUT_FILE, text)
    if not OUTPUT_FILE.is_file() or OUTPUT_FILE.stat().st_mode & 0o777 != 0o600:
        raise SystemExit("SOCKS5_WRITE_VERIFY_FAILED")
    if OUTPUT_FILE.read_text(encoding="utf-8") != text:
        raise SystemExit("SOCKS5_READBACK_MISMATCH")

    proxy_after, run_after = load_run_proxy(args.run_id)
    if proxy_after != proxy or run_after.get("vm_name") != run.get("vm_name"):
        raise SystemExit("RUN_CHANGED_DURING_WRITE")
    print("SOCKS5_RUN_ID=exact_matched")
    print("SOCKS5_RUN_HOST=verified")
    if write_state == "unchanged":
        print("SOCKS5_WRITE=unchanged")
    else:
        print("SOCKS5_WRITE=changed")
    print("SOCKS5_READBACK=exact")
    print("SOCKS5_OUTPUT=verified")
    print("SOCKS5_MODE=600")


if __name__ == "__main__":
    main()
