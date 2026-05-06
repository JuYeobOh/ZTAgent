#!/usr/bin/env python3
"""
E2E 테스트: 아래 TASKS 목록에서 실행할 태스크를 주석 해제해서 지정

실행:
    cd C:/Users/seclab/Desktop/ZTAgent/employee-agent
    python scripts/test_e2e.py
"""
import ssl
import urllib3
import asyncio
import sys
import os
import warnings
import random

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
import employee_agent.sites.dms          # noqa: F401


class _NullClient(ControllerClient):
    """Controller API 호출을 모두 무시하는 테스트용 클라이언트."""
    async def report_status(self, *a, **kw) -> None: pass
    async def emit_event(self, *a, **kw) -> None: pass
    async def upload_result(self, *a, **kw) -> None: pass
    async def aclose(self) -> None: pass

_NOW = datetime.now(timezone.utc)

def _t(site: str, module: str, action: str, idx: int = 0) -> TaskItem:
    tid = f"test-{site}-{module}-{action}-{idx:02d}"
    return TaskItem(
        run_task_id=tid,
        task_id=tid,
        task_type="work",
        site=site,
        module=module,
        action=action,
        scheduled_at=_NOW,
        status="pending",
    )


# ============================================================
#  실행할 태스크를 주석 해제하세요 (순서대로 실행됩니다)
# ============================================================
TASKS: list[TaskItem] = [

    # ── GroupOffice: 캘린더 ───────────────────────────────────
    # _t("groupoffice", "calendar",     "switch_view"),
    # _t("groupoffice", "calendar",     "create_event"),
    # _t("groupoffice", "calendar",     "manage_category"),
    # _t("groupoffice", "calendar",     "assign_category"),

    # ── GroupOffice: 주소록 ───────────────────────────────────
    # _t("groupoffice", "address_book", "view_contacts"),
    # _t("groupoffice", "address_book", "search_contact"),
    # _t("groupoffice", "address_book", "add_contact"),
    # _t("groupoffice", "address_book", "add_organization"),
    # _t("groupoffice", "address_book", "comment_contact"),

    # ── GroupOffice: 할일 ─────────────────────────────────────
    # _t("groupoffice", "tasks",        "view_tasks"),
    # _t("groupoffice", "tasks",        "create_or_update_task"),
    # _t("groupoffice", "tasks",        "complete_task"),
    # _t("groupoffice", "tasks",        "comment_task"),
    # _t("groupoffice", "tasks",        "manage_category"),
    # _t("groupoffice", "tasks",        "assign_category"),

    # ── GroupOffice: 노트 ─────────────────────────────────────
    # _t("groupoffice", "notes",        "view_notes"),
    # _t("groupoffice", "notes",        "create_note"),
    # _t("groupoffice", "notes",        "create_or_edit_note"),
    # _t("groupoffice", "notes",        "comment_note"),
    # _t("groupoffice", "notes",        "manage_notebook"),

    # ── GroupOffice: 북마크 ───────────────────────────────────
    # _t("groupoffice", "bookmarks",    "view_bookmarks"),
    # _t("groupoffice", "bookmarks",    "create_bookmark"),
    # _t("groupoffice", "bookmarks",    "manage_bookmark"),

    # ── DMS (Nextcloud): 파일 ─────────────────────────────────
    # _t("dms", "files",   "view_files"),
    # _t("dms", "files",   "view_recent"),
    # _t("dms", "files",   "view_favorites"),
    # _t("dms", "files",   "browse_directory"),
    # _t("dms", "files",   "upload_file"),
    _t("dms", "files",   "create_folder"),
    # _t("dms", "files",   "rename_file"),
    # _t("dms", "files",   "move_file"),
    # _t("dms", "files",   "team_folder_browse"),
    # _t("dms", "files",   "team_folder_create"),

    # ── DMS (Nextcloud): 공유 ─────────────────────────────────
    # _t("dms", "sharing", "share_file"),

    # ── DMS (Nextcloud): 검색 ─────────────────────────────────
    # _t("dms", "search",  "search_files"),
    # _t("dms", "common",  "search"),

]
# ============================================================


async def main() -> None:
    from browser_use.browser.session import BrowserSession
    from browser_use.browser.profile import BrowserProfile

    cfg = Settings()
    init_json_logger(cfg.LOG_DIR)

    if not TASKS:
        print("실행할 태스크가 없습니다. TASKS 목록에서 원하는 항목을 주석 해제하세요.")
        return

    print(f"\nEmployee : {cfg.EMPLOYEE_ID} @ {cfg.LOCATION_ID}")
    print(f"LLM model : {cfg.LLM_MODEL}  |  Headless: {cfg.BROWSER_HEADLESS}")
    print(f"\n실행 태스크 ({len(TASKS)}개):")
    for t in TASKS:
        print(f"  {t.site:12s} {t.module}.{t.action}")
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

    try:
        # GroupOffice 결정론적 로그인 (DMS SSO 세션도 여기서 확립)
        # browser-use의 active page(pages[0])에서 직접 로그인 — 새 탭 만들지 않음
        pw, _browser, ctx = await _playwright_context_from_session(browser_session)
        try:
            pages = ctx.pages
            page = pages[0] if pages else await ctx.new_page()
            await KeycloakAuthHelper(ctx, cfg).login_groupoffice(page)
            print("GroupOffice 로그인 완료\n")
        finally:
            await pw.stop()

        succeeded = 0
        failed = 0
        results: list[tuple[str, TaskItem]] = []

        tasks_this_round = TASKS.copy()
        random.shuffle(tasks_this_round)
        for task in tasks_this_round:
            print(f"▶ {task.site} / {task.module}.{task.action}")
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
        print(f"  [{mark}] {t.site:12s} {t.module}.{t.action}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
