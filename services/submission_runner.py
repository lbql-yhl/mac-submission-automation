#!/usr/bin/env python3
"""Run one Feishu-triggered submission workflow through Codex CLI."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

try:
    import feishu_bot
except ModuleNotFoundError:
    from services import feishu_bot


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "runtime"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_run_event(run_id: str, status: str, note: str, **fields: str) -> None:
    def apply_event(run: dict[str, Any]) -> None:
        run["status"] = status
        run.update({key: value for key, value in fields.items() if value})
        run.setdefault("events", []).append(
            {"at": utc_now(), "status": status, "note": note}
        )

    feishu_bot.mutate_run(run_id, apply_event)


def lifecycle_args(run_id: str, *, outcome: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        run_id=run_id,
        chat_id=os.getenv("SUBMISSION_CHAT_ID", ""),
        skill="",
        stage="",
        outcome=outcome,
    )


def finish_run(run_id: str, config: Any, outcome: str) -> int:
    return feishu_bot.notify_run_finish(
        lifecycle_args(run_id, outcome=outcome), config
    )


def record_terminal_event(
    run_id: str, status: str, note: str, **fields: str
) -> None:
    try:
        append_run_event(run_id, status, note, **fields)
    except Exception:  # noqa: BLE001 - terminal outcome must survive logging failure.
        print("Submission terminal event could not be persisted", file=sys.stderr)


def finish_run_safely(run_id: str, config: Any, outcome: str) -> int:
    try:
        return finish_run(run_id, config, outcome)
    except Exception:  # noqa: BLE001 - preserve the original terminal semantics.
        print("Submission terminal delivery failed", file=sys.stderr)
        return 2


def claim_legacy_runner(run_id: str) -> bool:
    claimed_at = utc_now()
    generation = uuid.uuid4().hex

    def apply_claim(run: dict[str, Any]) -> None:
        lifecycle = run.get("lifecycle")
        if (
            not isinstance(lifecycle, dict)
            or not lifecycle.get("start_message_id")
            or lifecycle.get("finished_at")
            or lifecycle.get("outcome")
            or "legacy_runner_claim" in run
        ):
            raise RuntimeError("legacy runner claim refused")
        run["legacy_runner_claim"] = {
            "claimed_at": claimed_at,
            "generation": generation,
        }

    try:
        return feishu_bot.mutate_run(run_id, apply_claim) is not None
    except Exception:  # noqa: BLE001 - ownership uncertainty must fail closed.
        return False


def main() -> int:
    run_id = os.getenv("SUBMISSION_RUN_ID", "")
    prompt_path = Path(os.getenv("SUBMISSION_PROMPT_PATH", ""))
    if not run_id or not prompt_path.exists():
        print("SUBMISSION_RUN_ID or SUBMISSION_PROMPT_PATH is missing", file=sys.stderr)
        return 2

    codex_command = os.getenv("FEISHU_CODEX_COMMAND", "codex")
    codex_model = os.getenv("FEISHU_CODEX_MODEL", "gpt-5.6-sol")
    timeout_seconds = int(os.getenv("SUBMISSION_RUNNER_TIMEOUT_SECONDS", "21600"))
    output_path = RUNTIME_DIR / f"{run_id}.codex-output.txt"

    try:
        config = feishu_bot.load_config()
    except RuntimeError:
        print("Submission lifecycle configuration is unavailable", file=sys.stderr)
        return 2
    if feishu_bot.notify_run_start(lifecycle_args(run_id), config) != 0:
        print("Submission start delivery is not confirmed", file=sys.stderr)
        return 2
    if not claim_legacy_runner(run_id):
        print("Submission runner claim was refused", file=sys.stderr)
        return 2

    try:
        append_run_event(
            run_id,
            "running",
            "Codex CLI submission runner started",
            codex_output_path=str(output_path),
        )

        prompt = prompt_path.read_text(encoding="utf-8")
        cmd = [
            codex_command,
            "exec",
            "--cd",
            str(ROOT),
            "--sandbox",
            "danger-full-access",
            "-m",
            codex_model,
            "-o",
            str(output_path),
            prompt,
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            record_terminal_event(
                run_id, "runner_timeout", "Codex CLI submission runner timed out"
            )
            finish_run_safely(run_id, config, "stopped")
            print("Codex CLI submission runner timed out", file=sys.stderr)
            return 124
        except KeyboardInterrupt:
            record_terminal_event(
                run_id, "runner_stopped", "Codex CLI submission runner stopped"
            )
            finish_run_safely(run_id, config, "stopped")
            raise

        if result.returncode == 0:
            record_terminal_event(
                run_id,
                "runner_completed",
                "Codex CLI submission runner completed",
            )
            return 0 if finish_run_safely(run_id, config, "success") == 0 else 2

        append_run_event(
            run_id,
            "runner_failed",
            f"Codex CLI submission runner exited with code {result.returncode}",
        )
        finish_run_safely(run_id, config, "failed")
        return result.returncode
    except Exception:
        record_terminal_event(
            run_id, "runner_failed", "Codex CLI submission runner failed"
        )
        finish_run_safely(run_id, config, "failed")
        print("Submission runner failed after confirmed start", file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
