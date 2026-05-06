from playwright.async_api import BrowserContext, Page
from employee_agent.config import Settings
import structlog

logger = structlog.get_logger()

SITE_URLS = {
    "groupoffice": "https://group.kmuinfosec.click",
    "dms": "https://dms.kmuinfosec.click",
}


class KeycloakAuthHelper:
    def __init__(self, context: BrowserContext, cfg: Settings):
        self._context = context
        self._cfg = cfg

    async def login_groupoffice(self, page: Page) -> Page:
        """
        Group-Office 로그인. 주어진 page에서 진행 (새 탭을 만들지 않음).
        - 세션 쿠키 없음 → Keycloak 폼 입력 → Sign in with keycloak
        - 세션 쿠키 있음 → 이미 로그인됨, 바로 반환
        쿠키는 BrowserContext 단위라 어떤 page든 한 번 인증되면 ctx 전체에 적용됨.
        """
        # 1. 사이트 접속 (세션 쿠키 있으면 Keycloak 생략됨)
        await page.goto(SITE_URLS["groupoffice"], wait_until="networkidle", timeout=30000)
        current_url = page.url

        # 2. 이미 Group-Office에 있으면 로그인 완료
        if "group.kmuinfosec.click" in current_url and "auth." not in current_url:
            logger.info("groupoffice_already_logged_in", employee_id=self._cfg.EMPLOYEE_ID)
            return page

        # 3. Keycloak 폼 입력
        await page.wait_for_selector("#username", timeout=15000)
        await page.fill("#username", self._cfg.EMPLOYEE_ID)
        await page.fill("#password", self._get_password())
        await page.click("#kc-login")

        # 4. group.kmuinfosec.click/? 로 리다이렉션 대기
        await page.wait_for_url(
            lambda url: "group.kmuinfosec.click" in url,
            timeout=15000,
        )

        # 5. SSO 버튼이 있으면 클릭, 없으면 Keycloak 로그인만으로 완료된 것
        try:
            await page.wait_for_selector("text=Sign in with keycloak", timeout=5000)
            await page.click("text=Sign in with keycloak")
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass  # 버튼 없이 바로 앱으로 진입됨

        logger.info("groupoffice_login_success", employee_id=self._cfg.EMPLOYEE_ID)
        return page

    async def login_dms(self, page: Page) -> Page:
        """DMS(Nextcloud) 로그인 — 주어진 page에서 진행 (새 탭을 만들지 않음).
        Keycloak 세션이 있으면 버튼 클릭만으로 완료.
        """
        await page.goto(SITE_URLS["dms"], wait_until="networkidle", timeout=30000)
        current_url = page.url

        if "dms.kmuinfosec.click" in current_url and "/login" not in current_url:
            logger.info("dms_already_logged_in", employee_id=self._cfg.EMPLOYEE_ID)
            return page

        try:
            await page.wait_for_selector("a[href*='keycloak'], a:has-text('keycloak')", timeout=10000)
            await page.click("a[href*='keycloak'], a:has-text('keycloak')")
            await page.wait_for_url(
                lambda url: "dms.kmuinfosec.click" in url and "/login" not in url,
                timeout=15000,
            )
        except Exception as e:
            logger.warning("dms_login_button_failed", error=repr(e))

        logger.info("dms_login_success", employee_id=self._cfg.EMPLOYEE_ID)
        return page

    async def do_logout(self, site: str) -> None:
        """결정론적 로그아웃"""
        page = await self._context.new_page()
        try:
            url = SITE_URLS[site]
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)

            if site == "groupoffice":
                # Web Component 렌더링 대기 후 아바타 클릭 → 로그아웃
                await page.wait_for_load_state("networkidle", timeout=15000)
                await page.locator("go-avatar").first.click(timeout=10000)
                await page.click("#logout, a:has-text('로그아웃'), [data-action='logout']", timeout=5000)
            elif site == "dms":
                # DMS: 설정 메뉴 버튼 → 로그아웃
                await page.click("button[aria-label='설정 메뉴']", timeout=5000)
                await page.click("#logout, a:has-text('로그아웃')", timeout=5000)

            logger.info("logout_success", site=site)
        except Exception as e:
            logger.warning("logout_failed", site=site, error=repr(e))
        finally:
            await page.close()

    def _get_password(self) -> str:
        """자격증명 조회 — 현재는 EMPLOYEE_ID와 동일 (테스트 환경)"""
        # TODO: Docker secret 파일 또는 Controller credential endpoint 연동
        import os
        secret_path = "/run/secrets/employee_password"
        if os.path.exists(secret_path):
            return open(secret_path).read().strip()
        # 테스트 환경: ID와 동일한 패스워드
        return self._cfg.EMPLOYEE_ID
