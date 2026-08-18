from pathlib import Path
import importlib.util
import subprocess

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


def test_askpass_reads_child_environment_without_exposing_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    synthetic_value = "9072"
    monkeypatch.setenv("SUBMISSION_GUEST_PASSWORD", synthetic_value)
    env = module.password_environment(runtime_dir=tmp_path)
    helper = Path(env["SSH_ASKPASS"])
    assert env["SSH_ASKPASS_REQUIRE"] == "force"
    assert env["SUBMISSION_GUEST_PASSWORD"] == synthetic_value
    assert helper.is_file() and not helper.is_symlink()
    assert helper.stat().st_mode & 0o777 == 0o700
    assert tmp_path.stat().st_mode & 0o777 == 0o700
    assert helper.name == "askpass"
    helper_source = helper.read_text(encoding="utf-8")
    assert "SUBMISSION_GUEST_PASSWORD" in helper_source
    assert synthetic_value not in helper_source
    command = module.ssh_args("wsyy", "192.168.64.26")
    assert synthetic_value not in " ".join(command)
    completed = subprocess.run(
        [str(helper)], env=env, text=True, capture_output=True, check=True
    )
    assert completed.stdout == synthetic_value + "\n"


def test_password_environment_fails_closed_when_configuration_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load_module()
    error = RuntimeError("missing required host setting: SUBMISSION_GUEST_PASSWORD")
    monkeypatch.setattr(module, "guest_password", lambda: (_ for _ in ()).throw(error))

    with pytest.raises(RuntimeError, match="^missing required host setting"):
        module.password_environment(runtime_dir=tmp_path)
