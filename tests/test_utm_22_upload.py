from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import utm_22_upload
from scripts.utm_22_upload import (
    UploadTarget,
    UploadTargetError,
    _create_or_resume_archive,
    _parse_args,
    _run_workflow,
    _run_upload,
    _verified_archive,
    archive_host_action,
    classify_upload_failure,
    choose_archive,
    resolve_manual_target,
    resolve_run_target,
    ssh_recovery_action,
)


@pytest.mark.parametrize(
    ("state", "alive", "expected"),
    [
        ("running", True, "poll"),
        ("verified", False, "use_verified"),
        ("starting", False, "stop_ambiguous"),
        ("failed", False, "stop_failed"),
    ],
)
def test_archive_host_recovery_never_starts_a_speculative_second_archive(
    state: str, alive: bool, expected: str
) -> None:
    assert archive_host_action(state=state, process_alive=alive) == expected


def test_verified_archive_is_bound_to_owner_vm_and_exact_xcarchive() -> None:
    target = UploadTarget("PitchPan", "user", "submission-1")
    owner_hash = "a" * 16
    ledger = {
        "owner_hash": owner_hash,
        "app_name": "PitchPan",
        "state": "verified",
        "archive_path": (
            "/Users/user/Library/Developer/Xcode/Archives/utm-22/"
            "aaaaaaaaaaaaaaaa-1.2.3-42.xcarchive"
        ),
        "bundle_id": "io.pitchpan.example",
        "version": "1.2.3",
        "build": "42",
    }

    archive = _verified_archive(target, owner_hash, ledger)

    assert archive == {
        "path": ledger["archive_path"],
        "app_name": "PitchPan",
        "bundle_id": "io.pitchpan.example",
        "version": "1.2.3",
        "build": "42",
    }
    with pytest.raises(UploadTargetError, match="ARCHIVE_OWNER_MISMATCH"):
        _verified_archive(target, "b" * 16, ledger)
    with pytest.raises(UploadTargetError, match="ARCHIVE_APPLICATION_MISMATCH"):
        _verified_archive(target, owner_hash, {**ledger, "app_name": "Other"})


def test_normal_workflow_archives_before_uploading_exact_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = UploadTarget("PitchPan", "user", "submission-1")
    archive = {
        "path": "/Users/user/Library/Developer/Xcode/Archives/utm-22/one.xcarchive",
        "app_name": "PitchPan",
        "bundle_id": "io.pitchpan.example",
        "version": "1.2.3",
        "build": "42",
    }
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        utm_22_upload,
        "_install_distributor",
        lambda user, ip: "/Users/user/Downloads/utm_22_distribute.mjs",
    )
    monkeypatch.setattr(
        utm_22_upload,
        "_install_archive_helper",
        lambda user, ip: "/Users/user/Downloads/utm_22_archive.py",
    )

    def create(target_arg, ip, helper, wait_seconds, *, game_center_recovery=False):
        calls.append(("archive", helper))
        return archive, "/Users/user/Downloads/apple-store-bm/config/prod.yml"

    def upload(target_arg, ip, distributor, archive_arg, config, wait_seconds):
        calls.append(("upload", archive_arg))
        return "verified"

    monkeypatch.setattr(utm_22_upload, "_create_or_resume_archive", create)
    monkeypatch.setattr(utm_22_upload, "_run_upload", upload)

    _run_workflow(target, "192.168.64.68", 1800, archive_path=None)

    assert calls == [
        ("archive", "/Users/user/Downloads/utm_22_archive.py"),
        ("upload", archive),
    ]


def test_only_exact_game_center_upload_error_allows_recovery() -> None:
    exact = "You must add the com.apple.developer.game-center key in Xcode."

    assert classify_upload_failure(f"prefix\n{exact}\nsuffix") == "game_center_retry"
    assert classify_upload_failure(exact.replace("Xcode.", "Xcode")) == "terminal"
    assert classify_upload_failure("missing another entitlement") == "terminal"


def test_workflow_runs_game_center_recovery_at_most_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = UploadTarget("PitchPan", "user", "submission-1")
    base = {
        "path": "/Archives/base.xcarchive",
        "version": "1.2.3",
        "build": "42",
    }
    recovered = {
        "path": "/Archives/recovered.xcarchive",
        "version": "1.2.3",
        "build": "43",
    }
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(utm_22_upload, "_install_distributor", lambda user, ip: "/dist")
    monkeypatch.setattr(
        utm_22_upload, "_install_archive_helper", lambda user, ip: "/archive"
    )

    def create(target_arg, ip, helper, wait_seconds, *, game_center_recovery=False):
        calls.append(("archive", game_center_recovery))
        return (recovered if game_center_recovery else base), "/config"

    upload_results = iter(("game_center_retry", "verified"))

    def upload(target_arg, ip, distributor, archive, config, wait_seconds):
        calls.append(("upload", archive["build"]))
        return next(upload_results)

    monkeypatch.setattr(utm_22_upload, "_create_or_resume_archive", create)
    monkeypatch.setattr(utm_22_upload, "_run_upload", upload)

    _run_workflow(target, "192.168.64.68", 1800, archive_path=None)

    assert calls == [
        ("archive", False),
        ("upload", "42"),
        ("archive", True),
        ("upload", "43"),
    ]


