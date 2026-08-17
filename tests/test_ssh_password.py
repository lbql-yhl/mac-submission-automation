from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = ROOT / "scripts" / "ssh_password.py"
    assert path.is_file(), "shared fixed-password SSH module is missing"
    spec = importlib.util.spec_from_file_location("ssh_password_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ssh_uses_only_fixed_password_authentication() -> None:
    module = _load_module()
    args = module.ssh_args("wsyy", "192.168.64.26")
    joined = " ".join(args)
    assert "BatchMode=no" in joined
    assert "PubkeyAuthentication=no" in joined
    assert "PreferredAuthentications=password,keyboard-interactive" in joined
    assert "NumberOfPasswordPrompts=1" in joined
    assert " -i " not in f" {joined} "


def test_askpass_environment_is_forced_and_not_in_argv(tmp_path: Path) -> None:
    module = _load_module()
    env = module.password_environment(runtime_dir=tmp_path)
    helper = Path(env["SSH_ASKPASS"])
    assert env["SSH_ASKPASS_REQUIRE"] == "force"
    assert helper.is_file() and not helper.is_symlink()
    assert helper.stat().st_mode & 0o777 == 0o700
    assert module.FIXED_PASSWORD not in " ".join(module.ssh_args("wsyy", "192.168.64.26"))
