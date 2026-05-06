import asyncio

from employee_agent.config import Settings
from employee_agent.controller_client import ControllerClient, DailyPlan
from employee_agent.observability.logger import init_json_logger, get_logger
from employee_agent.scheduler import wait_until, sleep_until_next_0630_kst
from employee_agent.runner import run_task

import employee_agent.sites.groupoffice  # noqa: F401
import employee_agent.sites.dms          # noqa: F401


async def run_day(
    cfg: Settings,
    client: ControllerClient,
    plan: DailyPlan,
    *,
    skip_wait: bool = False,
    max_work_tasks: int | None = None,
) -> None:
    """하루치 플랜 실행. skip_wait=True이면 scheduled_at 대기 없이 즉시 실행."""
    from browser_use.browser.session import BrowserSession
    from browser_use.browser.profile import BrowserProfile

    log = get_logger()

    tasks = plan.tasks
    if max_work_tasks is not None:
        clock_in  = [t for t in tasks if t.task_type == "clock_in"][:1]
        work      = [t for t in tasks if t.task_type == "work"][:max_work_tasks]
        clock_out = [t for t in tasks if t.task_type == "clock_out"][:1]
        tasks = clock_in + work + clock_out

    profile = BrowserProfile(
        headless=cfg.BROWSER_HEADLESS,
        executable_path=cfg.BROWSER_EXECUTABLE_PATH or None,
        disable_security=True,
        keep_alive=True,
    )
    browser_session = BrowserSession(browser_profile=profile)
    await browser_session.start()
    log.info("browser_started")

    try:
        for task in tasks:
            if not skip_wait:
                await wait_until(task.scheduled_at)
            await run_task(task, cfg, client, browser_session=browser_session)
    finally:
        await browser_session.stop()
        log.info("browser_stopped")


async def main() -> None:
    cfg = Settings()
    logger = init_json_logger(cfg.LOG_DIR)
    client = ControllerClient(cfg)

    logger.info("employee_agent_started", employee_id=cfg.EMPLOYEE_ID, location_id=cfg.LOCATION_ID)

    while True:
        try:
            plan = await client.get_today_plan(cfg.EMPLOYEE_ID, cfg.LOCATION_ID)
            logger.info("plan_received",
                        should_work_here=plan.should_work_here,
                        task_count=len(plan.tasks))

            if not plan.should_work_here or not plan.tasks:
                logger.info("no_work_today")
                await sleep_until_next_0630_kst()
                continue

            await run_day(cfg, client, plan)
            await sleep_until_next_0630_kst()

        except asyncio.CancelledError:
            logger.info("agent_cancelled")
            raise
        except Exception as e:
            logger.error("main_loop_error", error=repr(e))
            await asyncio.sleep(60)