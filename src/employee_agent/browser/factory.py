from playwright.async_api import async_playwright, Browser, BrowserContext
from employee_agent.config import Settings
from employee_agent.browser.session import SessionManager


class BrowserFactory:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def create(self) -> BrowserContext:
        """Playwright BrowserContext 초기화 (storage_state 로드 포함)"""
        self._playwright = await async_playwright().start()
        launch_kwargs: dict = {
            "headless": self.cfg.BROWSER_HEADLESS,
            "args": ["--no-sandbox", "--disable-dev-shm-usage"],
        }
        if self.cfg.BROWSER_EXECUTABLE_PATH:
            launch_kwargs["executable_path"] = self.cfg.BROWSER_EXECUTABLE_PATH
        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        session_mgr = SessionManager(self.cfg.PROFILE_DIR)
        storage_state = session_mgr.load()  # 없으면 None

        self._context = await self._browser.new_context(
            storage_state=storage_state,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            ignore_https_errors=True,
        )
        return self._context

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
