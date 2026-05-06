from __future__ import annotations

import pytest

from employee_agent.llm.budgets import BudgetGuard


def test_budget_not_exceeded():
    guard = BudgetGuard(daily_budget_usd=1.0)
    guard.record_usage(100, 100)  # 200 tokens * 0.002/1k = 0.0004 USD
    assert not guard.is_daily_exceeded()


def test_budget_exceeded():
    guard = BudgetGuard(daily_budget_usd=0.001)
    guard.record_usage(1000, 1000)  # 2000 tokens * 0.002/1k = 0.004 USD > 0.001
    assert guard.is_daily_exceeded()


def test_reset():
    guard = BudgetGuard(daily_budget_usd=0.001)
    guard.record_usage(1000, 1000)
    assert guard.is_daily_exceeded()
    guard.reset_daily()
    assert not guard.is_daily_exceeded()


def test_spent_usd_property():
    guard = BudgetGuard(daily_budget_usd=10.0)
    guard.record_usage(500, 500)  # 1000 tokens * 0.002/1k = 0.002 USD
    assert abs(guard.spent_usd - 0.002) < 1e-9


def test_custom_price_per_1k():
    guard = BudgetGuard(daily_budget_usd=1.0, price_per_1k_tokens=0.01)
    guard.record_usage(1000, 0)  # 1000 tokens * 0.01/1k = 0.01 USD
    assert abs(guard.spent_usd - 0.01) < 1e-9
    assert not guard.is_daily_exceeded()


def test_accumulated_usage():
    guard = BudgetGuard(daily_budget_usd=0.005)
    guard.record_usage(500, 500)   # 0.002 USD
    guard.record_usage(500, 500)   # 0.002 USD  -> total 0.004 USD
    assert not guard.is_daily_exceeded()
    guard.record_usage(500, 500)   # 0.002 USD  -> total 0.006 USD > 0.005
    assert guard.is_daily_exceeded()


def test_reset_clears_accumulation():
    guard = BudgetGuard(daily_budget_usd=0.005)
    guard.record_usage(1000, 1000)
    guard.reset_daily()
    assert guard.spent_usd == 0.0
    assert not guard.is_daily_exceeded()
