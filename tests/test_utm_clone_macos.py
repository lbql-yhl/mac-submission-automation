#!/usr/bin/env python3
import plistlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.utm_clone_macos import (  # noqa: E402
    compare_manifests,
    generate_local_mac,
    new_machine_identifier,
    parse_utmctl_list,
    rewrite_config_bytes,
)
from scripts import utm_clone_macos  # noqa: E402
from scripts.clean_cli import full_reason  # noqa: E402


def test_identity_rewrite_changes_only_allowed_fields() -> None:
    hardware = b"hardware-model"
    source = {
        "Information": {"Name": "macOS", "UUID": "11111111-1111-1111-1111-111111111111"},
        "Network": [{"MacAddress": "02:00:00:00:00:01", "Mode": "Shared"}],
        "System": {"MacPlatform": {"HardwareModel": hardware, "MachineIdentifier": new_machine_identifier()}},
    }
    changed = rewrite_config_bytes(
        plistlib.dumps(source),
        "abcd",
        "22222222-2222-2222-2222-222222222222",
        "02:00:00:00:00:02",
        new_machine_identifier(),
    )
    result = plistlib.loads(changed)
    assert result["Information"]["Name"] == "abcd"
    assert result["Information"]["UUID"] == "22222222-2222-2222-2222-222222222222"
    assert result["Network"][0]["MacAddress"] == "02:00:00:00:00:02"
    assert result["System"]["MacPlatform"]["HardwareModel"] == hardware


def test_manifest_compare_and_utmctl_parser(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "file.txt").write_text("same", encoding="utf-8")
    (destination / "file.txt").write_text("same", encoding="utf-8")
    assert compare_manifests(source, destination, {"config.plist", ".submission-clone.json"}) == []
    rows = parse_utmctl_list(
        "UUID                                 Status   Name\n"
        "11111111-1111-1111-1111-111111111111 stopped  abcd\n"
    )
    assert rows == [
        {
            "uuid": "11111111-1111-1111-1111-111111111111",
            "status": "stopped",
            "name": "abcd",
        }
    ]
    assert len(generate_local_mac({"02:00:00:00:00:01"})) == 17


def test_manifest_ignores_appledouble_sidecars(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "Data").mkdir()
    (destination / "Data").mkdir()
    (source / "Data" / "disk.img").write_bytes(b"same")
    (destination / "Data" / "disk.img").write_bytes(b"same")
    # exFAT creates AppleDouble metadata beside files written in the bundle.
    (source / "._config.plist").write_bytes(b"metadata")
    (destination / "._config.plist").write_bytes(b"metadata")
    (destination / "._.submission-clone.json").write_bytes(b"metadata")
    (destination / "Data" / "._disk.img").write_bytes(b"metadata")

    assert compare_manifests(source, destination, {"config.plist", ".submission-clone.json"}) == []


@pytest.mark.parametrize(
    ("scenario", "expected_code"),
    (
        ("ambiguous", "TEMPLATE_STATUS_AMBIGUOUS"),
        ("not_stopped", "TEMPLATE_NOT_STOPPED"),
        ("unavailable", "TEMPLATE_STATUS_UNAVAILABLE"),
    ),
)
def test_template_status_failures_use_stable_safe_codes(
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    expected_code: str,
) -> None:
    def status_command(_command: list[str]) -> str:
        if scenario == "ambiguous":
            return "stopped\nrunning\n"
        if scenario == "not_stopped":
            return "running\n"
        raise utm_clone_macos.CloneError("unsafe command failure detail")

    monkeypatch.setattr(
        utm_clone_macos, "run_template_status_command", status_command
    )
    monkeypatch.setattr(utm_clone_macos.time, "sleep", lambda _seconds: None)

    with pytest.raises(utm_clone_macos.CloneError) as caught:
        utm_clone_macos.require_template_stopped("template")

    assert str(caught.value) == expected_code
    assert full_reason(caught.value) == expected_code


def test_template_status_recovers_from_transient_command_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: list[str | BaseException] = [
        utm_clone_macos.CloneError("temporary unavailable"),
        "stopped\n",
        "stopped\n",
    ]
    calls: list[str] = []
    sleeps: list[float] = []

    def status_command(command: str) -> str:
        calls.append(command)
        response = responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    monkeypatch.setattr(
        utm_clone_macos, "run_template_status_command", status_command
    )
    monkeypatch.setattr(utm_clone_macos.time, "sleep", sleeps.append)

    utm_clone_macos.require_template_stopped("template")

    assert calls == ["template"] * 3
    assert sleeps == [5.0, utm_clone_macos.WAIT_SECONDS]


