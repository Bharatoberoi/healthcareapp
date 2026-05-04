"""
In-memory token-bucket rate limiter (per IP).

For single-process deployments this works out of the box.
In multi-replica production, swap with a Redis-backed implementation
by subclassing and overriding _get_bucket / _consume.
"""

import time
import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class TokenBucket:
    __slots__ = ("capacity", "tokens", "refill_rate", "last_refill")

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiter:
    """Per-IP in-memory rate limiter."""

    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.refill_rate = requests_per_minute / 60.0
        self._buckets: Dict[str, TokenBucket] = {}
        self._last_cleanup = time.monotonic()

    @property
    def enabled(self) -> bool:
        return self.rpm > 0

    def allow(self, key: str) -> Tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        if not self.enabled:
            return True, 0

        self._maybe_cleanup()

        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = TokenBucket(self.rpm, self.refill_rate)
            self._buckets[key] = bucket

        if bucket.consume():
            return True, 0

        wait = max(1, int((1.0 - bucket.tokens) / bucket.refill_rate))
        return False, wait

    def _maybe_cleanup(self):
        now = time.monotonic()
        if now - self._last_cleanup < 60:
            return
        self._last_cleanup = now
        cutoff = now - 120
        self._buckets = {
            k: v for k, v in self._buckets.items() if v.last_refill > cutoff
        }
