from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class GoalResult:
    goal: str
    template_used: str

class SiteHandler(ABC):
    @abstractmethod
    def build_goal(self, module: str, action: str, task=None, cfg=None) -> str:
        """action → 자연어 goal 텍스트 반환 (매 호출마다 다를 수 있음)"""
        ...

    @abstractmethod
    def system_prompt(self, cfg=None) -> str:
        """사이트별 browser-use system prompt"""
        ...

    def max_steps(self, action: str) -> int:
        """action 난이도별 최대 step 수"""
        return 14



class SiteRegistry:
    _handlers: dict[str, SiteHandler] = {}

    @classmethod
    def register(cls, site: str, handler: SiteHandler) -> None:
        cls._handlers[site] = handler

    @classmethod
    def get(cls, site: str) -> SiteHandler:
        if site not in cls._handlers:
            raise KeyError(f"Unknown site: {site}. Registered: {list(cls._handlers)}")
        return cls._handlers[site]
