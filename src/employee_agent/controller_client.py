from __future__ import annotations

import httpx
import structlog
from datetime import datetime
from pydantic import BaseModel
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)


class TaskItem(BaseModel):
    run_task_id: str
    task_id: str
    task_type: str        # clock_in | work | clock_out
    site: str | None = None
    module: str | None = None
    action: str
    scheduled_at: datetime
    status: str


# 하위 호환을 위한 별칭
RunTask = TaskItem


class DailyPlan(BaseModel):
    work_date: str
    employee_id: str
    requested_location_id: str
    assigned_location_id: str
    should_work_here: bool
    clock_in_at: datetime | None = None
    clock_out_at: datetime | None = None
    tasks: list[TaskItem] = []


def _is_retryable(exc: BaseException) -> bool:
    """Retry on 401, 429 and 5xx but not on 403."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 403:
            return False
        if status in (401, 429) or status >= 500:
            return True
        return False
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    return False


_retry_decorator = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=True,
)


class ControllerClient:
    def __init__(self, cfg: object) -> None:
        self._base_url: str = cfg.CONTROLLER_URL  # type: ignore[attr-defined]
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=30.0,
        )

    async def _get(self, path: str, **params: object) -> dict:
        @_retry_decorator
        async def _inner() -> httpx.Response:
            r = await self._client.get(path, params=params)  # type: ignore[arg-type]
            r.raise_for_status()
            return r

        r = await _inner()
        return r.json()

    async def _post(self, path: str, json: dict) -> dict | None:
        @_retry_decorator
        async def _inner() -> httpx.Response:
            r = await self._client.post(path, json=json)
            r.raise_for_status()
            return r

        r = await _inner()
        if r.content:
            return r.json()
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_today_plan(self, employee_id: str, location_id: str) -> DailyPlan:
        data = await self._get(
            f"/api/v1/employees/{employee_id}/plans/today",
            location_id=location_id,
        )
        return DailyPlan.model_validate(data)

    async def get_plan_by_date(
        self, employee_id: str, work_date: str, location_id: str
    ) -> DailyPlan:
        data = await self._get(
            f"/api/v1/employees/{employee_id}/plans/{work_date}",
            location_id=location_id,
        )
        return DailyPlan.model_validate(data)

    async def report_status(
        self,
        run_task_id: str,
        status: str,
        employee_id: str,
        location_id: str,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        payload: dict = {
            "status": status,
            "employee_id": employee_id,
            "location_id": location_id,
        }
        if error_message is not None:
            payload["error_message"] = error_message
        if metadata is not None:
            payload["metadata"] = metadata
        await self._post(f"/api/v1/run-tasks/{run_task_id}/status", json=payload)

    async def emit_event(
        self,
        run_task_id: str,
        event_type: str,
        message: str = "",
        payload: dict | None = None,
        employee_id: str = "",
        location_id: str = "",
    ) -> None:
        if not run_task_id:
            structlog.get_logger().warning(
                "emit_event_skipped_no_run_task_id",
                event_type=event_type,
                message=message,
            )
            return
        body: dict = {
            "event_type": event_type,
            "message": message,
            "employee_id": employee_id,
            "location_id": location_id,
        }
        if payload is not None:
            body["payload"] = payload
        await self._post(f"/api/v1/run-tasks/{run_task_id}/events", json=body)

    async def upload_result(
        self,
        run_task_id: str,
        employee_id: str,
        location_id: str,
        result_root_path: str,
        screenshots_path: str | None = None,
        browser_trace_path: str | None = None,
        network_log_path: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        body: dict = {
            "employee_id": employee_id,
            "location_id": location_id,
            "result_root_path": result_root_path,
        }
        if screenshots_path is not None:
            body["screenshots_path"] = screenshots_path
        if browser_trace_path is not None:
            body["browser_trace_path"] = browser_trace_path
        if network_log_path is not None:
            body["network_log_path"] = network_log_path
        if metadata is not None:
            body["metadata"] = metadata
        await self._post(f"/api/v1/run-tasks/{run_task_id}/result", json=body)

    async def aclose(self) -> None:
        await self._client.aclose()
