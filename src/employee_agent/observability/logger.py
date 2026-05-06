"""JSON structured logger for employee-agent.

Canonical event vocabulary (structlog event= key):
  Lifecycle:    employee_agent_started, plan_received, no_work_today
  Task:         task_started, task_running, task_skipped_budget,
                task_skipped_circuit, task_succeeded, task_failed
  Auth:         clock_in_complete, clock_out_complete
  browser-use:  browser_use_start, browser_use_step, browser_use_timeout
  Result:       result_uploaded
  Errors:       agent_cancelled, main_loop_error,
                emit_event_skipped_no_run_task_id
"""
import sys
import structlog
from pathlib import Path
from datetime import date


class _TeeWriter:
    """stdout과 파일에 동시 기록."""

    def __init__(self, path: Path) -> None:
        self._f = open(path, "a", encoding="utf-8")

    def write(self, message: str) -> None:
        sys.stdout.write(message)
        self._f.write(message)
        self._f.flush()

    def flush(self) -> None:
        sys.stdout.flush()
        self._f.flush()


def init_json_logger(log_dir: str) -> structlog.BoundLogger:
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    log_path = log_dir_path / f"agent_{date.today().strftime('%Y%m%d')}.jsonl"

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=_TeeWriter(log_path)),
    )
    return structlog.get_logger()


def get_logger() -> structlog.BoundLogger:
    return structlog.get_logger()
