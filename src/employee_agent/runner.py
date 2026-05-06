from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from employee_agent.controller_client import ControllerClient, TaskItem
from employee_agent.config import Settings
from employee_agent.observability.logger import get_logger
from employee_agent.browser.auth import KeycloakAuthHelper
from employee_agent.sites.base import SiteRegistry
from employee_agent.llm.provider import get_llm
from employee_agent.reporting.results import TaskResult, package_result

if TYPE_CHECKING:
    from browser_use.browser.session import BrowserSession

# 하위 호환 별칭
RunTask = TaskItem

SITE_HOME_URLS: dict[str, str] = {
    "groupoffice": "https://group.kmuinfosec.click",
    "dms": "https://dms.kmuinfosec.click",
}

TerminalStatus = Literal["succeeded", "failed", "skipped"]


class _StatusReporter:
    """Context manager: __aexit__에서 정확히 1회 terminal status 보고."""

    def __init__(self, client: ControllerClient, task: TaskItem, cfg: Settings) -> None:
        self._client = client
        self._task = task
        self._cfg = cfg
        self._reported = False
        self._final_status: TerminalStatus | None = None
        self._error: str | None = None
        self._metadata: dict | None = None

    async def __aenter__(self) -> "_StatusReporter":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            if not self._reported:
                if issubclass(exc_type, asyncio.CancelledError):
                    status: TerminalStatus = "failed"
                    error_message: str | None = "cancelled"
                elif issubclass(exc_type, TimeoutError):
                    status = "failed"
                    error_message = "timeout"
                else:
                    status = "failed"
                    error_message = repr(exc_val) if exc_val is not None else "unknown_error"

                if self._final_status is not None:
                    status = self._final_status
                    error_message = self._error

                await self._report(status, error_message=error_message)
            return False

        if not self._reported:
            status = self._final_status if self._final_status is not None else "succeeded"
            await self._report(status, error_message=self._error)
        return False

    async def _report(self, status: TerminalStatus, error_message: str | None = None) -> None:
        if self._reported:
            return
        self._reported = True
        try:
            await self._client.report_status(
                run_task_id=self._task.run_task_id,
                status=status,
                employee_id=self._cfg.EMPLOYEE_ID,
                location_id=self._cfg.LOCATION_ID,
                error_message=error_message,
                metadata=self._metadata,
            )
        except Exception:
            pass

    async def succeed(self, metadata: dict | None = None) -> None:
        self._final_status = "succeeded"
        self._metadata = metadata

    async def skip(self, reason: str) -> None:
        self._final_status = "skipped"
        self._error = reason

    async def fail(self, reason: str) -> None:
        self._final_status = "failed"
        self._error = reason


async def run_task(
    task: TaskItem,
    cfg: Settings,
    client: ControllerClient,
    *,
    browser_session: "BrowserSession",
    budget_exceeded: bool = False,
    circuit_open: bool = False,
) -> None:
    log = get_logger().bind(
        run_task_id=task.run_task_id,
        task_type=task.task_type,
        site=task.site,
        module=task.module,
        action=task.action,
    )
    log.info("task_started")

    async with _StatusReporter(client, task, cfg) as reporter:
        if budget_exceeded:
            log.warning("task_skipped_budget")
            await client.emit_event(
                run_task_id=task.run_task_id,
                event_type="budget_exceeded",
                employee_id=cfg.EMPLOYEE_ID,
                location_id=cfg.LOCATION_ID,
            )
            await reporter.skip("daily_budget_exceeded")
            return

        if circuit_open:
            log.warning("task_skipped_circuit")
            await reporter.skip("circuit_open")
            return

        t0 = time.monotonic()
        await client.report_status(
            run_task_id=task.run_task_id,
            status="running",
            employee_id=cfg.EMPLOYEE_ID,
            location_id=cfg.LOCATION_ID,
        )
        log.info("task_running")

        if task.task_type == "clock_in":
            await _do_clock_in(task, cfg, log, browser_session)
            await reporter.succeed(metadata={"task_type": "clock_in"})

        elif task.task_type == "clock_out":
            await _do_clock_out(task, cfg, log, browser_session)
            await reporter.succeed(metadata={"task_type": "clock_out"})

        elif task.task_type == "work":
            # DMS(Nextcloud 기반): browser-use navigate_to 사용 금지 (3s SPA 타임아웃 → session reset)
            # Playwright가 browser-use의 active page(=pages[0])에 직접 navigate + 결정론적 로그인.
            # 새 탭을 만들지 않아 browser-use가 보는 page와 일치.
            if task.site == "dms":
                try:
                    pw, _browser, ctx = await _playwright_context_from_session(browser_session)
                    try:
                        pages = ctx.pages
                        pl_page = pages[0] if pages else await ctx.new_page()
                        auth = KeycloakAuthHelper(ctx, cfg)
                        await auth.login_dms(pl_page)
                        await pl_page.bring_to_front()
                        log.info("navigated_to_site", site=task.site, url=SITE_HOME_URLS["dms"])
                    finally:
                        await pw.stop()
                except Exception as e:
                    log.warning("dms_login_failed", error=repr(e))

            else:
                # GroupOffice 등 일반 site: browser-use navigate_to 사용
                home_url = SITE_HOME_URLS.get(task.site or "")
                if home_url:
                    try:
                        await browser_session.navigate_to(home_url)
                        log.info("navigated_to_site", site=task.site, url=home_url)
                    except Exception:
                        pass

            result = await _do_work(task, cfg, client, log, browser_session)
            await client.upload_result(
                run_task_id=task.run_task_id,
                employee_id=cfg.EMPLOYEE_ID,
                location_id=cfg.LOCATION_ID,
                result_root_path=str(Path(cfg.RESULTS_DIR) / task.run_task_id),
                screenshots_path=result.screenshots_path,
                browser_trace_path=result.browser_trace_path,
                metadata=result.metadata,
            )
            log.info("result_uploaded", **result.metadata)

            duration_ms = int((time.monotonic() - t0) * 1000)

            # browser_use Agent 자체 판정이 실패면 태스크 실패 처리
            if not result.metadata.get("is_successful", True):
                await reporter.fail("browser_use_goal_not_achieved")
                raise RuntimeError(
                    f"browser_use: goal not achieved "
                    f"(final_result={result.metadata.get('final_result')!r})"
                )

            await reporter.succeed(metadata={
                **result.metadata,
                "duration_ms": duration_ms,
            })

        else:
            log.error("unknown_task_type")
            await reporter.fail(f"unknown_task_type:{task.task_type}")


