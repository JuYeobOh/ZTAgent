from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from employee_agent.llm.breaker import CircuitBreaker, State


@pytest.mark.asyncio
async def test_closed_to_open_on_failure_rate():
    """10 failures out of 10 samples (100% >= 80%) -> OPEN."""
    emit = AsyncMock()
    cb = CircuitBreaker(emit_event=emit, min_samples=10, failure_threshold=0.80)

    for _ in range(10):
        await cb.record_failure()

    assert cb._state == State.OPEN
    emit.assert_called()
    call_kwargs = emit.call_args
    assert call_kwargs.kwargs.get("event_type") == "circuit_open" or \
           call_kwargs[1].get("event_type") == "circuit_open" or \
           "circuit_open" in str(call_kwargs)


@pytest.mark.asyncio
async def test_open_is_open_returns_true():
    """In OPEN state is_open() returns True."""
    emit = AsyncMock()
    cb = CircuitBreaker(emit_event=emit, min_samples=10, failure_threshold=0.80)

    for _ in range(10):
        await cb.record_failure()

    assert cb.is_open() is True


@pytest.mark.asyncio
async def test_open_to_half_open_after_duration():
    """After open_duration seconds, is_open() returns False (half_open)."""
    emit = AsyncMock()
    cb = CircuitBreaker(
        emit_event=emit,
        min_samples=10,
        failure_threshold=0.80,
        open_duration=3600,
    )

    for _ in range(10):
        await cb.record_failure()

    assert cb._state == State.OPEN
    start = cb._open_at

    with patch("employee_agent.llm.breaker.time.time", return_value=start + 3601):
        result = cb.is_open()

    assert result is False
    assert cb._state == State.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_allows_single_probe():
    """In HALF_OPEN, allow_probe() returns True once then False."""
    emit = AsyncMock()
    cb = CircuitBreaker(
        emit_event=emit,
        min_samples=10,
        failure_threshold=0.80,
        open_duration=3600,
    )

    for _ in range(10):
        await cb.record_failure()

    start = cb._open_at
    with patch("employee_agent.llm.breaker.time.time", return_value=start + 3601):
        cb.is_open()  # triggers HALF_OPEN transition

    assert cb.allow_probe() is True
    assert cb.allow_probe() is False  # second call blocked


@pytest.mark.asyncio
async def test_half_open_to_closed_on_probe_success():
    """Probe success in HALF_OPEN -> CLOSED."""
    emit = AsyncMock()
    cb = CircuitBreaker(
        emit_event=emit,
        min_samples=10,
        failure_threshold=0.80,
        open_duration=3600,
    )

    for _ in range(10):
        await cb.record_failure()

    start = cb._open_at
    with patch("employee_agent.llm.breaker.time.time", return_value=start + 3601):
        cb.is_open()  # -> HALF_OPEN

    cb.allow_probe()  # mark probe in-flight
    await cb.record_success()

    assert cb._state == State.CLOSED
    # Check circuit_closed event was emitted
    event_types = [
        c.kwargs.get("event_type") or c[1].get("event_type")
        for c in emit.call_args_list
    ]
    assert "circuit_closed" in event_types


@pytest.mark.asyncio
async def test_half_open_to_open_on_probe_failure():
    """Probe failure in HALF_OPEN -> OPEN again."""
    emit = AsyncMock()
    cb = CircuitBreaker(
        emit_event=emit,
        min_samples=10,
        failure_threshold=0.80,
        open_duration=3600,
    )

    for _ in range(10):
        await cb.record_failure()

    start = cb._open_at
    with patch("employee_agent.llm.breaker.time.time", return_value=start + 3601):
        cb.is_open()  # -> HALF_OPEN

    cb.allow_probe()  # mark probe in-flight
    await cb.record_failure()

    assert cb._state == State.OPEN


@pytest.mark.asyncio
async def test_timeout_secondary_trigger():
    """30-minute window with > 8 timeouts triggers OPEN via secondary path."""
    emit = AsyncMock()
    cb = CircuitBreaker(
        emit_event=emit,
        min_samples=100,        # high: primary trigger won't fire
        failure_threshold=0.80,
        timeout_window=1800,
        timeout_max=8,
    )

    # Record 9 timeouts (> timeout_max of 8) -> secondary trigger
    for _ in range(9):
        await cb.record_timeout()

    assert cb._state == State.OPEN

    # Verify secondary event emitted
    event_types = [
        c.kwargs.get("event_type") or c[1].get("event_type")
        for c in emit.call_args_list
    ]
    assert "timeout_secondary" in event_types


@pytest.mark.asyncio
async def test_emit_event_called_with_circuit_open():
    """emit_event receives 'circuit_open' when primary trigger fires."""
    emit = AsyncMock()
    cb = CircuitBreaker(emit_event=emit, min_samples=5, failure_threshold=0.80)

    for _ in range(5):
        await cb.record_failure()

    assert emit.called
    # Find a call with circuit_open
    found = any(
        (c.kwargs.get("event_type") == "circuit_open" or
         c[1].get("event_type") == "circuit_open")
        for c in emit.call_args_list
    )
    assert found, f"Expected 'circuit_open' event; calls were: {emit.call_args_list}"


@pytest.mark.asyncio
async def test_below_threshold_stays_closed():
    """8 out of 10 calls succeeds -> failure rate 20% < 80%, stays CLOSED."""
    emit = AsyncMock()
    cb = CircuitBreaker(emit_event=emit, min_samples=10, failure_threshold=0.80)

    for _ in range(8):
        await cb.record_success()
    for _ in range(2):
        await cb.record_failure()

    assert cb._state == State.CLOSED
    assert not cb.is_open()
