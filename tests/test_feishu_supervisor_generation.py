from __future__ import annotations

import http.client
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import feishu_bot, feishu_supervisor


class HealthResponse:
    def __init__(self, generation: str, *, status: int = 200) -> None:
        self.status = status
        self._body = json.dumps(
            {"ok": True, "generation": generation}
        ).encode("utf-8")

    def __enter__(self) -> HealthResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class TruncatedHealthResponse(HealthResponse):
    def read(self) -> bytes:
        raise http.client.IncompleteRead(b'{"ok":')


def test_deployment_generation_changes_with_bot_service_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "project"
    services = root / "services"
    services.mkdir(parents=True)
    bot_source = services / "feishu_bot.py"
    bot_source.write_text("VERSION = 1\n", encoding="utf-8")
    monkeypatch.setattr(feishu_supervisor, "ROOT", root)

    first = feishu_supervisor.deployment_generation()
    bot_source.write_text("VERSION = 2\n", encoding="utf-8")

    assert feishu_supervisor.deployment_generation() != first


def test_health_rejects_stale_deployment_generation_before_http_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    supervisor.active_generation = "generation-at-process-start"
    monkeypatch.setattr(
        feishu_supervisor,
        "deployment_generation",
        lambda: "new-generation-on-disk",
    )
    monkeypatch.setattr(
        feishu_supervisor,
        "build_no_proxy_opener",
        lambda: pytest.fail("stale generation must fail before an HTTP 200 probe"),
    )

    assert supervisor.health_ok() is False


def test_public_health_rejects_stale_deployment_generation_before_http_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    supervisor.last_public_url = "https://current.trycloudflare.com"
    supervisor.active_generation = "generation-at-process-start"
    monkeypatch.setattr(
        feishu_supervisor,
        "deployment_generation",
        lambda: "new-generation-on-disk",
    )
    monkeypatch.setattr(
        feishu_supervisor.request,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail(
            "stale generation must fail before a public HTTP 200 probe"
        ),
    )

    assert supervisor.public_health_ok() is False


def test_health_rejects_http_200_from_stale_worker_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    supervisor.active_generation = "current-generation"
    monkeypatch.setattr(
        feishu_supervisor,
        "deployment_generation",
        lambda: "current-generation",
    )

    class StaleWorkerOpener:
        def open(self, *_args: object, **_kwargs: object) -> HealthResponse:
            return HealthResponse("stale-generation")

    monkeypatch.setattr(
        feishu_supervisor,
        "build_no_proxy_opener",
        lambda: StaleWorkerOpener(),
    )

    assert supervisor.health_ok() is False


def test_public_health_accepts_only_active_worker_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    supervisor.last_public_url = "https://current.trycloudflare.com"
    supervisor.active_generation = "current-generation"
    monkeypatch.setattr(
        feishu_supervisor,
        "deployment_generation",
        lambda: "current-generation",
    )
    responses = iter(
        (
            HealthResponse("stale-generation"),
            HealthResponse("current-generation"),
        )
    )
    monkeypatch.setattr(
        feishu_supervisor.request,
        "urlopen",
        lambda *_args, **_kwargs: next(responses),
    )

    assert supervisor.public_health_ok() is False
    assert supervisor.public_health_ok() is True


def test_local_health_treats_a_truncated_response_as_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    supervisor.active_generation = "current-generation"
    monkeypatch.setattr(
        feishu_supervisor,
        "deployment_generation",
        lambda: "current-generation",
    )

    class TruncatedWorkerOpener:
        def open(self, *_args: object, **_kwargs: object) -> HealthResponse:
            return TruncatedHealthResponse("current-generation")

    monkeypatch.setattr(
        feishu_supervisor,
        "build_no_proxy_opener",
        lambda: TruncatedWorkerOpener(),
    )

    assert supervisor.health_ok() is False


def test_public_health_treats_a_truncated_response_as_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    supervisor.last_public_url = "https://current.trycloudflare.com"
    supervisor.active_generation = "current-generation"
    monkeypatch.setattr(
        feishu_supervisor,
        "deployment_generation",
        lambda: "current-generation",
    )
    monkeypatch.setattr(
        feishu_supervisor.request,
        "urlopen",
        lambda *_args, **_kwargs: TruncatedHealthResponse("current-generation"),
    )

    assert supervisor.public_health_ok() is False


