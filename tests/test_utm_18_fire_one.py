from scripts import utm_18
from scripts.check_host_vm_dependencies import GUEST_PROBES
from scripts.utm_18_attempt import classify_attempt


SUCCESS_LOG = "增强版内购创建完成！\n统计信息: 共处理 14 个产品\n"


def test_utm_18_reuses_the_existing_authenticated_browser_session() -> None:
    source = utm_18.APPLE_EXISTING_SESSION_BRIDGE
    assert source.count("currentSessionIdentity()") == 2
    assert "connectLocalBrowser()" in source
    assert "before.edge_pid !== after.edge_pid" in source
    assert "before.edge_websocket !== after.edge_websocket" in source
    assert "before.sessionId !== after.sessionId" in source
    for forbidden in ("_ensure_apple_login", "open_url", ".goto(", ".newPage("):
        assert forbidden not in source


def test_fire_one_source_and_toolchain_are_explicit_guest_dependencies() -> None:
    fire_one_probe = dict(GUEST_PROBES)["虚拟机Fire One"]
    assert "$HOME/Downloads/Fire_One_en1.3/package.json" in fire_one_probe
    assert "$HOME/Downloads/Fire_One_en1.3/src/fill-description.ts" in fire_one_probe
    assert "$HOME/Downloads/Fire_One_en1.3/node_modules/.bin/ts-node" in fire_one_probe
    assert "/Users/" not in fire_one_probe


def test_fire_one_completion_accepts_clean_exit_or_verified_resident_process() -> None:
    attempt_id = "a" * 32
    exited = classify_attempt(
        SUCCESS_LOG,
        (
            f"ATTEMPT_ID={attempt_id}\nRUN_STATE=finished\n"
            "REMOTE_NPM_EXIT=0\nREMOTE_TEE_EXIT=0\n"
        ),
        process_running=False,
        expected_attempt_id=attempt_id,
    )
    resident = classify_attempt(
        SUCCESS_LOG,
        f"ATTEMPT_ID={attempt_id}\nRUN_STATE=running\n",
        process_running=True,
        expected_attempt_id=attempt_id,
    )

    assert (exited.state, exited.mode, exited.product_count) == (
        "verified",
        "exited_zero",
        14,
    )
    assert (resident.state, resident.mode, resident.product_count) == (
        "verified",
        "resident_after_summary",
        14,
    )
