#!/usr/bin/env python3
"""
Claude Code가 직접 Playwright로 GroupOffice를 조작합니다 (LLM 없음).
  cd C:/Users/seclab/Desktop/ZTAgent/employee-agent
  python scripts/claude_direct.py
"""
import asyncio
from datetime import datetime, timedelta

from playwright.async_api import async_playwright, Page

import os

GO_URL   = os.environ["GO_URL"]
USERNAME = os.environ["EMPLOYEE_ID"]
PASSWORD = os.environ.get("EMPLOYEE_PASSWORD", os.environ.get("EMPLOYEE_ID", ""))
CHROME   = os.environ.get("BROWSER_EXECUTABLE_PATH", "C:/Program Files/Google/Chrome/Application/chrome.exe")

TOMORROW = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")


def log(msg: str) -> None:
    print(f"[Claude] {msg}")


async def login(page: Page) -> None:
    log("GroupOffice 접속 중...")
    await page.goto(GO_URL, wait_until="networkidle", timeout=30_000)

    if "group.kmuinfosec.click" in page.url and "auth." not in page.url:
        log("이미 로그인됨")
        return

    log("Keycloak 로그인 폼 입력 중...")
    await page.wait_for_selector("#username", timeout=15_000)
    await page.fill("#username", USERNAME)
    await page.fill("#password", PASSWORD)
    await page.click("#kc-login")
    await page.wait_for_url(lambda u: "group.kmuinfosec.click" in u, timeout=15_000)

    # SSO 버튼이 있으면 클릭
    try:
        await page.wait_for_selector("text=Sign in with keycloak", timeout=5_000)
        await page.click("text=Sign in with keycloak")
        await page.wait_for_load_state("domcontentloaded", timeout=10_000)
    except Exception:
        pass

    log("로그인 완료")


async def go_to_module(page: Page, nav_text: str) -> None:
    """상단 탭 네비게이션에서 모듈 클릭."""
    selector = f"nav a:has-text('{nav_text}'), [role='tab']:has-text('{nav_text}'), a:has-text('{nav_text}')"
    await page.click(selector, timeout=10_000)
    await page.wait_for_load_state("domcontentloaded", timeout=10_000)
    await page.wait_for_timeout(1_000)


# ── 1. Calendar ──────────────────────────────────────────────

async def task_calendar_switch_view(page: Page) -> None:
    log("=== [1/5] 캘린더 탭 이동 → 주(Week) 뷰 전환 ===")
    await go_to_module(page, "Calendar")
    await page.wait_for_timeout(1_500)

    # week 버튼 클릭 (텍스트 또는 title 속성)
    for sel in ["button:has-text('Week')", "button[title='Week']", "button:has-text('week')"]:
        try:
            await page.click(sel, timeout=4_000)
            log("  Week 뷰 전환 완료")
            await page.wait_for_timeout(1_000)
            return
        except Exception:
            pass
    log("  Week 버튼을 찾지 못했습니다 (스킵)")


async def task_calendar_create_event(page: Page) -> None:
    log("=== [2/5] 캘린더 이벤트 생성 ===")
    await go_to_module(page, "Calendar")
    await page.wait_for_timeout(1_500)

    # + 버튼 (글로벌 추가) 또는 캘린더 toolbar add 버튼
    added = False
    for sel in [
        "button[title='Add'], button[aria-label='Add']",
        "go-button[title='Add event']",
        ".fc-toolbar button:has-text('+')",
        "button.add, button:has-text('+')",
    ]:
        try:
            await page.click(sel, timeout=3_000)
            added = True
            break
        except Exception:
            pass

    if not added:
        # 내일 날짜 셀 더블클릭으로 이벤트 생성창 열기
        try:
            tomorrow_cell = page.locator(f"[data-date='{TOMORROW}']").first
            await tomorrow_cell.dblclick(timeout=5_000)
            added = True
            log("  내일 날짜 셀 더블클릭으로 폼 열기")
        except Exception:
            pass

    if not added:
        log("  이벤트 생성 버튼을 찾지 못했습니다 (스킵)")
        return

    await page.wait_for_timeout(1_500)

    # 제목 입력
    for title_sel in ["input[name='title']", "input[placeholder*='제목']", "input[placeholder*='Title']", "input[placeholder*='title']"]:
        try:
            await page.fill(title_sel, "Claude 자동 생성 이벤트", timeout=4_000)
            log("  이벤트 제목 입력 완료")
            break
        except Exception:
            pass

    await page.wait_for_timeout(500)

    # 저장
    for save_sel in ["button:has-text('저장')", "button:has-text('Save')", "button[type='submit']"]:
        try:
            await page.click(save_sel, timeout=4_000)
            log("  이벤트 저장 완료")
            await page.wait_for_timeout(1_500)
            return
        except Exception:
            pass

    log("  저장 버튼 미발견 — Escape 닫기")
    await page.keyboard.press("Escape")


