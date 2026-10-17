"""统计结果封装 + 60 秒内存缓存。"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import aggregations
from app.core.database import get_session_factory
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

_TTL = 60.0
_cache: dict[str, tuple[float, Any]] = {}
_lock = asyncio.Lock()


async def _cached(key: str, producer: Callable[[AsyncSession], Awaitable[Any]]) -> Any:
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    async with _lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < _TTL:
            return hit[1]
        async with get_session_factory()() as session:
            value = await producer(session)
        _cache[key] = (time.monotonic(), value)
        return value


def invalidate() -> None:
    _cache.clear()


async def overview() -> dict:
    return await _cached("overview", aggregations.overview)


async def type_distribution(metric: str = "count") -> list[dict]:
    return await _cached(
        f"type-dist:{metric}",
        lambda s: aggregations.type_distribution(s, metric),
    )


async def type_matrix() -> list[dict]:
    return await _cached("type-matrix", aggregations.type_matrix)


async def ability_top(limit: int = 20) -> list[dict]:
    return await _cached(f"ability-top:{limit}", lambda s: aggregations.ability_top(s, limit))


async def height_weight(mode: str = "scatter", type_name: str | None = None) -> list[dict]:
    return await _cached(
        f"hw:{mode}:{type_name}",
        lambda s: aggregations.height_weight(s, mode, type_name),
    )


async def ranking(metric: str = "stat_total", limit: int = 20, order: str = "desc") -> list[dict]:
    return await _cached(
        f"ranking:{metric}:{limit}:{order}",
        lambda s: aggregations.ranking(s, metric, limit, order),
    )


async def radar(ids: list[int] | None = None, q: str | None = None, limit: int = 3) -> list[dict]:
    key = f"radar:{ids}:{q}:{limit}"
    return await _cached(key, lambda s: aggregations.radar(s, ids, q, limit))


async def crawl_trend(days: int = 7) -> list[dict]:
    return await _cached(f"trend:{days}", lambda s: aggregations.crawl_trend(s, days))


def envelope(items: Any, total: int = 0) -> dict:
    return {"updated_at": utcnow().isoformat(), "total": total, "items": items}
