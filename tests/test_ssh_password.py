from pathlib import Path
import importlib.util
import os
import subprocess
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = ROOT / "scripts" / "ssh_password.py"
    assert path.is_file(), "shared configured-password SSH module is missing"
    spec = importlib.util.spec_from_file_location("ssh_password_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ssh_uses_only_configured_password_authentication() -> None:
    module = _load_module()
    args = module.ssh_args("wsyy", "192.168.64.26")
    joined = " ".join(args)
    assert "BatchMode=no" in joined
    assert "PubkeyAuthentication=no" in joined
    assert "PreferredAuthentications=password,keyboard-interactive" in joined
    assert "NumberOfPasswordPrompts=1" in joined
    assert " -i " not in f" {joined} "


def test_askpass_reads_one_use_broker_without_exposing_password_in_child_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    synthetic_value = "9072"
    monkeypatch.setenv("SUBMISSION_GUEST_PASSWORD", synthetic_value)
    env = module.password_environment(runtime_dir=tmp_path)
    helper = Path(env["SSH_ASKPASS"])
    assert env["SSH_ASKPASS_REQUIRE"] == "force"
    assert "SUBMISSION_GUEST_PASSWORD" not in env
    assert env["SUBMISSION_SSH_ASKPASS_SOCKET"]
    assert env["SUBMISSION_SSH_ASKPASS_CAPABILITY"]
    assert helper.is_file() and not helper.is_symlink()
    assert helper.stat().st_mode & 0o777 == 0o700
    assert tmp_path.stat().st_mode & 0o777 == 0o700
    assert helper.name == "askpass"
    helper_source = helper.read_text(encoding="utf-8")
    assert "SUBMISSION_GUEST_PASSWORD" not in helper_source
    assert synthetic_value not in helper_source
    command = module.ssh_args("wsyy", "192.168.64.26")
    assert synthetic_value not in " ".join(command)
    assert synthetic_value not in "\0".join(f"{key}={value}" for key, value in env.items())
    completed = subprocess.run(
        [str(helper)], env=env, text=True, capture_output=True, check=True
    )
    assert completed.stdout == synthetic_value + "\n"
    for _ in range(100):
        if not Path(env["SUBMISSION_SSH_ASKPASS_SOCKET"]).exists():
            break
        time.sleep(0.01)
    assert not Path(env["SUBMISSION_SSH_ASKPASS_SOCKET"]).exists()

    replay = subprocess.run([str(helper)], env=env, text=True, capture_output=True)
    assert replay.returncode != 0
    assert synthetic_value not in replay.stdout + replay.stderr
    for entry in tmp_path.iterdir():
        if entry.is_file():
            assert synthetic_value not in entry.read_text(encoding="utf-8")


def test_password_broker_rejects_wrong_capability_without_disclosing_value(
    tmp_path: Path,
) -> None:
    module = _load_module()
    synthetic_value = "9072"
    env = module.password_environment(
        {"PATH": os.environ["PATH"], "SUBMISSION_GUEST_PASSWORD": synthetic_value},
        runtime_dir=tmp_path,
    )
    env["SUBMISSION_SSH_ASKPASS_CAPABILITY"] = "wrong-capability"

    completed = subprocess.run(
        [env["SSH_ASKPASS"]], env=env, text=True, capture_output=True
    )

    assert completed.returncode != 0
    assert synthetic_value not in completed.stdout + completed.stderr


def test_password_broker_times_out_and_removes_its_socket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_BROKER_TIMEOUT_SECONDS", 0.05)
    env = module.password_environment(
        {"SUBMISSION_GUEST_PASSWORD": "9072"}, runtime_dir=tmp_path
    )
    socket_path = Path(env["SUBMISSION_SSH_ASKPASS_SOCKET"])
    assert socket_path.exists()

    for _ in range(100):
        if not socket_path.exists():
            break
        time.sleep(0.01)

    assert not socket_path.exists()


def test_runtime_directory_symlink_is_rejected_without_touching_external_target(
    tmp_path: Path,
) -> None:
    module = _load_module()
    external = tmp_path / "external"
    external.mkdir(mode=0o755)
    marker = external / "marker.txt"
    marker.write_text("leave-me-alone", encoding="utf-8")
    external.chmod(0o755)
    runtime_link = tmp_path / "runtime-link"
    runtime_link.symlink_to(external, target_is_directory=True)
    before_mode = external.stat().st_mode & 0o777

    with pytest.raises(module.SSHPasswordError, match="runtime directory is unsafe"):
        module.password_environment(
            {"SUBMISSION_GUEST_PASSWORD": "9072"}, runtime_dir=runtime_link
        )

    assert external.stat().st_mode & 0o777 == before_mode
    assert marker.read_text(encoding="utf-8") == "leave-me-alone"
    assert sorted(path.name for path in external.iterdir()) == ["marker.txt"]


def test_explicit_password_environment_does_not_fall_back_to_ambient_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    monkeypatch.setenv("SUBMISSION_GUEST_PASSWORD", "9072")

    with pytest.raises(RuntimeError, match="missing required host setting"):
        module.password_environment({"PATH": os.environ["PATH"]}, runtime_dir=tmp_path)


def test_password_environment_fails_closed_when_configuration_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    error = RuntimeError("missing required host setting: SUBMISSION_GUEST_PASSWORD")
    monkeypatch.setattr(
        module,
        "guest_password",
        lambda **_kwargs: (_ for _ in ()).throw(error),
    )

    with pytest.raises(RuntimeError, match="^missing required host setting"):
        module.password_environment(runtime_dir=tmp_path)