def test_health_response_uses_generation_captured_at_worker_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = feishu_bot.load_config(
        environ={},
        env_path=tmp_path / "missing.env",
    )
    generation_calls: list[str] = []
    captured: dict[str, Any] = {}

    def calculate_generation(_root: Path) -> str:
        generation_calls.append("startup")
        return "worker-start-generation"

    class FakeServer:
        def __init__(self, _address: tuple[str, int], handler: type) -> None:
            captured["handler"] = handler

        def serve_forever(self) -> None:
            return None

        def server_close(self) -> None:
            return None

    monkeypatch.setattr(
        feishu_bot,
        "calculate_deployment_generation",
        calculate_generation,
        raising=False,
    )
    monkeypatch.setattr(feishu_bot, "RUNTIME_DIR", tmp_path / "runtime")
    monkeypatch.setattr(feishu_bot, "ReusableThreadingHTTPServer", FakeServer)

    assert feishu_bot.serve(SimpleNamespace(host="127.0.0.1", port=18787), config) == 0
    assert generation_calls == ["startup"]

    handler_type = captured["handler"]
    handler = object.__new__(handler_type)
    handler.path = "/health"
    responses: list[dict[str, Any]] = []
    handler._json_response = lambda status, payload: responses.append(  # type: ignore[method-assign]
        {"status": status, "payload": payload}
    )
    monkeypatch.setattr(
        feishu_bot,
        "calculate_deployment_generation",
        lambda _root: pytest.fail("health requests must not read deployment sources"),
    )

    handler.do_GET()
    handler.do_GET()

    assert responses == [
        {
            "status": 200,
            "payload": {
                "ok": True,
                "generation": "worker-start-generation",
                "time": responses[0]["payload"]["time"],
            },
        },
        {
            "status": 200,
            "payload": {
                "ok": True,
                "generation": "worker-start-generation",
                "time": responses[1]["payload"]["time"],
            },
        },
    ]


def test_changed_generation_restarts_bot_ws_and_poller_as_one_cohort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    supervisor.active_generation = "old-generation"
    supervisor.bot = object()  # type: ignore[assignment]
    supervisor.ws = object()  # type: ignore[assignment]
    supervisor.poller = object()  # type: ignore[assignment]
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        supervisor,
        "terminate_proc",
        lambda name, _proc: calls.append(("stop", name)),
    )
    monkeypatch.setattr(
        supervisor,
        "start_bot",
        lambda: calls.append(("start", "bot")),
    )
    monkeypatch.setattr(
        supervisor,
        "start_ws",
        lambda: calls.append(("start", "ws")),
    )
    monkeypatch.setattr(
        supervisor,
        "start_poller",
        lambda: calls.append(("start", "poller")),
    )
    monkeypatch.setattr(feishu_supervisor.time, "sleep", lambda _seconds: None)

    supervisor.restart_bot_cohort("new-generation")

    assert supervisor.active_generation == "new-generation"
    assert calls == [
        ("stop", "poller"),
        ("stop", "ws"),
        ("stop", "bot"),
        ("start", "bot"),
        ("start", "ws"),
        ("start", "poller"),
    ]


def test_generation_change_is_reconciled_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    supervisor.active_generation = "old-generation"
    restarted: list[str] = []
    monkeypatch.setattr(
        feishu_supervisor,
        "deployment_generation",
        lambda: "new-generation",
    )
    monkeypatch.setattr(
        supervisor,
        "restart_bot_cohort",
        lambda generation: restarted.append(generation),
    )

    assert supervisor.reconcile_deployment_generation() is True
    assert restarted == ["new-generation"]


def test_worker_command_match_requires_the_exact_project_role() -> None:
    matches = getattr(feishu_supervisor, "worker_command_matches_role", None)
    assert callable(matches)

    script = str(feishu_supervisor.ROOT / "services" / "feishu_bot.py")
    python = feishu_supervisor.sys.executable
    assert matches(
        f"{python} -u {script} --host 127.0.0.1 --port 8787",
        "bot",
    )
    assert matches(f"{python} -u {script} ws", "ws")
    assert matches(f"{python} -u {script} poll", "poller")
    assert not matches(f"/other/python -u {script} ws", "ws")
    assert not matches(f"{python} -u /other/project/feishu_bot.py ws", "ws")
    assert not matches(f"{python} -u {script} ws --extra", "ws")
    assert not matches(f"{python} -u {script} --host 127.0.0.1", "bot")


