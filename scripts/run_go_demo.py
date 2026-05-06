#!/usr/bin/env python3
"""
GroupOffice 데모: 캘린더 / 태스크 / 노트 생성
  cd C:/Users/seclab/Desktop/ZTAgent/employee-agent
  python scripts/run_go_demo.py
"""
import ssl, urllib3, asyncio, sys, os, warnings
from datetime import datetime, timezone
from pathlib import Path

warnings.filterwarnings("ignore", category=ResourceWarning)
os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["PYTHONHTTPSVERIFY"] = "0"
os.environ["LITELLM_LOG"] = "ERROR"
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests as _req
_orig_req = _req.Session.request
def _no_verify(self, *a, **kw):
    kw["verify"] = False
    return _orig_req(self, *a, **kw)
_req.Session.request = _no_verify

import httpx as _httpx
_orig_client = _httpx.Client.__init__
def _httpx_no_verify(self, *a, **kw): kw["verify"] = False; _orig_client(self, *a, **kw)
_httpx.Client.__init__ = _httpx_no_verify
_orig_async = _httpx.AsyncClient.__init__
def _httpx_async_no_verify(self, *a, **kw): kw["verify"] = False; _orig_async(self, *a, **kw)
_httpx.AsyncClient.__init__ = _httpx_async_no_verify

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.chdir(Path(__file__).parent.parent)

from employee_agent.config import Settings
from employee_agent.controller_client import ControllerClient, TaskItem
from employee_agent.observability.logger import init_json_logger
from employee_agent.runner import run_task, _playwright_context_from_session
from employee_agent.browser.auth import KeycloakAuthHelper

import employee_agent.sites.groupoffice  # noqa: F401

class _NullClient(ControllerClient):
    async def report_status(self, *a, **kw) -> None: pass
    async def emit_event(self, *a, **kw) -> None: pass
    async def upload_result(self, *a, **kw) -> None: pass
    async def aclose(self) -> None: pass

_NOW = datetime.now(timezone.utc)

def _t(module: str, action: str, idx: int = 0) -> TaskItem:
    tid = f"demo-go-{module}-{action}-{idx:02d}"
    return TaskItem(
        run_task_id=tid, task_id=tid, task_type="work",
        site="groupoffice", module=module, action=action,
        scheduled_at=_NOW, status="pending",
    )

TASKS: list[TaskItem] = [
    _t("calendar", "switch_view"),
    _t("calendar", "create_event"),
    _t("tasks",    "view_tasks"),
    _t("tasks",    "create_or_update_task"),
    _t("notes",    "view_notes"),
    _t("notes",    "create_or_edit_note"),
]


async def main() -> None:
    from browser_use.browser.session import BrowserSession
    from browser_use.browser.profile import BrowserProfile

    cfg = Settings()
    init_json_logger(cfg.LOG_DIR)

    print(f"\nEmployee : {cfg.EMPLOYEE_ID} @ {cfg.LOCATION_ID}")
    print(f"LLM      : {cfg.LLM_MODEL}  |  Headless: {cfg.BROWSER_HEADLESS}")
    print(f"\n실행 태스크 ({len(TASKS)}개):")
    for t in TASKS:
        print(f"  {t.module}.{t.action}")
    print("=" * 60)

    client = _NullClient(cfg)
    profile = BrowserProfile(
        headless=cfg.BROWSER_HEADLESS,
        executable_path=cfg.BROWSER_EXECUTABLE_PATH or None,
        disable_security=True,
        keep_alive=True,
    )
    browser_session = BrowserSession(browser_profile=profile)
    await browser_session.start()

    succeeded, failed = 0, 0
    results: list[tuple[str, TaskItem]] = []

    try:
        pw, _browser, ctx = await _playwright_context_from_session(browser_session)
        try:
            await KeycloakAuthHelper(ctx, cfg).login_groupoffice()
            print("GroupOffice 로그인 완료\n")
        finally:
            await pw.stop()

        for task in TASKS:
            print(f"▶ {task.module}.{task.action}")
            try:
                await run_task(task, cfg, client, browser_session=browser_session)
                print(f"  [성공]\n")
                succeeded += 1
                results.append(("성공", task))
            except KeyboardInterrupt:
                print("\n[중단됨]")
                break
            except Exception as e:
                print(f"  [실패] {e}\n")
                failed += 1
                results.append(("실패", task))

    finally:
        await browser_session.stop()
        await client.aclose()

    total = succeeded + failed
    print("=" * 60)
    print(f"결과 요약: 성공 {succeeded} / 실패 {failed} / 전체 {total}")
    print("-" * 60)
    for mark, t in results:
        print(f"  [{mark}] {t.module}.{t.action}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
