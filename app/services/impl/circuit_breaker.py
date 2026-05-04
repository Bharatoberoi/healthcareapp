"""
Circuit breaker for external service calls (LLM APIs, etc.).

States:
  CLOSED  – calls flow normally; failures are counted.
  OPEN    – calls fail fast; after *recovery_timeout* move to HALF_OPEN.
  HALF_OPEN – one probe call allowed; success → CLOSED, failure → OPEN.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open and rejecting calls."""


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        window: float = 60.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.window = window

        self._state = CircuitState.CLOSED
        self._failures: list[float] = []
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
        return self._state

    async def __aenter__(self):
        async with self._lock:
            current = self.state
            if current == CircuitState.OPEN:
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is OPEN — failing fast"
                )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:
            if exc_type is not None:
                self._record_failure()
                return False

            if self._state == CircuitState.HALF_OPEN:
                logger.info("[CircuitBreaker:%s] Probe succeeded → CLOSED", self.name)
                self._state = CircuitState.CLOSED
                self._failures.clear()
        return False

    def _record_failure(self):
        now = time.monotonic()
        self._failures = [t for t in self._failures if now - t < self.window]
        self._failures.append(now)
        self._last_failure_time = now

        if len(self._failures) >= self.failure_threshold:
            logger.warning(
                "[CircuitBreaker:%s] %d failures in %.0fs → OPEN",
                self.name, len(self._failures), self.window,
            )
            self._state = CircuitState.OPEN

    def reset(self):
        self._state = CircuitState.CLOSED
        self._failures.clear()