def test_managed_pid_reader_accepts_a_regular_pid_file(tmp_path: Path) -> None:
    read_pid = getattr(feishu_supervisor, "read_managed_pid", None)
    assert callable(read_pid)
    pid_file = tmp_path / "worker.pid"
    pid_file.write_text("12345", encoding="ascii")

    assert read_pid(pid_file) == 12345


def test_managed_pid_reader_refuses_a_symlink(tmp_path: Path) -> None:
    read_pid = getattr(feishu_supervisor, "read_managed_pid", None)
    assert callable(read_pid)
    target = tmp_path / "target.pid"
    target.write_text("12345", encoding="ascii")
    pid_file = tmp_path / "worker.pid"
    pid_file.symlink_to(target)

    with pytest.raises(RuntimeError, match="managed pid"):
        read_pid(pid_file)


def test_startup_cleanup_fails_closed_on_an_unsafe_matched_process_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    cleanup = getattr(supervisor, "cleanup_stale_worker_cohort", None)
    assert callable(cleanup)

    pids = {
        feishu_supervisor.BOT_PID_FILE: 101,
        feishu_supervisor.WS_PID_FILE: 202,
        feishu_supervisor.POLLER_PID_FILE: 303,
    }
    script = str(feishu_supervisor.ROOT / "services" / "feishu_bot.py")
    python = feishu_supervisor.sys.executable
    commands = {
        101: f"{python} -u {script} --host 127.0.0.1 --port 8787",
        202: f"{python} -u /other/project/feishu_bot.py ws",
        303: f"{python} -u {script} poll",
    }
    terminated: list[tuple[str, int]] = []

    monkeypatch.setattr(
        feishu_supervisor,
        "read_managed_pid",
        lambda path: pids[path],
        raising=False,
    )
    monkeypatch.setattr(
        feishu_supervisor,
        "managed_process_command",
        lambda pid: commands[pid],
        raising=False,
    )
    monkeypatch.setattr(
        feishu_supervisor.os,
        "getpgid",
        lambda pid: pid if pid != 303 else 999,
    )
    monkeypatch.setattr(
        supervisor,
        "terminate_orphan_worker",
        lambda name, pid: terminated.append((name, pid)),
        raising=False,
    )

    with pytest.raises(RuntimeError, match="process group"):
        cleanup()

    assert terminated == [("bot", 101)]


def test_startup_cleanup_fails_closed_when_a_live_pid_cannot_be_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    monkeypatch.setattr(
        feishu_supervisor,
        "read_managed_pid",
        lambda path: 101 if path == feishu_supervisor.BOT_PID_FILE else 0,
    )
    monkeypatch.setattr(
        feishu_supervisor,
        "managed_process_command",
        lambda _pid: "",
    )
    monkeypatch.setattr(
        feishu_supervisor,
        "managed_process_exists",
        lambda _pid: True,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="verify stale bot"):
        supervisor.cleanup_stale_worker_cohort()


def test_startup_cleanup_fails_closed_without_exact_process_inspection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    monkeypatch.setattr(feishu_supervisor.os, "name", "nt")

    with pytest.raises(RuntimeError, match="not supported"):
        supervisor.cleanup_stale_worker_cohort()


