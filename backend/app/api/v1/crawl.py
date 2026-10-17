"""爬取任务接口：触发、查询、取消、定时调度、robots 状态。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from app.core.database import get_session_factory
from app.core.repository import list_failed_targets
from app.core.schemas import CrawlTriggerRequest, JobOut
from app.crawler.factory import FetcherFactory
from app.crawler.pipeline import TARGETS
from app.crawler.robots import RobotsPolicy
from app.crawler.scheduler import describe as describe_sched
from app.crawler.scheduler import pause as pause_sched
from app.crawler.scheduler import resume as resume_sched
from app.crawler.scheduler import run_now
from app.services import crawl_service
from config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crawl", tags=["crawl"])


@router.post("/trigger", status_code=202)
async def trigger(payload: CrawlTriggerRequest) -> dict:
    settings = get_settings()
    mode = payload.mode.lower()
    if mode not in {"full", "incremental", "range", "ids", "retry_failed"}:
        raise HTTPException(status_code=422, detail=f"不支持的模式：{mode}")

    target = payload.target.lower()
    if target not in TARGETS:
        raise HTTPException(
            status_code=422,
            detail=f"不支持的抓取目标：{target}，可选 {sorted(TARGETS)}",
        )

    ids = payload.ids
    if mode == "retry_failed":
        # 失败记录按目标前缀过滤（species:/evolution:/move:/ability:/pokemon:）
        prefix = f"{TARGETS[target]['prefix']}:"
        async with get_session_factory()() as session:
            ids = [
                int(t.split(":")[-1])
                for t in await list_failed_targets(session)
                if t and t.startswith(prefix) and t.split(":")[-1].isdigit()
            ]
        if not ids:
            raise HTTPException(status_code=404, detail="没有需要重试的失败记录")
        mode = "ids"

    try:
        job_id = await crawl_service.trigger(
            mode=mode,
            target=target,
            fetcher=payload.fetcher,
            adapter=payload.adapter,
            limit=payload.limit,
            offset=payload.offset,
            ids=ids,
            concurrency=payload.concurrency,
            page_size=payload.page_size,
            dry_run=payload.dry_run,
            trigger_source="api",
        )
    except crawl_service.JobConflict as exc:
        raise HTTPException(status_code=409, detail=f"已有任务 #{exc.job_id} 正在运行") from exc

    return {
        "job_id": job_id,
        "status": "pending",
        "message": f"已创建任务 #{job_id}（{mode} / {target} / {payload.fetcher or settings.crawler_fetcher}）",
    }


@router.get("/jobs")
async def jobs(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    total, rows = await crawl_service.list_jobs(status=status, page=page, page_size=page_size)
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [crawl_service.job_to_dict(j) for j in rows],
    }


@router.get("/jobs/{job_id}", response_model=JobOut)
async def job_detail(job_id: int):
    job = await crawl_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"任务不存在：{job_id}")
    return JobOut(**crawl_service.job_to_dict(job))


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: int) -> dict:
    status = await crawl_service.cancel(job_id)
    if status == "not_found":
        raise HTTPException(status_code=404, detail=f"任务不存在：{job_id}")
    return {"job_id": job_id, "status": status}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: int) -> dict:
    ok = await crawl_service.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=409, detail="任务正在运行或不存在")
    return {"deleted": True}


@router.get("/scheduler")
async def scheduler_state() -> dict:
    return {"items": describe_sched(), "active_job": crawl_service.active_job_id()}


@router.post("/scheduler/{job_id}/run-now")
async def scheduler_run_now(job_id: str) -> dict:
    try:
        new_job_id = await run_now(job_id)
    except crawl_service.JobConflict as exc:
        raise HTTPException(status_code=409, detail=f"已有任务 #{exc.job_id} 正在运行") from exc
    return {"job_id": new_job_id, "message": f"已立即执行 {job_id}"}


@router.post("/scheduler/{job_id}/pause")
async def scheduler_pause(job_id: str) -> dict:
    return {"paused": pause_sched(job_id)}


@router.post("/scheduler/{job_id}/resume")
async def scheduler_resume(job_id: str) -> dict:
    return {"resumed": resume_sched(job_id)}


@router.get("/robots")
async def robots_state(url: str = Query("https://pokeapi.co/api/v2/pokemon/1/")) -> dict:
    settings = get_settings()
    policy = RobotsPolicy(settings)
    return await policy.describe(url)


@router.get("/fetchers")
async def fetchers() -> dict:
    return {
        "available": FetcherFactory.available(),
        "default": get_settings().crawler_fetcher,
    }
