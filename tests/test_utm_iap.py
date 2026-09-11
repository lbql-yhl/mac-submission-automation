from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import pytest

from scripts import utm_iap
from scripts import utm_iap_attempt as attempts
from scripts import preflight


IAP_LOG = "增强版内购创建完成！\n统计信息: 共处理 2 个产品\n"
FINISHED = (
    "ATTEMPT_ID=" + "b" * 32 + "\n"
    "RUN_STATE=finished\nREMOTE_IAP_EXIT=0\nREMOTE_TEE_EXIT=0\n"
)


def test_utm_iap_is_standalone_not_mainline() -> None:
    assert "utm-iap" in preflight.STANDALONE
    assert "utm-iap" not in preflight.ORDERED
    assert len(preflight.ORDERED) == 16
    skill = Path(__file__).resolve().parents[1] / "skills" / "utm-iap" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert "scripts/utm_iap.py" in text
    assert "UTM_IAP=verified" in text
    assert "optional" in text.casefold() or "按需" in text or "Optional" in text
    assert "utm-image" not in text.split("## Result and handoff", 1)[-1]


def test_classify_requires_completion_and_positive_product_count() -> None:
    result = attempts.classify_attempt(
        IAP_LOG,
        FINISHED,
        process_running=False,
        expected_attempt_id="b" * 32,
    )
    assert result.state == "verified"
    assert result.product_count == 2
    incomplete = attempts.classify_attempt(
        "增强版内购创建完成！\n",
        FINISHED,
        process_running=False,
        expected_attempt_id="b" * 32,
    )
    assert incomplete.state != "verified"
    zero = attempts.classify_attempt(
        "增强版内购创建完成！\n统计信息: 共处理 0 个产品\n",
        FINISHED,
        process_running=False,
        expected_attempt_id="b" * 32,
    )
    assert zero.state != "verified"


def test_attempt_ledger_is_independent_of_utm18_skip_flag(tmp_path) -> None:
    attempt = attempts.create_attempt(
        tmp_path, run_id="run-demo", vm_name="abcd", vm_ip="192.0.2.10"
    )
    loaded = attempts.load_single_attempt(tmp_path, "run-demo")
    assert loaded is not None
    assert loaded.attempt_id == attempt.attempt_id
    assert not hasattr(loaded, "skip_iap")
    script = attempts._remote_run_script(attempt)
    assert "iap-enhanced" in script
    assert "UTM_SKIP_IAP" not in script
    assert "utm-iap-" in attempt.log_path


def test_public_selector_matches_other_skills() -> None:
    parser = utm_iap.build_parser()
    args = parser.parse_args(
        [
            "--page-title",
            "Demo-abcd",
            "--vm-name",
            "abcd",
            "--vm-ip",
            "192.0.2.10",
            "--vm-user",
            "abcd",
        ]
    )
    assert args.page_title == "Demo-abcd"
    assert args.run_id is None
    run_args = parser.parse_args(
        [
            "--run-id",
            "run-12345678",
            "--vm-name",
            "abcd",
            "--vm-ip",
            "192.0.2.10",
            "--vm-user",
            "abcd",
        ]
    )
    assert run_args.run_id == "run-12345678"


def test_main_prints_clean_success(monkeypatch, capsys) -> None:
    monkeypatch.setattr(utm_iap, "run", lambda args: 0)
    assert (
        utm_iap.main(
            [
                "--page-title",
                "Demo-abcd",
                "--vm-name",
                "abcd",
                "--vm-ip",
                "192.0.2.10",
                "--vm-user",
                "abcd",
            ]
        )
        == 0
    )
    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "开始执行：utm-iap",
        "执行成功：utm-iap；UTM_IAP=verified",
    ]


def test_resume_verified_attempt(monkeypatch, tmp_path) -> None:
    attempt = attempts.create_attempt(
        tmp_path, run_id="run-demo", vm_name="abcd", vm_ip="192.0.2.10"
    )
    attempts.mark_attempt(attempt, state="verified")
    monkeypatch.setattr(
        utm_iap,
        "api_from_env",
        lambda: SimpleNamespace(
            verify_parent=lambda title: title,
            read_field=lambda *args, **kwargs: "Demo",
        ),
    )
    monkeypatch.setattr(
        utm_iap,
        "resolve_direct_context",
        lambda **kwargs: SimpleNamespace(
            context_id="run-demo",
            parent_title="Host",
            page_title="Demo-abcd",
            app_name="Demo",
        ),
    )
    args = SimpleNamespace(
        run_id=None,
        page_title="Demo-abcd",
        vm_name="abcd",
        vm_user="abcd",
        vm_ip="192.0.2.10",
        attempts_root=tmp_path,
    )
    assert utm_iap.run(args) == 0


def test_run_marks_verified_after_remote_success(monkeypatch, tmp_path) -> None:
    created = {}

    def fake_create(root, **kwargs):
        attempt = attempts.create_attempt(root, **kwargs)
        created["attempt"] = attempt
        return attempt

    monkeypatch.setattr(utm_iap, "create_attempt", fake_create)
    monkeypatch.setattr(utm_iap, "precommit_remote", lambda attempt: None)
    monkeypatch.setattr(utm_iap, "run_remote", lambda attempt: 0)
    monkeypatch.setattr(
        utm_iap,
        "inspect_remote",
        lambda attempt: (
            IAP_LOG,
            (
                f"ATTEMPT_ID={attempt.attempt_id}\n"
                "RUN_STATE=finished\nREMOTE_IAP_EXIT=0\nREMOTE_TEE_EXIT=0\n"
            ),
            False,
        ),
    )
    monkeypatch.setattr(
        utm_iap,
        "api_from_env",
        lambda: SimpleNamespace(
            verify_parent=lambda title: title,
            read_field=lambda *args, **kwargs: "Demo",
        ),
    )
    monkeypatch.setattr(
        utm_iap,
        "resolve_direct_context",
        lambda **kwargs: SimpleNamespace(
            context_id="run-demo",
            parent_title="Host",
            page_title="Demo-abcd",
            app_name="Demo",
        ),
    )
    args = SimpleNamespace(
        run_id=None,
        page_title="Demo-abcd",
        vm_name="abcd",
        vm_user="abcd",
        vm_ip="192.0.2.10",
        attempts_root=tmp_path,
    )
    assert utm_iap.run(args) == 0
    loaded = attempts.load_single_attempt(tmp_path, "run-demo")
    assert loaded is not None
    assert loaded.state == "verified"
