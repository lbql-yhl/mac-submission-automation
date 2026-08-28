from __future__ import annotations

import importlib
import stat
from pathlib import Path

import pytest

from services import feishu_supervisor


def singleton_module():
    return importlib.import_module("services.supervisor_singleton")


def test_supervisor_lock_is_regular_private_and_nonblocking(tmp_path: Path) -> None:
    singleton = singleton_module()
    lock_path = tmp_path / "feishu_supervisor.lock"

    with singleton.supervisor_lock(lock_path):
        metadata = lock_path.lstat()
        assert stat.S_ISREG(metadata.st_mode)
        assert stat.S_IMODE(metadata.st_mode) == 0o600
        assert metadata.st_nlink == 1
        with pytest.raises(singleton.SupervisorAlreadyRunning):
            with singleton.supervisor_lock(lock_path):
                pytest.fail("a second supervisor acquired the singleton lock")

    with singleton.supervisor_lock(lock_path):
        pass


def test_supervisor_lock_rejects_symlink_without_changing_target(
    tmp_path: Path,
) -> None:
    singleton = singleton_module()
    target = tmp_path / "outside"
    target.write_text("preserve", encoding="utf-8")
    target.chmod(0o644)
    lock_path = tmp_path / "feishu_supervisor.lock"
    lock_path.symlink_to(target)

    with pytest.raises(singleton.SupervisorLockError):
        with singleton.supervisor_lock(lock_path):
            pytest.fail("a symlink was accepted as the supervisor lock")

    assert target.read_text(encoding="utf-8") == "preserve"
    assert stat.S_IMODE(target.stat().st_mode) == 0o644


def test_supervisor_main_holds_lock_for_entire_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    singleton = singleton_module()
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    lock_path = runtime / "feishu_supervisor.lock"
    events: list[str] = []

    class FakeSupervisor:
        def run(self) -> int:
            events.append("run")
            with pytest.raises(singleton.SupervisorAlreadyRunning):
                with singleton.supervisor_lock(lock_path):
                    pytest.fail("main released its singleton lock before run returned")
            return 23

    monkeypatch.setattr(feishu_supervisor, "RUNTIME_DIR", runtime)
    monkeypatch.setattr(feishu_supervisor, "harden_runtime_metadata", lambda: None)
    monkeypatch.setattr(feishu_supervisor, "load_dotenv", lambda _path: None)
    monkeypatch.setattr(feishu_supervisor, "Supervisor", FakeSupervisor)

    assert feishu_supervisor.main() == 23
    assert events == ["run"]
    with singleton.supervisor_lock(lock_path):
        pass


def test_second_supervisor_exits_nonzero_without_constructing_worker_supervisor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    singleton = singleton_module()
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    lock_path = runtime / "feishu_supervisor.lock"

    class ForbiddenSupervisor:
        def __init__(self) -> None:
            pytest.fail("the second process constructed Supervisor")

    monkeypatch.setattr(feishu_supervisor, "RUNTIME_DIR", runtime)
    monkeypatch.setattr(feishu_supervisor, "harden_runtime_metadata", lambda: None)
    monkeypatch.setattr(feishu_supervisor, "load_dotenv", lambda _path: None)
    monkeypatch.setattr(feishu_supervisor, "Supervisor", ForbiddenSupervisor)

    with singleton.supervisor_lock(lock_path):
        result = feishu_supervisor.main()

    assert result != 0
    assert "already running" in capsys.readouterr().err.lower()


def test_supervisor_lock_fails_closed_on_windows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    singleton = singleton_module()
    monkeypatch.setattr(singleton.os, "name", "nt")

    with pytest.raises(singleton.SupervisorLockError, match="not supported"):
        with singleton.supervisor_lock(tmp_path / "feishu_supervisor.lock"):
            pytest.fail("Windows started without a safe singleton lock")
