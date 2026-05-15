import asyncio

from employee_agent.config import Settings
from employee_agent.controller_client import ControllerClient, DailyPlan
from employee_agent.observability.logger import init_json_logger, get_logger
from employee_agent.observability.resources import snapshot as _resource_snapshot
from employee_agent.scheduler import wait_until, sleep_until_next_fetch
from employee_agent.runner import run_task, BrowserUseGoalNotAchieved

import employee_agent.sites.groupoffice  # noqa: F401
import employee_agent.sites.dms          # noqa: F401


async def _make_browser_session(cfg: Settings):
    from browser_use.browser.session import BrowserSession
    from browser_use.browser.profile import BrowserProfile

    profile = BrowserProfile(
        headless=cfg.BROWSER_HEADLESS,
        executable_path=cfg.BROWSER_EXECUTABLE_PATH or None,
        disable_security=True,
        keep_alive=True,
    )
    session = BrowserSession(browser_profile=profile)
    await session.start()
    return session


async def run_day(
    cfg: Settings,
    client: ControllerClient,
    plan: DailyPlan,
    *,
    skip_wait: bool = False,
    max_work_tasks: int | None = None,
) -> None:
    """하루치 플랜 실행. skip_wait=True이면 scheduled_at 대기 없이 즉시 실행."""
    log = get_logger()

    tasks = plan.tasks
    if max_work_tasks is not None:
        clock_in  = [t for t in tasks if t.task_type == "clock_in"][:1]
        work      = [t for t in tasks if t.task_type == "work"][:max_work_tasks]
        clock_out = [t for t in tasks if t.task_type == "clock_out"][:1]
        tasks = clock_in + work + clock_out

    browser_session = await _make_browser_session(cfg)
    log.info("browser_started")
    consecutive_work_failures = 0
    threshold = cfg.CONSECUTIVE_WORK_FAILURE_THRESHOLD

    try:
        for task in tasks:
            if not skip_wait:
                await wait_until(task.scheduled_at)
            # task 직전 자원 baseline — 실패 시점과 비교하기 위한 기준선.
            log.info(
                "task_resource_baseline",
                run_task_id=task.run_task_id,
                task_type=task.task_type,
                **_resource_snapshot(),
            )
            task_failed = False
            likely_browser_dead = False
            try:
                await run_task(task, cfg, client, browser_session=browser_session)
            except asyncio.CancelledError:
                # 시스템 종료 신호: 즉시 전파
                raise
            except BrowserUseGoalNotAchieved as e:
                task_failed = True
                # steps=0 = 단 한 step도 못 만듦 → CDP/screenshot 깨짐 의심.
                # steps>0 = LLM이 풀지 못한 정상 실패 (세션 재생성과 무관).
                likely_browser_dead = (e.steps == 0)
                log.warning(
                    "task_failed_continue",
                    run_task_id=task.run_task_id,
                    task_type=task.task_type,
                    site=task.site,
                    module=task.module,
                    action=task.action,
                    steps=e.steps,
                    likely_browser_dead=likely_browser_dead,
                    error=repr(e),
                    **_resource_snapshot(),
                )
                if task.task_type == "clock_in":
                    log.error("clock_in_failed_aborting_day", run_task_id=task.run_task_id)
                    break
            except Exception as e:
                task_failed = True
                # 알 수 없는 예외 — 안전하게 브라우저 죽음으로 간주.
                likely_browser_dead = True
                log.warning(
                    "task_failed_continue",
                    run_task_id=task.run_task_id,
                    task_type=task.task_type,
                    site=task.site,
                    module=task.module,
                    action=task.action,
                    likely_browser_dead=likely_browser_dead,
                    error=repr(e),
                    **_resource_snapshot(),
                )
                if task.task_type == "clock_in":
                    log.error("clock_in_failed_aborting_day", run_task_id=task.run_task_id)
                    break

            # work 카운팅: 브라우저 깨짐 의심만 +1, LLM 정상 실패는 카운터 유지, 성공 시 reset.
            # Chrome/CDP가 일과 중 깨지면 세션 공유 구조상 회복 못 하므로 자가 회복.
            if task.task_type == "work":
                if not task_failed:
                    consecutive_work_failures = 0
                elif likely_browser_dead:
                    consecutive_work_failures += 1
                    if threshold > 0 and consecutive_work_failures >= threshold:
                        log.warning(
                            "browser_session_reset_triggered",
                            consecutive_work_failures=consecutive_work_failures,
                            threshold=threshold,
                            **_resource_snapshot(),
                        )
                        try:
                            await browser_session.stop()
                        except Exception as stop_err:
                            log.warning("browser_session_stop_failed", error=repr(stop_err))
                        try:
                            browser_session = await _make_browser_session(cfg)
                            log.info(
                                "browser_session_restarted",
                                **_resource_snapshot(),
                            )
                            consecutive_work_failures = 0
                        except Exception as start_err:
                            log.error(
                                "browser_session_restart_failed",
                                error=repr(start_err),
                                **_resource_snapshot(),
                            )
                            break
    finally:
        try:
            await browser_session.stop()
        except Exception as e:
            log.warning("browser_session_stop_failed_on_exit", error=repr(e))
        log.info("browser_stopped")


async def main() -> None:
    cfg = Settings()
    logger = init_json_logger(cfg.LOG_DIR)
    client = ControllerClient(cfg)

    logger.info(
        "employee_agent_started",
        employee_id=cfg.EMPLOYEE_ID,
        location_id=cfg.LOCATION_ID,
        **_resource_snapshot(),
    )

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
                await sleep_until_next_fetch(cfg.PLAN_FETCH_HOUR, cfg.PLAN_FETCH_MINUTE)
                continue

            await run_day(cfg, client, plan)
            await sleep_until_next_fetch(cfg.PLAN_FETCH_HOUR, cfg.PLAN_FETCH_MINUTE)

        except asyncio.CancelledError:
            logger.info("agent_cancelled")
            raise
        except Exception as e:
            logger.error("main_loop_error", error=repr(e))
            await asyncio.sleep(cfg.ERROR_RETRY_SECONDS)