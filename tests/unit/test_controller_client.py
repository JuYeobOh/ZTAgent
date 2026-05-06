from __future__ import annotations

import pytest
import respx
import httpx
import json
from datetime import datetime, timezone

from employee_agent.controller_client import ControllerClient, DailyPlan, RunTask


# ---------------------------------------------------------------------------
# Minimal Settings stub so we don't need env vars
# ---------------------------------------------------------------------------
class _FakeSettings:
    CONTROLLER_URL = "http://controller.test"


PLAN_WITH_TASKS = {
    "work_date": "2024-01-15",
    "employee_id": "emp-001",
    "requested_location_id": "loc-001",
    "assigned_location_id": "loc-001",
    "should_work_here": True,
    "clock_in_at": "2024-01-15T09:00:00+00:00",
    "clock_out_at": "2024-01-15T18:00:00+00:00",
    "tasks": [
        {
            "run_task_id": "rt-001",
            "task_id": "t-001",
            "task_type": "clock_in",
            "site": "groupoffice",
            "module": "attendance",
            "action": "punch_in",
            "scheduled_at": "2024-01-15T09:00:00+00:00",
            "status": "pending",
        }
    ],
}

PLAN_NOT_WORKING = {
    "work_date": "2024-01-15",
    "employee_id": "emp-001",
    "should_work_here": False,
    "tasks": [],
}


@pytest.fixture
def fake_cfg() -> _FakeSettings:
    return _FakeSettings()


# ---------------------------------------------------------------------------
# 1. get_today_plan – successful response with tasks
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_today_plan_with_tasks(fake_cfg: _FakeSettings) -> None:
    with respx.mock(base_url="http://controller.test") as mock:
        mock.get("/api/v1/employees/emp-001/plans/today").mock(
            return_value=httpx.Response(200, json=PLAN_WITH_TASKS)
        )

        client = ControllerClient(fake_cfg)
        plan = await client.get_today_plan("emp-001", "loc-001")
        await client.aclose()

    assert isinstance(plan, DailyPlan)
    assert plan.should_work_here is True
    assert len(plan.tasks) == 1
    assert plan.tasks[0].task_type == "clock_in"
    assert plan.tasks[0].run_task_id == "rt-001"
    assert plan.requested_location_id == "loc-001"
    assert plan.assigned_location_id == "loc-001"


# ---------------------------------------------------------------------------
# 2. get_today_plan – should_work_here=false
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_today_plan_not_working_here(fake_cfg: _FakeSettings) -> None:
    with respx.mock(base_url="http://controller.test") as mock:
        mock.get("/api/v1/employees/emp-001/plans/today").mock(
            return_value=httpx.Response(200, json=PLAN_NOT_WORKING)
        )

        client = ControllerClient(fake_cfg)
        plan = await client.get_today_plan("emp-001", "loc-001")
        await client.aclose()

    assert plan.should_work_here is False
    assert plan.tasks == []


# ---------------------------------------------------------------------------
# 3. report_status – no X-Controller-Token header (token auth removed)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_report_status_no_token_header(fake_cfg: _FakeSettings) -> None:
    captured_request: list[httpx.Request] = []

    with respx.mock(base_url="http://controller.test") as mock:
        def capture(request: httpx.Request) -> httpx.Response:
            captured_request.append(request)
            return httpx.Response(204)

        mock.post("/api/v1/run-tasks/rt-001/status").mock(side_effect=capture)

        client = ControllerClient(fake_cfg)
        await client.report_status(
            run_task_id="rt-001",
            status="completed",
            employee_id="emp-001",
            location_id="loc-001",
        )
        await client.aclose()

    assert len(captured_request) == 1
    # 네트워크 격리로 대체되었으므로 토큰 헤더는 송신되면 안 된다.
    assert "X-Controller-Token" not in captured_request[0].headers


# ---------------------------------------------------------------------------
# 4. emit_event – successful call
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_emit_event_success(fake_cfg: _FakeSettings) -> None:
    with respx.mock(base_url="http://controller.test") as mock:
        route = mock.post("/api/v1/run-tasks/rt-001/events").mock(
            return_value=httpx.Response(200, json={})
        )

        client = ControllerClient(fake_cfg)
        await client.emit_event(
            run_task_id="rt-001",
            event_type="task_started",
            message="Starting task",
            employee_id="emp-001",
            location_id="loc-001",
        )
        await client.aclose()

    assert route.called


# ---------------------------------------------------------------------------
# 5. upload_result – successful call
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_upload_result_success(fake_cfg: _FakeSettings) -> None:
    with respx.mock(base_url="http://controller.test") as mock:
        route = mock.post("/api/v1/run-tasks/rt-001/result").mock(
            return_value=httpx.Response(200, json={})
        )

        client = ControllerClient(fake_cfg)
        await client.upload_result(
            run_task_id="rt-001",
            employee_id="emp-001",
            location_id="loc-001",
            result_root_path="/app/results/rt-001",
            screenshots_path="/app/results/rt-001/screenshots",
            browser_trace_path="/app/results/rt-001/trace.zip",
            metadata={"duration_s": 12.5},
        )
        await client.aclose()

    assert route.called


# ---------------------------------------------------------------------------
# 6. 429 triggers retry and eventually succeeds
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_retry_on_429(fake_cfg: _FakeSettings) -> None:
    call_count = 0

    with respx.mock(base_url="http://controller.test") as mock:
        def flaky(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return httpx.Response(429)
            return httpx.Response(200, json=PLAN_WITH_TASKS)

        mock.get("/api/v1/employees/emp-001/plans/today").mock(side_effect=flaky)

        client = ControllerClient(fake_cfg)
        plan = await client.get_today_plan("emp-001", "loc-001")
        await client.aclose()

    assert call_count == 3
    assert plan.should_work_here is True


# ---------------------------------------------------------------------------
# 7. report_status body does NOT contain run_task_id
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_report_status_body_omits_run_task_id(fake_cfg: _FakeSettings) -> None:
    captured_request: list[httpx.Request] = []

    with respx.mock(base_url="http://controller.test") as mock:
        def capture(request: httpx.Request) -> httpx.Response:
            captured_request.append(request)
            return httpx.Response(204)

        mock.post("/api/v1/run-tasks/rt-001/status").mock(side_effect=capture)

        client = ControllerClient(fake_cfg)
        await client.report_status(
            run_task_id="rt-001",
            status="running",
            employee_id="emp-001",
            location_id="loc-001",
        )
        await client.aclose()

    body = json.loads(captured_request[0].content)
    assert "run_task_id" not in body
    assert body["status"] == "running"
    assert body["employee_id"] == "emp-001"
    assert body["location_id"] == "loc-001"


# ---------------------------------------------------------------------------
# 8. get_today_plan URL path and query param
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_today_plan_url_path(fake_cfg: _FakeSettings) -> None:
    captured_request: list[httpx.Request] = []

    with respx.mock(base_url="http://controller.test") as mock:
        def capture(request: httpx.Request) -> httpx.Response:
            captured_request.append(request)
            return httpx.Response(200, json=PLAN_NOT_WORKING)

        mock.get("/api/v1/employees/emp-001/plans/today").mock(side_effect=capture)

        client = ControllerClient(fake_cfg)
        await client.get_today_plan("emp-001", "loc-001")
        await client.aclose()

    req = captured_request[0]
    assert req.url.path == "/api/v1/employees/emp-001/plans/today"
    assert req.url.params["location_id"] == "loc-001"