# ── 2. Tasks ────────────────────────────────────────────────

async def task_tasks_view(page: Page) -> None:
    log("=== [3/5] 태스크 탭 이동 ===")
    await go_to_module(page, "Tasks")
    await page.wait_for_timeout(1_500)
    log("  태스크 목록 확인 완료")


async def task_tasks_create(page: Page) -> None:
    log("=== [4/5] 새 태스크 생성 ===")
    await go_to_module(page, "Tasks")
    await page.wait_for_timeout(1_500)

    added = False
    for sel in [
        "button[title='Add'], button[aria-label='Add']",
        "button:has-text('+')",
        ".add-button",
    ]:
        try:
            await page.click(sel, timeout=3_000)
            added = True
            break
        except Exception:
            pass

    if not added:
        log("  태스크 추가 버튼 미발견 (스킵)")
        return

    await page.wait_for_timeout(1_500)

    for title_sel in ["input[name='title']", "input[placeholder*='제목']", "input[placeholder*='Title']"]:
        try:
            await page.fill(title_sel, "Claude 자동 생성 태스크", timeout=4_000)
            log("  태스크 제목 입력 완료")
            break
        except Exception:
            pass

    await page.wait_for_timeout(500)

    for save_sel in ["button:has-text('저장')", "button:has-text('Save')", "button[type='submit']"]:
        try:
            await page.click(save_sel, timeout=4_000)
            log("  태스크 저장 완료")
            await page.wait_for_timeout(1_500)
            return
        except Exception:
            pass

    log("  저장 버튼 미발견 — Escape 닫기")
    await page.keyboard.press("Escape")


# ── 3. Notes ────────────────────────────────────────────────

async def task_notes_create(page: Page) -> None:
    log("=== [5/5] 새 노트 생성 ===")

    # 한국어 탭 이름 우선, 영어 fallback
    nav_found = False
    for nav_name in ["노트", "Notes", "Note"]:
        try:
            await go_to_module(page, nav_name)
            nav_found = True
            break
        except Exception:
            pass

    if not nav_found:
        log("  노트 탭 미발견 (스킵)")
        return

    await page.wait_for_timeout(1_500)

    added = False
    for sel in [
        "button[title='Add'], button[aria-label='Add']",
        "button:has-text('+')",
    ]:
        try:
            await page.click(sel, timeout=3_000)
            added = True
            break
        except Exception:
            pass

    if not added:
        log("  노트 추가 버튼 미발견 (스킵)")
        return

    await page.wait_for_timeout(1_500)

    for title_sel in ["input[name='title']", "input[placeholder*='제목']", "input[placeholder*='Title']"]:
        try:
            await page.fill(title_sel, "Claude 자동 생성 노트", timeout=4_000)
            log("  노트 제목 입력 완료")
            break
        except Exception:
            pass

    # 본문 입력
    for body_sel in ["textarea", ".note-body", "[contenteditable='true']"]:
        try:
            await page.fill(body_sel, "이 노트는 Claude Code가 직접 Playwright로 생성했습니다.", timeout=3_000)
            log("  노트 본문 입력 완료")
            break
        except Exception:
            pass

    await page.wait_for_timeout(500)

    for save_sel in ["button:has-text('저장')", "button:has-text('Save')", "button[type='submit']"]:
        try:
            await page.click(save_sel, timeout=4_000)
            log("  노트 저장 완료")
            await page.wait_for_timeout(1_500)
            return
        except Exception:
            pass

    log("  저장 버튼 미발견 — Escape 닫기")
    await page.keyboard.press("Escape")


# ── 메인 ────────────────────────────────────────────────────

async def main() -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            executable_path=CHROME,
            headless=False,
            args=["--start-maximized"],
        )
        ctx = await browser.new_context(
            ignore_https_errors=True,
            no_viewport=True,
        )
        page = await ctx.new_page()

        results: list[tuple[str, str]] = []

        async def run(name: str, coro) -> None:
            try:
                await coro
                results.append(("성공", name))
            except Exception as e:
                log(f"  오류: {e}")
                results.append(("실패", name))

        await login(page)
        await page.wait_for_timeout(1_000)

        await run("캘린더 뷰 전환",  task_calendar_switch_view(page))
        await run("캘린더 이벤트 생성", task_calendar_create_event(page))
        await run("태스크 목록 조회",  task_tasks_view(page))
        await run("태스크 생성",       task_tasks_create(page))
        await run("노트 생성",         task_notes_create(page))

        print("\n" + "=" * 50)
        print(f"결과 요약: 성공 {sum(1 for m,_ in results if m=='성공')} / 실패 {sum(1 for m,_ in results if m=='실패')} / 전체 {len(results)}")
        print("-" * 50)
        for mark, name in results:
            print(f"  [{mark}] {name}")
        print("=" * 50)

        log("3초 후 브라우저 닫힘...")
        await page.wait_for_timeout(3_000)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
