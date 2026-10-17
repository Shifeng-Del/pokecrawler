import asyncio
import time

from app.crawler.throttle import TokenBucket, build_limiter


async def test_token_bucket_limits_rate():
    bucket = TokenBucket(rate=20.0, capacity=1.0, min_interval=0.0)
    start = time.perf_counter()
    for _ in range(4):
        await bucket.acquire()
    elapsed = time.perf_counter() - start
    # 首个令牌立即可用，其余 3 个需要 3/20 = 0.15s
    assert elapsed >= 0.12, f"限速未生效：{elapsed:.3f}s"


async def test_min_interval_enforced():
    bucket = TokenBucket(rate=100.0, capacity=10.0, min_interval=0.05)
    start = time.perf_counter()
    await bucket.acquire()
    await bucket.acquire()
    elapsed = time.perf_counter() - start
    assert elapsed >= 0.045, f"最小间隔未生效：{elapsed:.3f}s"


def test_build_limiter():
    limiter, sem = build_limiter(5.0, 150, 6)
    assert limiter.rate == 5.0
    assert abs(limiter.min_interval - 0.15) < 1e-9
    assert sem._value == 6