def test_template_status_exhausts_bounded_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    sleeps: list[float] = []

    def unavailable(command: str) -> str:
        calls.append(command)
        raise utm_clone_macos.CloneError("temporary unavailable")

    monkeypatch.setattr(
        utm_clone_macos, "run_template_status_command", unavailable
    )
    monkeypatch.setattr(utm_clone_macos.time, "sleep", sleeps.append)

    with pytest.raises(
        utm_clone_macos.CloneError, match="^TEMPLATE_STATUS_UNAVAILABLE$"
    ):
        utm_clone_macos.require_template_stopped("template")

    assert calls == ["template"] * 3
    assert sleeps == [5.0, 10.0]


def test_template_status_uses_bounded_process_and_ignores_stderr_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def status_process(command: list[str], **kwargs: object):
        calls.append((command, kwargs))
        return utm_clone_macos.subprocess.CompletedProcess(
            command,
            0,
            stdout="stopped\n",
            stderr="non-status warning\n",
        )

    monkeypatch.setattr(utm_clone_macos.subprocess, "run", status_process)
    monkeypatch.setattr(
        utm_clone_macos.subprocess,
        "check_output",
        lambda *_args, **_kwargs: pytest.fail(
            "template status must use its bounded, stderr-separated command"
        ),
    )
    monkeypatch.setattr(utm_clone_macos.time, "sleep", lambda _seconds: None)

    utm_clone_macos.require_template_stopped("template")

    assert len(calls) == 2
    for command, kwargs in calls:
        assert command == ["utmctl", "status", "template"]
        assert kwargs["timeout"] == 15.0
        assert kwargs["stdout"] is utm_clone_macos.subprocess.PIPE
        assert kwargs["stderr"] is utm_clone_macos.subprocess.PIPE


def test_template_status_timeout_retries_the_same_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: list[object] = [
        utm_clone_macos.subprocess.TimeoutExpired(
            ["utmctl", "status", "template"], 15.0
        ),
        utm_clone_macos.subprocess.CompletedProcess(
            [], 0, stdout="stopped\n", stderr=""
        ),
        utm_clone_macos.subprocess.CompletedProcess(
            [], 0, stdout="stopped\n", stderr=""
        ),
    ]
    calls: list[list[str]] = []
    sleeps: list[float] = []

    def status_process(command: list[str], **_kwargs: object):
        calls.append(command)
        response = responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    monkeypatch.setattr(utm_clone_macos.subprocess, "run", status_process)
    monkeypatch.setattr(
        utm_clone_macos.subprocess,
        "check_output",
        lambda *_args, **_kwargs: "stopped\n",
    )
    monkeypatch.setattr(utm_clone_macos.time, "sleep", sleeps.append)

    utm_clone_macos.require_template_stopped("template")

    assert calls == [["utmctl", "status", "template"]] * 3
    assert sleeps == [5.0, utm_clone_macos.WAIT_SECONDS]


def test_second_stability_read_failure_retries_the_entire_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: list[object] = [
        utm_clone_macos.subprocess.CompletedProcess(
            [], 0, stdout="stopped\n", stderr=""
        ),
        utm_clone_macos.subprocess.TimeoutExpired(
            ["utmctl", "status", "template"], 15.0
        ),
        utm_clone_macos.subprocess.CompletedProcess(
            [], 0, stdout="stopped\n", stderr=""
        ),
        utm_clone_macos.subprocess.CompletedProcess(
            [], 0, stdout="stopped\n", stderr=""
        ),
    ]
    calls: list[list[str]] = []
    sleeps: list[float] = []

    def status_process(command: list[str], **_kwargs: object):
        calls.append(command)
        response = responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    monkeypatch.setattr(utm_clone_macos.subprocess, "run", status_process)
    monkeypatch.setattr(
        utm_clone_macos.subprocess,
        "check_output",
        lambda *_args, **_kwargs: "stopped\n",
    )
    monkeypatch.setattr(utm_clone_macos.time, "sleep", sleeps.append)

    utm_clone_macos.require_template_stopped("template")

    assert calls == [["utmctl", "status", "template"]] * 4
    assert sleeps == [
        utm_clone_macos.WAIT_SECONDS,
        5.0,
        utm_clone_macos.WAIT_SECONDS,
    ]


def test_template_status_transition_retries_the_entire_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = iter(("stopping\n", "stopped\n", "stopped\n", "stopped\n"))
    calls: list[str] = []
    sleeps: list[float] = []

    def status_command(template_name_value: str) -> str:
        calls.append(template_name_value)
        return next(states)

    monkeypatch.setattr(
        utm_clone_macos, "run_template_status_command", status_command
    )
    monkeypatch.setattr(utm_clone_macos.time, "sleep", sleeps.append)

    utm_clone_macos.require_template_stopped("template")

    assert calls == ["template"] * 4
    assert sleeps == [
        utm_clone_macos.WAIT_SECONDS,
        5.0,
        utm_clone_macos.WAIT_SECONDS,
    ]


