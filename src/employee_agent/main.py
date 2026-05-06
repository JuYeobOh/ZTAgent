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
            try:
                await run_task(task, cfg, client, browser_session=browser_session)
            except asyncio.CancelledError:
                # 시스템 종료 신호: 즉시 전파
                raise
            except Exception as e:
                log.warning(
                    "task_failed_continue",
                    run_task_id=task.run_task_id,
                    task_type=task.task_type,
                    site=task.site,
                    module=task.module,
                    action=task.action,
                    error=repr(e),
                )
                # clock_in 실패는 치명적 — 인증 없이 work 진행 무의미. 그날 종료.
                if task.task_type == "clock_in":
                    log.error("clock_in_failed_aborting_day", run_task_id=task.run_task_id)
                    break
                # work / clock_out 실패는 다음 task로 계속 진행.
                # 다음 task의 _prepare_for_work이 reload+자동 로그인으로 자연스럽게 복구.
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
            # plan 풀 dump → /app/logs/agent_YYYYMMDD.jsonl 에 한 줄로 떨어짐
            # → 호스트 /data/zt/logs/{loc}/{eid}/ → 매시간 S3 sync로 들어감
            logger.info(
                "plan_received",
                work_date=plan.work_date,
                should_work_here=plan.should_work_here,
                requested_location_id=plan.requested_location_id,
                assigned_location_id=plan.assigned_location_id,
                clock_in_at=plan.clock_in_at.isoformat() if plan.clock_in_at else None,
                clock_out_at=plan.clock_out_at.isoformat() if plan.clock_out_at else None,
                task_count=len(plan.tasks),
                tasks=[t.model_dump(mode="json") for t in plan.tasks],
            )

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