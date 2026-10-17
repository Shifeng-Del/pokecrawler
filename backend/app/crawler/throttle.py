"""限速：令牌桶 + 最小请求间隔。"""

from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """异步令牌桶。

    rate        每秒生成令牌数（平均速率）
    capacity    桶容量（允许的瞬时突发）
    min_interval 两次请求之间的最小间隔（秒）
    """

    def __init__(
        self,
        rate: float,
        capacity: float | None = None,
        min_interval: float = 0.0,
    ) -> None:
        self.rate = max(rate, 0.01)
        self.capacity = capacity if capacity is not None else max(1.0, rate)
        self.min_interval = max(min_interval, 0.0)
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._last_request: float | None = None
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
        self._last = now

    async def acquire(self, n: float = 1.0) -> None:
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= n:
                    self._tokens -= n
                    now = time.monotonic()
                    delay = 0.0
                    if self._last_request is not None:
                        delay = max(
                            0.0, self._last_request + self.min_interval - now
                        )
                    self._last_request = now + delay
                    break
                wait = (n - self._tokens) / self.rate
            await asyncio.sleep(wait)
        if delay:
            await asyncio.sleep(delay)


def build_limiter(
    rate_per_sec: float, min_interval_ms: int, concurrency: int
) -> tuple[TokenBucket, asyncio.Semaphore]:
    return (
        TokenBucket(rate_per_sec, max(1.0, rate_per_sec), min_interval_ms / 1000.0),
        asyncio.Semaphore(concurrency),
    )
