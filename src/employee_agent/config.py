from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    EMPLOYEE_ID: str
    LOCATION_ID: str
    WORKER_GROUP: str = "enterprise"
    CONTROLLER_URL: str
    PROFILE_DIR: str = "/app/profile"
    RESULTS_DIR: str = "/app/results"
    LOG_DIR: str = "/app/logs"
    TZ: str = "Asia/Seoul"
    BROWSER_HEADLESS: bool = True
    BROWSER_EXECUTABLE_PATH: str = ""  # 빈 문자열이면 Playwright 기본 Chromium 사용
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o"
    LLM_API_KEY: str = ""
    LLM_DAILY_BUDGET_USD: float = 10.0

    # ── 운영 다이얼 ──────────────────────────────────────
    # Plan fetch 시각 (KST). Controller의 daily plan 생성 시각보다 늦어야 한다.
    # 운영 기본: 06:30 (Controller가 06:00에 plan 생성).
    # 테스트 시: PLAN_FETCH_HOUR=1, PLAN_FETCH_MINUTE=10 식으로 override.
    PLAN_FETCH_HOUR: int = 6
    PLAN_FETCH_MINUTE: int = 30
    # main loop가 예외로 빠졌을 때 다음 시도까지 sleep
    ERROR_RETRY_SECONDS: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