def test_stale_worker_identity_is_rechecked_before_term(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    monkeypatch.setattr(supervisor, "log", lambda _message: None)
    script = str(feishu_supervisor.ROOT / "services" / "feishu_bot.py")
    expected = f"{feishu_supervisor.sys.executable} -u {script} ws"
    commands = iter((expected, "/other/python -u /other/worker.py"))
    starts = iter(("start-one", "start-one"))
    monkeypatch.setattr(
        feishu_supervisor,
        "managed_process_command",
        lambda _pid: next(commands),
    )
    monkeypatch.setattr(
        feishu_supervisor,
        "managed_process_start_identity",
        lambda _pid: next(starts),
        raising=False,
    )
    monkeypatch.setattr(feishu_supervisor.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(
        feishu_supervisor.os,
        "killpg",
        lambda *_args: pytest.fail("changed process identity must not be signaled"),
    )

    with pytest.raises(RuntimeError, match="identity changed"):
        supervisor.terminate_orphan_worker("ws", 101)


def test_pid_reuse_after_term_never_receives_kill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    monkeypatch.setattr(supervisor, "log", lambda _message: None)
    script = str(feishu_supervisor.ROOT / "services" / "feishu_bot.py")
    expected = f"{feishu_supervisor.sys.executable} -u {script} poll"
    commands = iter((expected, expected, "/other/python -u /other/worker.py"))
    starts = iter(("start-one", "start-one", "start-two"))
    signals: list[int] = []
    monotonic = iter((0.0, 9.0))
    monkeypatch.setattr(
        feishu_supervisor,
        "managed_process_command",
        lambda _pid: next(commands),
    )
    monkeypatch.setattr(
        feishu_supervisor,
        "managed_process_start_identity",
        lambda _pid: next(starts),
        raising=False,
    )
    monkeypatch.setattr(feishu_supervisor.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(
        feishu_supervisor.os,
        "killpg",
        lambda _pid, sent_signal: signals.append(sent_signal),
    )
    monkeypatch.setattr(
        feishu_supervisor.time,
        "monotonic",
        lambda: next(monotonic),
    )

    supervisor.terminate_orphan_worker("poller", 101)

    assert signals == [feishu_supervisor.signal.SIGTERM]


def test_supervisor_cleans_stale_workers_before_starting_new_workers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    supervisor.stopping = True
    supervisor.tunnel_enabled = False
    events: list[str] = []

    monkeypatch.setattr(feishu_supervisor, "RUNTIME_DIR", tmp_path / "runtime")
    monkeypatch.setattr(feishu_supervisor, "PUBLIC_URL_FILE", tmp_path / "public")
    monkeypatch.setattr(feishu_supervisor, "CALLBACK_URL_FILE", tmp_path / "callback")
    monkeypatch.setattr(feishu_supervisor.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(feishu_supervisor.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(supervisor, "log", lambda _message: None)
    monkeypatch.setattr(
        supervisor,
        "cleanup_stale_worker_cohort",
        lambda: events.append("cleanup"),
        raising=False,
    )
    monkeypatch.setattr(supervisor, "start_bot", lambda: events.append("bot"))
    monkeypatch.setattr(supervisor, "start_ws", lambda: events.append("ws"))
    monkeypatch.setattr(supervisor, "start_poller", lambda: events.append("poller"))
    monkeypatch.setattr(supervisor, "start_tunnel", lambda: None)
    monkeypatch.setattr(supervisor, "terminate_proc", lambda *_args: None)

    assert supervisor.run() == 0
    assert events[:4] == ["cleanup", "bot", "ws", "poller"]


def test_supervisor_cleans_partial_cohort_when_startup_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    supervisor = feishu_supervisor.Supervisor()
    supervisor.tunnel_enabled = False
    started_bot = object()
    stopped: list[str] = []

    monkeypatch.setattr(feishu_supervisor, "RUNTIME_DIR", tmp_path / "runtime")
    monkeypatch.setattr(feishu_supervisor, "PUBLIC_URL_FILE", tmp_path / "public")
    monkeypatch.setattr(feishu_supervisor, "CALLBACK_URL_FILE", tmp_path / "callback")
    monkeypatch.setattr(feishu_supervisor, "deployment_generation", lambda: "current")
    monkeypatch.setattr(feishu_supervisor.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(supervisor, "log", lambda _message: None)
    monkeypatch.setattr(supervisor, "cleanup_stale_worker_cohort", lambda: None)

    def fail_after_starting_bot() -> None:
        supervisor.bot = started_bot  # type: ignore[assignment]
        raise RuntimeError("pid persistence failed")

    monkeypatch.setattr(supervisor, "start_bot", fail_after_starting_bot)
    monkeypatch.setattr(
        supervisor,
        "terminate_proc",
        lambda name, proc: stopped.append(name) if proc is not None else None,
    )

    with pytest.raises(RuntimeError, match="pid persistence failed"):
        supervisor.run()

    assert stopped == ["bot"]
