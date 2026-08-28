#!/usr/bin/env python3
"""Keep the Feishu bot and public tunnel running.

The supervisor restarts the local bot service and the Cloudflare tunnel when
either exits. It also writes the current public callback URL into runtime files.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import shutil
import stat
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request

try:
    from deployment_generation import calculate_deployment_generation
except ModuleNotFoundError:
    from services.deployment_generation import calculate_deployment_generation

try:
    from host_config import (
        secure_append_text,
        secure_runtime_file,
        secure_runtime_root,
        secure_write_text,
    )
except ModuleNotFoundError:
    from services.host_config import (
        secure_append_text,
        secure_runtime_file,
        secure_runtime_root,
        secure_write_text,
    )


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "runtime"
SUPERVISOR_LOG = RUNTIME_DIR / "feishu_supervisor.log"
PUBLIC_URL_FILE = RUNTIME_DIR / "public_url.txt"
CALLBACK_URL_FILE = RUNTIME_DIR / "feishu_callback_url.txt"
BOT_PID_FILE = RUNTIME_DIR / "feishu_bot.pid"
WS_PID_FILE = RUNTIME_DIR / "feishu_ws.pid"
POLLER_PID_FILE = RUNTIME_DIR / "feishu_poller.pid"
CLOUDFLARED_PID_FILE = RUNTIME_DIR / "cloudflared.pid"
LOCAL_CLOUDFLARED = ROOT / "tools" / "bin" / ("cloudflared.exe" if os.name == "nt" else "cloudflared")

TRY_CLOUDFLARE_RE = re.compile(r"https://(?!api\.)[a-zA-Z0-9-]+\.trycloudflare\.com")


def deployment_generation() -> str:
    """Return a stable fingerprint for the Python code loaded by bot workers."""
    return calculate_deployment_generation(ROOT)


def harden_runtime_metadata() -> None:
    """Secure known supervisor metadata without traversing shared runtime."""
    secure_runtime_root(ROOT)
    secure_runtime_root(RUNTIME_DIR, create=True)
    for metadata_file in (
        SUPERVISOR_LOG,
        PUBLIC_URL_FILE,
        CALLBACK_URL_FILE,
        BOT_PID_FILE,
        WS_PID_FILE,
        POLLER_PID_FILE,
        CLOUDFLARED_PID_FILE,
    ):
        secure_runtime_file(metadata_file)


def build_no_proxy_opener() -> request.OpenerDirector:
    return request.build_opener(request.ProxyHandler({}))


def process_group_kwargs() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def resolve_cloudflared() -> str:
    configured = os.getenv("CLOUDFLARED_BIN", "").strip()
    if configured:
        return configured
    if LOCAL_CLOUDFLARED.exists():
        return str(LOCAL_CLOUDFLARED)
    found = shutil.which("cloudflared")
    if found:
        return found
    return "cloudflared"


def read_managed_pid(path: Path) -> int:
    """Read one regular PID file without following links or accepting junk."""
    try:
        before = path.lstat()
    except FileNotFoundError:
        return 0
    except OSError as error:
        raise RuntimeError("unable to inspect managed pid") from error
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise RuntimeError("unsafe managed pid")

    descriptor = -1
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(descriptor)
        current = path.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_dev != before.st_dev
            or opened.st_ino != before.st_ino
            or current.st_dev != opened.st_dev
            or current.st_ino != opened.st_ino
        ):
            raise RuntimeError("unsafe managed pid")
        raw = os.read(descriptor, 33)
    except RuntimeError:
        raise
    except (OSError, UnicodeError) as error:
        raise RuntimeError("unable to read managed pid") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    if len(raw) > 32:
        raise RuntimeError("invalid managed pid")
    try:
        value = raw.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise RuntimeError("invalid managed pid") from error
    if re.fullmatch(r"[1-9][0-9]*", value) is None:
        raise RuntimeError("invalid managed pid")
    pid = int(value)
    if pid <= 1:
        raise RuntimeError("invalid managed pid")
    return pid


def managed_process_command(pid: int) -> str:
    """Return one full process command without using broad process matching."""
    if pid <= 1 or os.name == "nt":
        return ""
    try:
        result = subprocess.run(
            [shutil.which("ps") or "/bin/ps", "-ww", "-p", str(pid), "-o", "command="],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def managed_process_exists(pid: int) -> bool:
    """Check one exact POSIX PID without sending it a terminating signal."""
    if pid <= 1:
        return False
    if os.name != "posix":
        raise RuntimeError("exact managed process inspection is not supported")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as error:
        raise RuntimeError("unable to inspect managed process") from error
    return True


def managed_process_start_identity(pid: int) -> str:
    """Return a kernel-backed identity that changes when a PID is reused."""
    if pid <= 1 or os.name != "posix":
        return ""

    if sys.platform == "darwin":
        import ctypes

        class ProcBsdInfo(ctypes.Structure):
            _fields_ = [
                ("pbi_flags", ctypes.c_uint32),
                ("pbi_status", ctypes.c_uint32),
                ("pbi_xstatus", ctypes.c_uint32),
                ("pbi_pid", ctypes.c_uint32),
                ("pbi_ppid", ctypes.c_uint32),
                ("pbi_uid", ctypes.c_uint32),
                ("pbi_gid", ctypes.c_uint32),
                ("pbi_ruid", ctypes.c_uint32),
                ("pbi_rgid", ctypes.c_uint32),
                ("pbi_svuid", ctypes.c_uint32),
                ("pbi_svgid", ctypes.c_uint32),
                ("rfu_1", ctypes.c_uint32),
                ("pbi_comm", ctypes.c_char * 16),
                ("pbi_name", ctypes.c_char * 32),
                ("pbi_nfiles", ctypes.c_uint32),
                ("pbi_pgid", ctypes.c_uint32),
                ("pbi_pjobc", ctypes.c_uint32),
                ("e_tdev", ctypes.c_uint32),
                ("e_tpgid", ctypes.c_uint32),
                ("pbi_nice", ctypes.c_int32),
                ("pbi_start_tvsec", ctypes.c_uint64),
                ("pbi_start_tvusec", ctypes.c_uint64),
            ]

        try:
            libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
            proc_pidinfo = libproc.proc_pidinfo
            proc_pidinfo.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_uint64,
                ctypes.c_void_p,
                ctypes.c_int,
            ]
            proc_pidinfo.restype = ctypes.c_int
            info = ProcBsdInfo()
            received = proc_pidinfo(
                pid,
                3,  # PROC_PIDTBSDINFO
                0,
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
        except (AttributeError, OSError):
            return ""
        if received != ctypes.sizeof(info) or info.pbi_pid != pid:
            return ""
        return f"darwin:{info.pbi_start_tvsec}:{info.pbi_start_tvusec}"

    if sys.platform.startswith("linux"):
        try:
            raw_stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        except (FileNotFoundError, ProcessLookupError, OSError, UnicodeError):
            return ""
        closing_parenthesis = raw_stat.rfind(")")
        if closing_parenthesis < 0:
            return ""
        fields = raw_stat[closing_parenthesis + 1 :].split()
        if len(fields) <= 19 or not fields[19].isdigit():
            return ""
        return f"linux:{fields[19]}"

    return ""


def worker_command_matches_role(command: str, role: str) -> bool:
    """Match only workers launched from this checkout for one exact role."""
    try:
        tokens = shlex.split(str(command or ""))
    except ValueError:
        return False
    script = str(ROOT / "services" / "feishu_bot.py")
    if len(tokens) < 4:
        return False
    if os.path.normcase(os.path.realpath(tokens[0])) != os.path.normcase(
        os.path.realpath(sys.executable)
    ):
        return False
    if tokens[1:3] != ["-u", script]:
        return False
    arguments = tokens[3:]
    if role == "ws":
        return arguments == ["ws"]
    if role == "poller":
        return arguments == ["poll"]
    if role != "bot" or len(arguments) != 4:
        return False
    if arguments[0] != "--host" or not arguments[1] or arguments[2] != "--port":
        return False
    try:
        port = int(arguments[3])
    except ValueError:
        return False
    return 1 <= port <= 65535


class Supervisor:
    def __init__(self) -> None:
        self.host = os.getenv("FEISHU_BOT_HOST", "0.0.0.0")
        self.port = int(os.getenv("FEISHU_BOT_PORT", "8787"))
        self.bot: subprocess.Popen[str] | None = None
        self.ws: subprocess.Popen[str] | None = None
        self.poller: subprocess.Popen[str] | None = None
        self.tunnel: subprocess.Popen[str] | None = None
        self.stopping = False
        self.last_public_url = ""
        self.bot_failed_checks = 0
        self.active_generation = deployment_generation()
        allowed_chat = os.getenv("FEISHU_ALLOWED_CHAT_ID", "").strip()
        self.poll_chat_id = allowed_chat
        self.poller_enabled = bool(self.poll_chat_id)
        self.ws_enabled = os.getenv("FEISHU_WS_ENABLED", "1").lower() in {"1", "true", "yes"}
        self.tunnel_enabled = os.getenv("FEISHU_TUNNEL_ENABLED", "1").lower() in {"1", "true", "yes"}
        self.tunnel_failed_checks = 0
        self.cloudflared_bin = resolve_cloudflared()
        self.cloudflared_protocol = os.getenv("CLOUDFLARED_PROTOCOL", "").strip()
        self.public_health_check = os.getenv("FEISHU_PUBLIC_HEALTH_CHECK", "").lower() in {
            "1",
            "true",
            "yes",
        }

    def log(self, message: str) -> None:
        line = f"[{datetime.now().isoformat(timespec='seconds')}] {message}"
        print(line, flush=True)
        secure_append_text(SUPERVISOR_LOG, line + "\n")

    def stale_worker_identity(
        self,
        role: str,
        pid: int,
    ) -> tuple[str, str, int] | None:
        """Capture one worker instance without confusing PID reuse for survival."""
        command = managed_process_command(pid)
        if not command:
            if managed_process_exists(pid):
                raise RuntimeError(f"unable to verify stale {role} worker")
            return None

        start_identity = managed_process_start_identity(pid)
        if not start_identity:
            if managed_process_exists(pid):
                raise RuntimeError(f"unable to verify stale {role} worker identity")
            return None

        try:
            process_group = os.getpgid(pid)
        except ProcessLookupError:
            return None
        except OSError as error:
            raise RuntimeError(f"unable to inspect stale {role} worker") from error
        return command, start_identity, process_group

    def terminate_orphan_worker(self, role: str, pid: int) -> None:
        """Stop one verified stale worker without touching unrelated processes."""
        identity = self.stale_worker_identity(role, pid)
        if identity is None:
            return
        if not worker_command_matches_role(identity[0], role) or identity[2] != pid:
            raise RuntimeError(f"stale {role} worker identity changed")

        before_term = self.stale_worker_identity(role, pid)
        if before_term is None:
            return
        if before_term != identity:
            raise RuntimeError(f"stale {role} worker identity changed")

        self.log(f"stopping stale {role} worker")
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except OSError as error:
            raise RuntimeError(f"unable to stop stale {role} worker") from error

        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            current_identity = self.stale_worker_identity(role, pid)
            if current_identity is None or current_identity != identity:
                return
            time.sleep(0.2)

        current_identity = self.stale_worker_identity(role, pid)
        if current_identity is None or current_identity != identity:
            return
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        except OSError as error:
            raise RuntimeError(f"unable to kill stale {role} worker") from error

    def cleanup_stale_worker_cohort(self) -> None:
        """Reap a previous supervisor's exact worker cohort before startup."""
        if os.name != "posix":
            raise RuntimeError("exact stale worker cleanup is not supported")
        workers = (
            ("bot", BOT_PID_FILE),
            ("ws", WS_PID_FILE),
            ("poller", POLLER_PID_FILE),
        )
        for role, pid_file in workers:
            pid = read_managed_pid(pid_file)
            if not pid or pid == os.getpid():
                continue
            command = managed_process_command(pid)
            if not command:
                if managed_process_exists(pid):
                    raise RuntimeError(f"unable to verify stale {role} worker")
                continue
            if not worker_command_matches_role(command, role):
                continue
            try:
                process_group = os.getpgid(pid)
            except ProcessLookupError:
                continue
            except OSError as error:
                raise RuntimeError(
                    f"unable to inspect stale {role} worker"
                ) from error
            if process_group != pid:
                raise RuntimeError(f"unsafe stale {role} worker process group")
            self.terminate_orphan_worker(role, pid)

    def start_bot(self) -> None:
        if self.bot and self.bot.poll() is None:
            return
        cmd = [
            sys.executable,
            "-u",
            str(ROOT / "services" / "feishu_bot.py"),
            "--host",
            self.host,
            "--port",
            str(self.port),
        ]
        self.bot = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **process_group_kwargs(),
        )
        secure_write_text(BOT_PID_FILE, str(self.bot.pid))
        self.log(f"started feishu bot pid={self.bot.pid}")
        threading.Thread(target=self.pipe_output, args=("bot", self.bot), daemon=True).start()

    def start_ws(self) -> None:
        if not self.ws_enabled:
            return
        if self.ws and self.ws.poll() is None:
            return
        cmd = [
            sys.executable,
            "-u",
            str(ROOT / "services" / "feishu_bot.py"),
            "ws",
        ]
        self.ws = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **process_group_kwargs(),
        )
        secure_write_text(WS_PID_FILE, str(self.ws.pid))
        self.log(f"started feishu ws pid={self.ws.pid}")
        threading.Thread(target=self.pipe_output, args=("ws", self.ws), daemon=True).start()

    def start_poller(self) -> None:
        if not self.poller_enabled:
            return
        if self.poller and self.poller.poll() is None:
            return
        cmd = self.poller_command()
        self.poller = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **process_group_kwargs(),
        )
        secure_write_text(POLLER_PID_FILE, str(self.poller.pid))
        self.log(f"started feishu poller pid={self.poller.pid}")
        threading.Thread(target=self.pipe_output, args=("poller", self.poller), daemon=True).start()

    def poller_command(self) -> list[str]:
        return [
            sys.executable,
            "-u",
            str(ROOT / "services" / "feishu_bot.py"),
            "poll",
        ]

    def start_tunnel(self) -> None:
        if not self.tunnel_enabled:
            return
        if self.tunnel and self.tunnel.poll() is None:
            return
        cmd = [
            self.cloudflared_bin,
            "tunnel",
            "--url",
            f"http://127.0.0.1:{self.port}",
            "--no-autoupdate",
        ]
        if self.cloudflared_protocol:
            cmd.extend(["--protocol", self.cloudflared_protocol])
        self.tunnel = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **process_group_kwargs(),
        )
        secure_write_text(CLOUDFLARED_PID_FILE, str(self.tunnel.pid))
        self.log(f"started cloudflared pid={self.tunnel.pid}")
        threading.Thread(target=self.pipe_output, args=("cloudflared", self.tunnel), daemon=True).start()

    def pipe_output(self, name: str, proc: subprocess.Popen[str]) -> None:
        if proc.stdout is None:
            return
        for raw_line in proc.stdout:
            line = raw_line.rstrip()
            if not line:
                continue
            self.log(f"{name}: {line}")
            if name == "cloudflared":
                match = TRY_CLOUDFLARE_RE.search(line)
                if match:
                    self.set_public_url(match.group(0))

    def set_public_url(self, public_url: str) -> None:
        if public_url == self.last_public_url:
            return
        self.last_public_url = public_url
        callback_url = public_url.rstrip("/") + "/feishu/events"
        secure_write_text(PUBLIC_URL_FILE, public_url + "\n")
        secure_write_text(CALLBACK_URL_FILE, callback_url + "\n")
        self.log(f"public url: {public_url}")
        self.log(f"feishu callback url: {callback_url}")

    def health_ok(self) -> bool:
        if not self.deployment_generation_ok():
            return False
        try:
            with build_no_proxy_opener().open(f"http://127.0.0.1:{self.port}/health", timeout=5) as resp:
                return self.health_response_matches_generation(resp)
        except (error.URLError, TimeoutError, OSError):
            return False

    def public_health_ok(self) -> bool:
        if not self.last_public_url:
            return False
        if not self.deployment_generation_ok():
            return False
        try:
            with request.urlopen(f"{self.last_public_url.rstrip('/')}/health", timeout=8) as resp:
                return self.health_response_matches_generation(resp)
        except (error.URLError, TimeoutError, OSError):
            return False

    def health_response_matches_generation(self, response: Any) -> bool:
        if response.status != 200:
            return False
        try:
            payload = json.loads(response.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 - an invalid health response is unhealthy.
            return False
        return (
            isinstance(payload, dict)
            and payload.get("generation") == self.active_generation
        )

    def terminate_proc(self, name: str, proc: subprocess.Popen[str] | None) -> None:
        if not proc or proc.poll() is not None:
            return
        self.log(f"stopping {name} pid={proc.pid}")
        if os.name == "nt":
            proc.terminate()
        else:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                return
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.log(f"killing {name} pid={proc.pid}")
            if os.name == "nt":
                proc.kill()
            else:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def restart_bot(self) -> None:
        self.terminate_proc("bot", self.bot)
        self.bot = None
        self.bot_failed_checks = 0
        time.sleep(1)
        self.start_bot()

    def deployment_generation_ok(self) -> bool:
        try:
            return deployment_generation() == self.active_generation
        except OSError:
            return False

    def restart_bot_cohort(self, generation: str) -> None:
        self.terminate_proc("poller", self.poller)
        self.terminate_proc("ws", self.ws)
        self.terminate_proc("bot", self.bot)
        self.poller = None
        self.ws = None
        self.bot = None
        self.bot_failed_checks = 0
        self.active_generation = generation
        time.sleep(1)
        self.start_bot()
        self.start_ws()
        time.sleep(2)
        self.start_poller()

    def reconcile_deployment_generation(self) -> bool:
        try:
            current_generation = deployment_generation()
        except OSError:
            self.log("deployment generation unavailable; workers are not ready")
            return False
        if current_generation == self.active_generation:
            return False
        self.log("deployment generation changed; restarting bot worker cohort")
        self.restart_bot_cohort(current_generation)
        return True

    def restart_tunnel(self) -> None:
        self.terminate_proc("cloudflared", self.tunnel)
        self.tunnel = None
        self.tunnel_failed_checks = 0
        self.last_public_url = ""
        time.sleep(1)
        self.start_tunnel()

    def stop(self, *_args: object) -> None:
        self.stopping = True

    def run(self) -> int:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        self.log("supervisor starting")
        if not self.tunnel_enabled:
            # Long-connection mode does not use an HTTP callback URL. Remove
            # stale quick-tunnel metadata so operators cannot follow a dead
            # address while diagnosing callback delivery.
            for stale_path in (PUBLIC_URL_FILE, CALLBACK_URL_FILE):
                try:
                    stale_path.unlink()
                except FileNotFoundError:
                    pass
        self.active_generation = deployment_generation()
        self.cleanup_stale_worker_cohort()
        self.start_bot()
        self.start_ws()
        time.sleep(2)
        self.start_poller()
        self.start_tunnel()

        while not self.stopping:
            self.reconcile_deployment_generation()

            if self.bot and self.bot.poll() is not None:
                self.log(f"bot exited code={self.bot.returncode}; restarting")
                self.bot = None
                self.start_bot()

            if not self.health_ok():
                self.bot_failed_checks += 1
                self.log(f"bot health check failed count={self.bot_failed_checks}")
                if self.bot_failed_checks >= 3:
                    self.restart_bot()
            else:
                self.bot_failed_checks = 0

            if self.ws_enabled and self.ws and self.ws.poll() is not None:
                self.log(f"ws exited code={self.ws.returncode}; restarting")
                self.ws = None
                self.start_ws()

            if self.poller_enabled and self.poller and self.poller.poll() is not None:
                self.log(f"poller exited code={self.poller.returncode}; restarting")
                self.poller = None
                self.start_poller()

            if self.tunnel_enabled and self.tunnel and self.tunnel.poll() is not None:
                self.log(f"cloudflared exited code={self.tunnel.returncode}; restarting")
                self.tunnel = None
                self.start_tunnel()
            elif self.tunnel_enabled and self.public_health_check and self.last_public_url and not self.public_health_ok():
                self.tunnel_failed_checks += 1
                self.log(f"public tunnel health check failed count={self.tunnel_failed_checks}")
                if self.tunnel_failed_checks >= 2:
                    self.restart_tunnel()
            elif self.tunnel_enabled and self.public_health_check and self.last_public_url:
                self.tunnel_failed_checks = 0

            time.sleep(10)

        self.log("supervisor stopping")
        self.terminate_proc("cloudflared", self.tunnel)
        self.terminate_proc("poller", self.poller)
        self.terminate_proc("ws", self.ws)
        self.terminate_proc("bot", self.bot)
        return 0


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    os.umask(0o077)
    harden_runtime_metadata()
    try:
        from supervisor_singleton import (
            SupervisorAlreadyRunning,
            SupervisorLockError,
            supervisor_lock,
        )
    except ModuleNotFoundError:
        from services.supervisor_singleton import (
            SupervisorAlreadyRunning,
            SupervisorLockError,
            supervisor_lock,
        )

    try:
        with supervisor_lock(RUNTIME_DIR / "feishu_supervisor.lock"):
            load_dotenv(ROOT / ".env")
            return Supervisor().run()
    except SupervisorAlreadyRunning:
        print("feishu supervisor is already running", file=sys.stderr)
        return 2
    except SupervisorLockError:
        print("feishu supervisor singleton lock is unavailable", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