def test_archive_start_nonzero_reconciles_existing_verified_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = UploadTarget("PitchPan", "user", "submission-1")
    owner_hash = hashlib.sha256(b"submission-1").hexdigest()[:16]
    ledger = {
        "owner_hash": owner_hash,
        "app_name": "PitchPan",
        "state": "verified",
        "archive_path": (
            "/Users/user/Library/Developer/Xcode/Archives/utm-22/"
            f"{owner_hash}-1.2.3-42.xcarchive"
        ),
        "bundle_id": "io.pitchpan.example",
        "version": "1.2.3",
        "build": "42",
    }
    monkeypatch.setattr(
        utm_22_upload,
        "_run_ssh",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        utm_22_upload,
        "_probe_archive",
        lambda *args, **kwargs: (ledger, False),
    )

    archive, config = _create_or_resume_archive(
        target,
        "192.168.64.68",
        "/Users/user/Downloads/utm_22_archive.py",
        1800,
    )

    assert archive["path"] == ledger["archive_path"]
    assert config.endswith("/apple-store-bm/config/prod.yml")


def test_upload_node_process_uses_environment_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def runner(command, **kwargs):
        observed["command"] = command
        return SimpleNamespace(
            returncode=0,
            stdout=(
                "BUILD_UPLOAD_FINAL_STATE=COMPLETE\nBUILD_PROCESSING_STATE=VALID\n"
            ),
        )

    monkeypatch.setattr(utm_22_upload.subprocess, "run", runner)
    monkeypatch.setattr(utm_22_upload, "password_environment", lambda: {})

    _run_upload(
        UploadTarget("SlopeRight", "gvby", "manual:SlopeRight-gvby"),
        "192.168.64.68",
        "/Users/example/Downloads/utm_22_distribute.mjs",
        {
            "path": "/Archives/SlopeRight.xcarchive",
            "version": "1.0",
            "build": "1",
        },
        "/Users/example/Downloads/apple-store-bm/config/prod.yml",
        1800,
    )

    remote_command = observed["command"][-1]
    assert remote_command.startswith(
        "/usr/bin/env NODE_USE_ENV_PROXY=1 /usr/local/bin/node "
    )


def test_public_entry_emits_full_skill_success_marker(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = UploadTarget("PitchPan", "user", "manual:PitchPan-user")
    monkeypatch.setattr(utm_22_upload, "resolve_manual_target", lambda *args: target)
    monkeypatch.setattr(
        utm_22_upload,
        "require_exact_bound_vm",
        lambda *args: object(),
    )
    monkeypatch.setattr(
        utm_22_upload,
        "resolve_exact_vm_ip",
        lambda bound: "192.168.64.68",
    )
    monkeypatch.setattr(
        utm_22_upload,
        "_run_ssh",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="user\n", stderr=""
        ),
    )
    monkeypatch.setattr(utm_22_upload, "_run_workflow", lambda *args, **kwargs: None)

    assert utm_22_upload.main(["--target", "PitchPan-user"]) == 0
    assert "UTM_22=verified" in capsys.readouterr().out


def test_resolve_run_target_requires_one_owned_exact_binding() -> None:
    payload = {
        "runs": [
            {
                "id": "submission-1",
                "app_name": "PitchPan",
                "vm_name": "user",
                "host_machine": "host-a",
                "submission_data": {
                    "app_name": "PitchPan",
                    "host_machine": "host-a",
                },
            }
        ]
    }

    target = resolve_run_target(payload, "submission-1", "host-a")

    assert target.app_name == "PitchPan"
    assert target.vm_name == "user"
    assert target.attempt_owner == "submission-1"


def test_resolve_run_target_rejects_host_mismatch() -> None:
    payload = {
        "runs": [
            {
                "id": "submission-1",
                "app_name": "PitchPan",
                "vm_name": "user",
                "submission_data": {
                    "app_name": "PitchPan",
                    "host_machine": "host-b",
                },
            }
        ]
    }

    with pytest.raises(UploadTargetError, match="RUN_HOST_OWNERSHIP_MISMATCH"):
        resolve_run_target(payload, "submission-1", "host-a")


