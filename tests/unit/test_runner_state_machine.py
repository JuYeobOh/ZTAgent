import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from employee_agent.runner import _StatusReporter, run_task
from employee_agent.controller_client import RunTask
from employee_agent.reporting.results import TaskResult


def make_task(**kwargs) -> RunTask:
    defaults = {
        "run_task_id": "rt-001",
        "task_id": "t-001",
        "task_type": "work",
        "site": "groupoffice",
        "module": "calendar",
        "action": "create_event",
        "scheduled_at": datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
        "status": "pending",
    }
    defaults.update(kwargs)
    return RunTask(**defaults)


def make_client() -> AsyncMock:
    client = AsyncMock()
    client.report_status = AsyncMock()
    client.emit_event = AsyncMock()
    client.upload_result = AsyncMock()
    return client


def make_cfg():
    cfg = MagicMock()
    cfg.EMPLOYEE_ID = "emp-001"
    cfg.LOCATION_ID = "loc-001"
    cfg.RESULTS_DIR = "/tmp/results"
    cfg.PROFILE_DIR = "/tmp/profile"
    cfg.BROWSER_HEADLESS = True
    cfg.PER_TASK_LLM_TIMEOUT_S = 90.0
    return cfg


# ---------------------------------------------------------------------------
# _StatusReporter unit tests (1 report_status call each — no running call here)
# ---------------------------------------------------------------------------

# 테스트 1: succeed 경로 — "succeeded" 1회 보고
@pytest.mark.asyncio
async def test_succeed_path():
    client = make_client()
    task = make_task()
    cfg = make_cfg()

    async with _StatusReporter(client, task, cfg) as reporter:
        await reporter.succeed(metadata={"steps": 5})

    assert client.report_status.call_count == 1
    call_kwargs = client.report_status.call_args.kwargs
    assert call_kwargs["status"] == "succeeded"


# 테스트 2: fail 경로 — "failed" 1회 보고
@pytest.mark.asyncio
async def test_fail_path():
    client = make_client()
    task = make_task()
    cfg = make_cfg()

    async with _StatusReporter(client, task, cfg) as reporter:
        await reporter.fail("some_error")

    assert client.report_status.call_count == 1
    call_kwargs = client.report_status.call_args.kwargs
    assert call_kwargs["status"] == "failed"


# 테스트 3: skip 경로 — "skipped" 1회 보고
@pytest.mark.asyncio
async def test_skip_path():
    client = make_client()
    task = make_task()
    cfg = make_cfg()

    async with _StatusReporter(client, task, cfg) as reporter:
        await reporter.skip("circuit_open")

    assert client.report_status.call_count == 1
    call_kwargs = client.report_status.call_args.kwargs
    assert call_kwargs["status"] == "skipped"


# 테스트 4: 일반 예외 경로 — "failed" 1회 보고, 예외 re-raise
@pytest.mark.asyncio
async def test_exception_path():
    client = make_client()
    task = make_task()
    cfg = make_cfg()

    with pytest.raises(ValueError, match="unexpected"):
        async with _StatusReporter(client, task, cfg) as reporter:
            raise ValueError("unexpected error")

    assert client.report_status.call_count == 1
    call_kwargs = client.report_status.call_args.kwargs
    assert call_kwargs["status"] == "failed"


# 테스트 5: CancelledError 경로 — "failed" 1회 보고, CancelledError re-raise
@pytest.mark.asyncio
async def test_cancelled_error_path():
    client = make_client()
    task = make_task()
    cfg = make_cfg()

    with pytest.raises(asyncio.CancelledError):
        async with _StatusReporter(client, task, cfg) as reporter:
            raise asyncio.CancelledError()

    assert client.report_status.call_count == 1
    call_kwargs = client.report_status.call_args.kwargs
    assert call_kwargs["status"] == "failed"


# ---------------------------------------------------------------------------
# run_task pre-flight skips (no running call)
# ---------------------------------------------------------------------------

# 테스트 6: run_task budget_exceeded — emit_event + skip 1회
@pytest.mark.asyncio
async def test_run_task_budget_exceeded():
    client = make_client()
    task = make_task()
    cfg = make_cfg()

    await run_task(task, cfg, client, budget_exceeded=True)

    assert client.report_status.call_count == 1
    assert client.report_status.call_args.kwargs["status"] == "skipped"
    assert any(
        call.kwargs.get("event_type") == "budget_exceeded"
        for call in client.emit_event.call_args_list
    )


# 테스트 7: run_task circuit_open — skip 1회
@pytest.mark.asyncio
async def test_run_task_circuit_open():
    client = make_client()
    task = make_task()
    cfg = make_cfg()

    await run_task(task, cfg, client, circuit_open=True)

    assert client.report_status.call_count == 1
    assert client.report_status.call_args.kwargs["status"] == "skipped"


# ---------------------------------------------------------------------------
# run_task dispatch tests (running + terminal = 2 calls each)
# ---------------------------------------------------------------------------

# 테스트 8: clock_in dispatch
@pytest.mark.asyncio
async def test_run_task_dispatches_clock_in(monkeypatch):
    client = make_client()
    task = make_task(task_type="clock_in")
    cfg = make_cfg()

    mock_fn = AsyncMock()
    monkeypatch.setattr("employee_agent.runner._do_clock_in", mock_fn)

    await run_task(task, cfg, client)

    mock_fn.assert_awaited_once()
    assert client.report_status.call_count == 2
    calls = client.report_status.call_args_list
    assert calls[0].kwargs["status"] == "running"
    assert calls[1].kwargs["status"] == "succeeded"


# 테스트 9: clock_out dispatch
@pytest.mark.asyncio
async def test_run_task_dispatches_clock_out(monkeypatch):
    client = make_client()
    task = make_task(task_type="clock_out")
    cfg = make_cfg()

    mock_fn = AsyncMock()
    monkeypatch.setattr("employee_agent.runner._do_clock_out", mock_fn)

    await run_task(task, cfg, client)

    mock_fn.assert_awaited_once()
    assert client.report_status.call_count == 2
    calls = client.report_status.call_args_list
    assert calls[0].kwargs["status"] == "running"
    assert calls[1].kwargs["status"] == "succeeded"


# 테스트 10: work dispatch
@pytest.mark.asyncio
async def test_run_task_dispatches_work(monkeypatch):
    client = make_client()
    task = make_task(task_type="work")
    cfg = make_cfg()

    stub_result = TaskResult(
        screenshots_path=None,
        browser_trace_path=None,
        metadata={"steps": 3, "final_url": "http://example.com"},
    )
    mock_fn = AsyncMock(return_value=stub_result)
    monkeypatch.setattr("employee_agent.runner._do_work", mock_fn)

    await run_task(task, cfg, client)

    mock_fn.assert_awaited_once()
    client.upload_result.assert_awaited_once()
    assert client.report_status.call_count == 2
    calls = client.report_status.call_args_list
    assert calls[0].kwargs["status"] == "running"
    assert calls[1].kwargs["status"] == "succeeded"


# 테스트 11: unknown task_type — running + failed
@pytest.mark.asyncio
async def test_run_task_unknown_task_type():
    client = make_client()
    task = make_task(task_type="mystery_type")
    cfg = make_cfg()

    await run_task(task, cfg, client)

    assert client.report_status.call_count == 2
    calls = client.report_status.call_args_list
    assert calls[0].kwargs["status"] == "running"
    assert calls[1].kwargs["status"] == "failed"
    assert calls[1].kwargs.get("error_message", "").startswith("unknown_task_type:")