def test_template_status_persistently_running_exhausts_three_rounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    sleeps: list[float] = []

    def running(template_name_value: str) -> str:
        calls.append(template_name_value)
        return "running\n"

    monkeypatch.setattr(
        utm_clone_macos, "run_template_status_command", running
    )
    monkeypatch.setattr(utm_clone_macos.time, "sleep", sleeps.append)

    with pytest.raises(
        utm_clone_macos.CloneError, match="^TEMPLATE_NOT_STOPPED$"
    ):
        utm_clone_macos.require_template_stopped("template")

    assert calls == ["template"] * 6
    assert sleeps == [
        utm_clone_macos.WAIT_SECONDS,
        5.0,
        utm_clone_macos.WAIT_SECONDS,
        10.0,
        utm_clone_macos.WAIT_SECONDS,
    ]


def test_registration_waits_for_delayed_registry(monkeypatch, tmp_path: Path) -> None:
    bundle = tmp_path / "abcd.utm"
    rows = [{"uuid": "UUID", "status": "stopped", "name": "abcd"}]
    registries = [{"other": True}, {"ready": True}]
    sleeps: list[float] = []

    monkeypatch.setattr(
        utm_clone_macos, "target_status_rows", lambda _uuid, _name: rows
    )
    monkeypatch.setattr(
        utm_clone_macos, "read_registry", lambda: registries.pop(0)
    )
    monkeypatch.setattr(
        utm_clone_macos,
        "registry_matches",
        lambda registry, _uuid, _name, _bundle: (
            [{"match": "yes"}] if registry.get("ready") else []
        ),
    )
    monkeypatch.setattr(utm_clone_macos.time, "sleep", sleeps.append)

    actual_rows, actual_matches, registry_available = utm_clone_macos.wait_for_registration(
        "UUID", "abcd", bundle
    )

    assert actual_rows == rows
    assert actual_matches == [{"match": "yes"}]
    assert registry_available is True
    assert sleeps == [utm_clone_macos.WAIT_SECONDS]


def test_registration_accepts_cli_when_registry_domain_is_unavailable(
    monkeypatch, tmp_path: Path
) -> None:
    bundle = tmp_path / "abcd.utm"
    rows = [{"uuid": "UUID", "status": "stopped", "name": "abcd"}]
    sleeps: list[float] = []

    monkeypatch.setattr(
        utm_clone_macos, "target_status_rows", lambda _uuid, _name: rows
    )
    monkeypatch.setattr(utm_clone_macos, "read_registry", lambda: {})
    monkeypatch.setattr(
        utm_clone_macos,
        "registry_matches",
        lambda _registry, _uuid, _name, _bundle: [],
    )
    monkeypatch.setattr(utm_clone_macos.time, "sleep", sleeps.append)

    actual_rows, actual_matches, registry_available = (
        utm_clone_macos.wait_for_registration("UUID", "abcd", bundle)
    )

    assert actual_rows == rows
    assert actual_matches == []
    assert registry_available is False
    assert sleeps == []


def storage_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "source.utm"
    primary = tmp_path / "primary"
    fallback = tmp_path / "fallback"
    for path in (source, primary, fallback):
        path.mkdir()
    return source, primary, fallback


def test_select_clone_images_dir_uses_first_eligible_candidate(
    monkeypatch, tmp_path: Path
) -> None:
    source, primary, fallback = storage_paths(tmp_path)
    checked: list[Path] = []
    monkeypatch.setattr(utm_clone_macos, "package_allocated_bytes", lambda _: 50)
    monkeypatch.setattr(
        utm_clone_macos, "is_external_writable_volume", lambda _: True
    )

    def disk_usage(path: Path) -> SimpleNamespace:
        checked.append(path)
        return SimpleNamespace(free=utm_clone_macos.MINIMUM_FREE_BYTES + 50)

    monkeypatch.setattr(utm_clone_macos.shutil, "disk_usage", disk_usage)

    assert utm_clone_macos.select_clone_images_dir(
        source, (primary, fallback)
    ) == primary
    assert checked == [primary]


def test_select_clone_images_dir_falls_back_when_primary_would_cross_reserve(
    monkeypatch, tmp_path: Path
) -> None:
    source, primary, fallback = storage_paths(tmp_path)
    monkeypatch.setattr(utm_clone_macos, "package_allocated_bytes", lambda _: 50)
    monkeypatch.setattr(
        utm_clone_macos, "is_external_writable_volume", lambda _: True
    )
    monkeypatch.setattr(
        utm_clone_macos.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(
            free=utm_clone_macos.MINIMUM_FREE_BYTES
            + (49 if path == primary else 50)
        ),
    )

    assert utm_clone_macos.select_clone_images_dir(
        source, (primary, fallback)
    ) == fallback


