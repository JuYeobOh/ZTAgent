import json
from pathlib import Path
from playwright.async_api import BrowserContext


class SessionManager:
    def __init__(self, profile_dir: str):
        self._path = Path(profile_dir) / "storage_state.json"

    def load(self) -> dict | None:
        """storage_state 파일이 있으면 dict 반환, 없으면 None"""
        if self._path.exists():
            return json.loads(self._path.read_text(encoding="utf-8"))
        return None

    async def save(self, context: BrowserContext) -> None:
        """현재 BrowserContext의 storage_state를 파일에 저장"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        state = await context.storage_state()
        self._path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.exists()