def _cdp_ws_to_http(ws_url: str) -> str:
    """ws://127.0.0.1:PORT/... → http://127.0.0.1:PORT"""
    m = re.match(r"ws://([^/]+)", ws_url)
    if m:
        return f"http://{m.group(1)}"
    return ws_url


async def _playwright_context_from_session(browser_session: "BrowserSession"):
    """BrowserSession이 실행 중인 Chrome에 Playwright를 CDP로 연결해 context 반환."""
    from playwright.async_api import async_playwright

    http_url = _cdp_ws_to_http(browser_session.cdp_url)
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(http_url)
    # 기존 context 재사용 (쿠키 공유)
    contexts = browser.contexts
    ctx = contexts[0] if contexts else await browser.new_context(ignore_https_errors=True)
    return pw, browser, ctx


async def _do_clock_in(
    task: TaskItem, cfg: Settings, log: object, browser_session: "BrowserSession"
) -> None:
    """Playwright를 BrowserSession Chrome에 CDP 연결해 결정론적 로그인.
    browser-use의 active page(pages[0])에서 직접 로그인 — 새 탭을 만들지 않음.
    로그인 후 브라우저는 열린 채 유지 — 이후 work 태스크가 같은 세션/page 사용.
    """
    pw, browser, ctx = await _playwright_context_from_session(browser_session)
    try:
        pages = ctx.pages
        page = pages[0] if pages else await ctx.new_page()
        auth = KeycloakAuthHelper(ctx, cfg)
        await auth.login_groupoffice(page)
        log.info("clock_in_complete")  # type: ignore[attr-defined]
    finally:
        await pw.stop()


async def _do_clock_out(
    task: TaskItem, cfg: Settings, log: object, browser_session: "BrowserSession"
) -> None:
    """clock_out = 브라우저 세션 종료 신호. 실제 닫기는 main의 finally가 담당."""
    log.info("clock_out_complete")  # type: ignore[attr-defined]


async def _do_work(
    task: TaskItem,
    cfg: Settings,
    client: ControllerClient,
    log: object,
    browser_session: "BrowserSession",
) -> TaskResult:
    from browser_use import Agent

    handler = SiteRegistry.get(task.site)
    goal = handler.build_goal(task.module, task.action, task, cfg=cfg)
    system_prompt = handler.system_prompt(cfg=cfg)
    max_steps = handler.max_steps(task.action)
    llm = get_llm(cfg)

    trace_dir = Path(cfg.RESULTS_DIR) / task.run_task_id
    trace_dir.mkdir(parents=True, exist_ok=True)

    def step_callback(state: object, output: object, step_num: int) -> None:
        log.info("browser_use_step", step=step_num, action=str(output)[:512])  # type: ignore[attr-defined]

    log.info("browser_use_start", goal=goal, max_steps=max_steps)  # type: ignore[attr-defined]

    agent = Agent(
        task=goal,
        llm=llm,
        browser_session=browser_session,   # 공유 세션 재사용
        extend_system_message=system_prompt,
        register_new_step_callback=step_callback,
        max_actions_per_step=3,
        use_vision=True,
    )

    history = await agent.run(max_steps=max_steps)

    return package_result(
        history=history,
        results_dir=cfg.RESULTS_DIR,
        run_task_id=task.run_task_id,
        trace_dir=trace_dir,
    )
