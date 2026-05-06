from __future__ import annotations


class BudgetGuard:
    """Track daily LLM token spend against a configurable USD budget."""

    def __init__(
        self,
        daily_budget_usd: float,
        price_per_1k_tokens: float = 0.002,
    ) -> None:
        self._daily_budget_usd = daily_budget_usd
        self._price_per_1k_tokens = price_per_1k_tokens
        self._spent_usd: float = 0.0

    def record_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        total_tokens = prompt_tokens + completion_tokens
        cost = (total_tokens / 1000.0) * self._price_per_1k_tokens
        self._spent_usd += cost

    def is_daily_exceeded(self) -> bool:
        return self._spent_usd >= self._daily_budget_usd

    def reset_daily(self) -> None:
        self._spent_usd = 0.0

    @property
    def spent_usd(self) -> float:
        return self._spent_usd
