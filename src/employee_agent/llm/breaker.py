from __future__ import annotations

import time
from collections import deque
from enum import Enum
from typing import Awaitable, Callable


class State(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """3-state circuit breaker (CLOSED -> OPEN -> HALF_OPEN -> CLOSED).

    Primary trigger: rolling 5-minute window, >= failure_threshold rate with
    at least min_samples calls.
    Secondary trigger: >= timeout_max timeouts within timeout_window seconds.
    """

    def __init__(
        self,
        emit_event: Callable[..., Awaitable[None]],
        window_seconds: int = 300,
        min_samples: int = 10,
        failure_threshold: float = 0.80,
        open_duration: int = 3600,
        timeout_window: int = 1800,
        timeout_max: int = 8,
        timeout_weight: float = 0.5,
    ) -> None:
        self._emit_event = emit_event
        self._window_seconds = window_seconds
        self._min_samples = min_samples
        self._failure_threshold = failure_threshold
        self._open_duration = open_duration
        self._timeout_window = timeout_window
        self._timeout_max = timeout_max
        self._timeout_weight = timeout_weight

        # (timestamp, failure_weight) — 0.0=success, 1.0=failure, 0.5=timeout
        self._calls: deque[tuple[float, float]] = deque()
        # timestamps of timeout events — secondary trigger window
        self._timeouts: deque[float] = deque()

        self._state: State = State.CLOSED
        self._open_at: float | None = None
        self._probe_in_flight: bool = False

    # ------------------------------------------------------------------
    # Public recording API
    # ------------------------------------------------------------------

    async def record_success(self) -> None:
        now = time.time()
        self._calls.append((now, 0.0))
        self._evict(now)

        if self._state == State.HALF_OPEN and self._probe_in_flight:
            self._probe_in_flight = False
            await self._transition(State.CLOSED)

    async def record_failure(self) -> None:
        now = time.time()
        self._calls.append((now, 1.0))
        self._evict(now)

        if self._state == State.CLOSED:
            await self._check_primary_trigger()
        elif self._state == State.HALF_OPEN and self._probe_in_flight:
            self._probe_in_flight = False
            await self._transition(State.OPEN)

    async def record_timeout(self) -> None:
        """Record a timeout event.

        Counts as a weighted failure (weight=0.5) in the primary window and
        as a full event in the secondary timeout window. If the secondary
        window accumulates >= timeout_max timeouts, the breaker opens.
        """
        now = time.time()

        # Timeout counts as partial failure with configured weight
        self._calls.append((now, self._timeout_weight))
        self._evict(now)

        # Secondary timeout window
        self._timeouts.append(now)
        # Evict old timeout entries
        cutoff = now - self._timeout_window
        while self._timeouts and self._timeouts[0] < cutoff:
            self._timeouts.popleft()

        if self._state == State.CLOSED:
            # Check secondary trigger first
            if len(self._timeouts) > self._timeout_max:
                await self._transition(State.OPEN, secondary=True)
                return
            await self._check_primary_trigger()
        elif self._state == State.HALF_OPEN and self._probe_in_flight:
            self._probe_in_flight = False
            await self._transition(State.OPEN)

    # ------------------------------------------------------------------
    # State query API
    # ------------------------------------------------------------------

    def is_open(self) -> bool:
        """Return True when requests should be blocked.

        As a side-effect, lazily transitions OPEN -> HALF_OPEN when the
        open_duration has elapsed.
        """
        if self._state == State.OPEN:
            if self._open_at is not None and time.time() - self._open_at >= self._open_duration:
                # Lazy transition: schedule via sync path (no await available here).
                # Perform state mutation directly; the event emit is best-effort.
                self._state = State.HALF_OPEN
                self._probe_in_flight = False
                return False  # Now HALF_OPEN — allow a probe
            return True
        return False

    def allow_probe(self) -> bool:
        """Return True once when in HALF_OPEN and no probe is in flight."""
        if self._state == State.HALF_OPEN and not self._probe_in_flight:
            self._probe_in_flight = True
            return True
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evict(self, now: float) -> None:
        """Remove entries outside the primary rolling window."""
        cutoff = now - self._window_seconds
        while self._calls and self._calls[0][0] < cutoff:
            self._calls.popleft()

    async def _check_primary_trigger(self) -> None:
        if len(self._calls) < self._min_samples:
            return
        failure_weight = sum(w for _, w in self._calls)
        rate = failure_weight / len(self._calls)
        if rate >= self._failure_threshold:
            await self._transition(State.OPEN)

    async def _transition(self, new_state: State, secondary: bool = False) -> None:
        self._state = new_state

        if new_state == State.OPEN:
            self._open_at = time.time()
            self._probe_in_flight = False
            event_type = "timeout_secondary" if secondary else "circuit_open"
            await self._emit_event(
                run_task_id="",
                event_type=event_type,
                message=f"Circuit breaker -> OPEN (secondary={secondary})",
                payload={"state": "open", "secondary": secondary},
            )
        elif new_state == State.HALF_OPEN:
            await self._emit_event(
                run_task_id="",
                event_type="circuit_half_open",
                message="Circuit breaker -> HALF_OPEN",
                payload={"state": "half_open"},
            )
        elif new_state == State.CLOSED:
            self._open_at = None
            self._calls.clear()
            self._timeouts.clear()
            await self._emit_event(
                run_task_id="",
                event_type="circuit_closed",
                message="Circuit breaker -> CLOSED",
                payload={"state": "closed"},
            )