def test_resolve_manual_target_matches_full_app_vm_identity(tmp_path: Path) -> None:
    database = tmp_path / "vm-inventory.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE vm_inventory "
            "(vm_name TEXT, application_name TEXT, status TEXT, "
            "directory_present INTEGER, reusable INTEGER, available INTEGER)"
        )
        connection.execute(
            "INSERT INTO vm_inventory VALUES (?, ?, ?, ?, ?, ?)",
            ("user", "Pitch-Pan", "complete", 1, 0, 0),
        )

    target = resolve_manual_target(database, "Pitch-Pan-user")

    assert target.app_name == "Pitch-Pan"
    assert target.vm_name == "user"
    assert target.attempt_owner == "manual:Pitch-Pan-user"


def test_resolve_manual_target_rejects_unbound_or_non_complete_vm(
    tmp_path: Path,
) -> None:
    database = tmp_path / "vm-inventory.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE vm_inventory "
            "(vm_name TEXT, application_name TEXT, status TEXT, "
            "directory_present INTEGER, reusable INTEGER, available INTEGER)"
        )
        connection.execute(
            "INSERT INTO vm_inventory VALUES (?, ?, ?, ?, ?, ?)",
            ("user", "PitchPan", "complete", 1, 0, 1),
        )

    with pytest.raises(UploadTargetError, match="TARGET_MATCH_COUNT=0"):
        resolve_manual_target(database, "PitchPan-user")


def test_choose_archive_requires_one_app_and_bundle_match() -> None:
    candidates = [
        {
            "path": "/Archives/PitchPan.xcarchive",
            "app_name": "PitchPan",
            "bundle_id": "io.pitchpan.example",
            "version": "1.0.0",
            "build": "1",
        },
        {
            "path": "/Archives/Other.xcarchive",
            "app_name": "Other",
            "bundle_id": "io.other.example",
            "version": "1.0.0",
            "build": "1",
        },
    ]

    selected = choose_archive(candidates, "PitchPan", "io.pitchpan.example")

    assert selected["path"] == "/Archives/PitchPan.xcarchive"


def test_choose_archive_never_guesses_latest_when_multiple_match() -> None:
    candidates = [
        {
            "path": f"/Archives/PitchPan-{index}.xcarchive",
            "app_name": "PitchPan",
            "bundle_id": "io.pitchpan.example",
            "version": "1.0.0",
            "build": "1",
        }
        for index in (1, 2)
    ]

    with pytest.raises(UploadTargetError, match="ARCHIVE_MATCH_COUNT=2"):
        choose_archive(candidates, "PitchPan", "io.pitchpan.example")


def test_choose_archive_accepts_one_exact_path_when_multiple_match() -> None:
    candidates = [
        {
            "path": f"/Archives/PitchPan-{index}.xcarchive",
            "app_name": "PitchPan",
            "bundle_id": "io.pitchpan.example",
            "version": "1.0.0",
            "build": "2",
        }
        for index in (1, 2)
    ]

    selected = choose_archive(
        candidates,
        "PitchPan",
        "io.pitchpan.example",
        archive_path="/Archives/PitchPan-2.xcarchive",
    )

    assert selected["path"] == "/Archives/PitchPan-2.xcarchive"


def test_choose_archive_rejects_nonmatching_exact_path() -> None:
    candidates = [
        {
            "path": "/Archives/PitchPan-2.xcarchive",
            "app_name": "PitchPan",
            "bundle_id": "io.pitchpan.example",
            "version": "1.0.0",
            "build": "2",
        }
    ]

    with pytest.raises(UploadTargetError, match="ARCHIVE_MATCH_COUNT=0"):
        choose_archive(
            candidates,
            "PitchPan",
            "io.pitchpan.example",
            archive_path="/Archives/PitchPan-missing.xcarchive",
        )


def test_archive_path_is_manual_target_only() -> None:
    with pytest.raises(SystemExit):
        _parse_args(
            [
                "--run-id",
                "submission-1",
                "--archive-path",
                "/Archives/PitchPan-2.xcarchive",
            ]
        )


def test_ssh_recovery_resumes_same_attempt_after_transport_loss() -> None:
    assert (
        ssh_recovery_action(255, attempt_exists=True, remote_process_running=False)
        == "resume_attempt"
    )
    assert (
        ssh_recovery_action(255, attempt_exists=False, remote_process_running=True)
        == "wait_same_process"
    )
    assert (
        ssh_recovery_action(255, attempt_exists=False, remote_process_running=False)
        == "prove_not_executed"
    )
    assert (
        ssh_recovery_action(1, attempt_exists=True, remote_process_running=False)
        == "stop"
    )
