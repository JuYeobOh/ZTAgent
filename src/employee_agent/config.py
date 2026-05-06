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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