def test_select_clone_images_dir_accepts_exact_reserve(
    monkeypatch, tmp_path: Path
) -> None:
    source, primary, _fallback = storage_paths(tmp_path)
    monkeypatch.setattr(utm_clone_macos, "package_allocated_bytes", lambda _: 50)
    monkeypatch.setattr(
        utm_clone_macos, "is_external_writable_volume", lambda _: True
    )
    monkeypatch.setattr(
        utm_clone_macos.shutil,
        "disk_usage",
        lambda _: SimpleNamespace(free=utm_clone_macos.MINIMUM_FREE_BYTES + 50),
    )

    assert utm_clone_macos.select_clone_images_dir(source, (primary,)) == primary


def test_select_clone_images_dir_skips_non_external_candidate(
    monkeypatch, tmp_path: Path
) -> None:
    source, primary, fallback = storage_paths(tmp_path)
    monkeypatch.setattr(utm_clone_macos, "package_allocated_bytes", lambda _: 50)
    monkeypatch.setattr(
        utm_clone_macos,
        "is_external_writable_volume",
        lambda path: path == fallback,
    )
    monkeypatch.setattr(
        utm_clone_macos.shutil,
        "disk_usage",
        lambda _: SimpleNamespace(free=utm_clone_macos.MINIMUM_FREE_BYTES + 50),
    )

    assert utm_clone_macos.select_clone_images_dir(
        source, (primary, fallback)
    ) == fallback


def test_select_clone_images_dir_blocks_when_all_candidates_are_insufficient(
    monkeypatch, tmp_path: Path
) -> None:
    source, primary, fallback = storage_paths(tmp_path)
    monkeypatch.setattr(utm_clone_macos, "package_allocated_bytes", lambda _: 50)
    monkeypatch.setattr(
        utm_clone_macos, "is_external_writable_volume", lambda _: True
    )
    monkeypatch.setattr(
        utm_clone_macos.shutil,
        "disk_usage",
        lambda _: SimpleNamespace(free=utm_clone_macos.MINIMUM_FREE_BYTES + 49),
    )

    with pytest.raises(
        utm_clone_macos.CloneError, match="CLONE_STORAGE_UNAVAILABLE"
    ):
        utm_clone_macos.select_clone_images_dir(source, (primary, fallback))


def test_external_volume_check_uses_diskutil_metadata(
    monkeypatch, tmp_path: Path
) -> None:
    candidate = tmp_path / "images"
    candidate.mkdir()
    payload = plistlib.dumps(
        {
            "Internal": False,
            "Mounted": True,
            "MountPoint": str(tmp_path),
            "MediaReadOnly": False,
            "VolumeReadOnly": False,
        }
    )
    monkeypatch.setattr(
        utm_clone_macos.subprocess,
        "check_output",
        lambda *_args, **_kwargs: payload,
    )

    assert utm_clone_macos.is_external_writable_volume(candidate) is True


def test_external_volume_check_accepts_omitted_mounted_flag(
    monkeypatch, tmp_path: Path
) -> None:
    candidate = tmp_path / "images"
    candidate.mkdir()
    payload = plistlib.dumps(
        {
            "Internal": False,
            "MountPoint": str(tmp_path),
            "BusProtocol": "USB",
            "Ejectable": True,
        }
    )
    monkeypatch.setattr(
        utm_clone_macos.subprocess,
        "check_output",
        lambda *_args, **_kwargs: payload,
    )

    assert utm_clone_macos.is_external_writable_volume(candidate) is True


def test_external_volume_check_resolves_the_device_for_a_subdirectory(
    monkeypatch, tmp_path: Path
) -> None:
    candidate = tmp_path / "images"
    candidate.mkdir()
    device = "/dev/disk9s1"
    payload = plistlib.dumps(
        {
            "Internal": False,
            "Mounted": True,
            "MountPoint": str(tmp_path),
            "MediaReadOnly": False,
            "VolumeReadOnly": False,
        }
    )
    calls: list[list[str]] = []

    def check_output(command, **_kwargs):
        calls.append(command)
        if command[:3] == ["diskutil", "info", "-plist"] and command[3] == str(
            candidate
        ):
            raise utm_clone_macos.subprocess.CalledProcessError(1, command)
        if command == ["/bin/df", "-P", str(candidate)]:
            return (
                "Filesystem 512-blocks Used Available Capacity Mounted on\n"
                f"{device} 1000 100 900 10% {tmp_path}\n"
            ).encode()
        if command == ["diskutil", "info", "-plist", device]:
            return payload
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(utm_clone_macos.subprocess, "check_output", check_output)

    assert utm_clone_macos.is_external_writable_volume(candidate) is True
    assert calls == [
        ["diskutil", "info", "-plist", str(candidate)],
        ["/bin/df", "-P", str(candidate)],
        ["diskutil", "info", "-plist", device],
    ]


if __name__ == "__main__":
    raise SystemExit(0)
