"""统计聚合接口：图表数据源。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.constants import METRIC_OPTIONS
from app.services import stats_service

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
async def overview():
    return await stats_service.overview()


@router.get("/type-distribution")
async def type_distribution(metric: str = Query("count", pattern="^(count|avg_total)$")):
    items = await stats_service.type_distribution(metric)
    return stats_service.envelope(items, total=len(items))


@router.get("/type-matrix")
async def type_matrix():
    items = await stats_service.type_matrix()
    return stats_service.envelope(items, total=len(items))


@router.get("/ability-top")
async def ability_top(limit: int = Query(20, ge=1, le=100)):
    items = await stats_service.ability_top(limit)
    return stats_service.envelope(items, total=len(items))


@router.get("/height-weight")
async def height_weight(
    mode: str = Query("scatter", pattern="^(scatter|hist)$"),
    type: str | None = Query(None),
):
    items = await stats_service.height_weight(mode, type)
    return stats_service.envelope(items, total=len(items))


@router.get("/ranking")
async def ranking(
    metric: str = Query("stat_total"),
    limit: int = Query(20, ge=1, le=100),
    order: str = Query("desc", pattern="^(asc|desc)$"),
):
    if metric not in METRIC_OPTIONS:
        metric = "stat_total"
    items = await stats_service.ranking(metric, limit, order)
    return {"metric": metric, "metric_label": METRIC_OPTIONS[metric], "items": items}


@router.get("/radar")
async def radar(
    ids: str | None = Query(None, description="逗号分隔的宝可梦 id"),
    q: str | None = Query(None),
    limit: int = Query(3, ge=1, le=10),
):
    id_list = None
    if ids:
        try:
            id_list = [int(x) for x in ids.split(",") if x.strip()]
        except ValueError:
            id_list = None
    items = await stats_service.radar(id_list, q, limit)
    return stats_service.envelope(items, total=len(items))


@router.get("/type-radar")
async def type_radar():
    """各属性的六维均值（等价于 type-distribution 的雷达视角）。"""
    items = await stats_service.type_distribution("count")
    return stats_service.envelope(items, total=len(items))


@router.get("/crawl-trend")
async def crawl_trend(days: int = Query(7, ge=1, le=60)):
    items = await stats_service.crawl_trend(days)
    return stats_service.envelope(items, total=len(items))


@router.get("/metrics")
async def metrics():
    return {"metrics": [{"name": k, "label": v} for k, v in METRIC_OPTIONS.items()]}
