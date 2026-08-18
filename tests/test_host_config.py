from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import stat

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "services" / "host_config.py"
TEST_SETTING = "HOST_CONFIG_TEST_SETTING"


def load_module():
    assert MODULE.is_file(), "host configuration accessors are missing"
    spec = importlib.util.spec_from_file_location("host_config_under_test", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_process_environment_precedes_dotenv_without_mutating_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    env_path = tmp_path / ".env"
    env_path.write_text(f"{TEST_SETTING}=from-file\n", encoding="utf-8")
    monkeypatch.setenv(TEST_SETTING, "  from-process  ")
    before = dict(os.environ)

    assert module.optional_setting(TEST_SETTING, env_path=env_path) == "from-process"
    assert dict(os.environ) == before


def test_explicit_environment_is_the_only_configuration_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    env_path = tmp_path / ".env"
    env_path.write_text(f"{TEST_SETTING}=from-file\n", encoding="utf-8")
    monkeypatch.setenv(TEST_SETTING, "from-process")
    supplied = {TEST_SETTING: "  from-mapping  "}

    assert (
        module.optional_setting(TEST_SETTING, environ=supplied, env_path=env_path)
        == "from-mapping"
    )
    assert module.optional_setting(TEST_SETTING, environ={}, env_path=env_path) == ""
    assert supplied == {TEST_SETTING: "  from-mapping  "}


def test_dotenv_is_a_read_only_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    env_path = tmp_path / ".env"
    env_path.write_text(
        f"# host-only settings\n{TEST_SETTING}=  from-file  \n",
        encoding="utf-8",
    )
    monkeypatch.delenv(TEST_SETTING, raising=False)
    before = dict(os.environ)

    assert module.optional_setting(TEST_SETTING, env_path=env_path) == "from-file"
    assert dict(os.environ) == before


def test_dotenv_symlink_is_rejected_without_reading_or_modifying_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    synthetic_value = "9072"
    external = tmp_path / "external.env"
    external.write_text(f"{TEST_SETTING}={synthetic_value}\n", encoding="utf-8")
    external.chmod(0o640)
    env_path = tmp_path / ".env"
    env_path.symlink_to(external)
    monkeypatch.delenv(TEST_SETTING, raising=False)
    before_mode = stat.S_IMODE(external.stat().st_mode)

    with pytest.raises(module.ConfigurationError) as captured:
        module.optional_setting(TEST_SETTING, env_path=env_path)

    assert synthetic_value not in str(captured.value)
    assert stat.S_IMODE(external.stat().st_mode) == before_mode
    assert external.read_text(encoding="utf-8") == f"{TEST_SETTING}={synthetic_value}\n"


def test_required_setting_fails_with_only_the_setting_name() -> None:
    module = load_module()
    with pytest.raises(
        module.ConfigurationError,
        match=f"^missing required host setting: {TEST_SETTING}$",
    ) as captured:
        module.required_setting(TEST_SETTING, environ={TEST_SETTING: "  "})

    assert "secret" not in str(captured.value).casefold()


def test_guest_password_reads_the_required_host_setting() -> None:
    module = load_module()
    synthetic_value = "9072"

    assert (
        module.guest_password(
            environ={"SUBMISSION_GUEST_PASSWORD": f"  {synthetic_value}  "}
        )
        == synthetic_value
    )


@pytest.mark.parametrize("invalid", ("12", "12345", "12a4", "１２３４"))
def test_guest_password_rejects_non_four_ascii_digits_without_echo(
    invalid: str,
) -> None:
    module = load_module()

    with pytest.raises(module.ConfigurationError) as captured:
        module.guest_password(environ={"SUBMISSION_GUEST_PASSWORD": invalid})

    assert invalid not in str(captured.value)
