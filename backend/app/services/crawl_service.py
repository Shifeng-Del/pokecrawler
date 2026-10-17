"""爬取任务服务：触发、取消、查询。

要点：
- 用 asyncio.create_task 而非 BackgroundTasks（需要可取消与句柄）
- TASK_REGISTRY 保存强引用，防止 Task 被 GC
- 全局 CRAWL_LOCK：SQLite 单写者，且要遵守限速，同时只允许一个任务
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.database import get_session_factory
from app.core.models import CrawlJob
from app.core.repository import create_job
from app.crawler.pipeline import run_crawl
from app.utils.time import utcnow
from config.settings import get_settings

logger = logging.getLogger(__name__)

CRAWL_LOCK = asyncio.Lock()
TASK_REGISTRY: dict[int, asyncio.Task] = {}


def active_job_id() -> int | None:
    for job_id, task in list(TASK_REGISTRY.items()):
        if not task.done():
            return job_id
    return None


class JobConflict(Exception):
    def __init__(self, job_id: int | None):
        self.job_id = job_id
        super().__init__(f"已有任务 #{job_id} 正在运行")


async def trigger(
    *,
    mode: str = "full",
    target: str = "pokemon",
    fetcher: str | None = None,
    adapter: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    ids: list[int] | None = None,
    concurrency: int | None = None,
    page_size: int | None = None,
    dry_run: bool = False,
    trigger_source: str = "api",
) -> int:
    settings = get_settings()

    if CRAWL_LOCK.locked():
        raise JobConflict(active_job_id())

    # 锁一直持有到任务结束（由 done_callback 释放），覆盖整个执行期
    await CRAWL_LOCK.acquire()
    try:
        params = {
            "mode": mode,
            "target": target,
            "limit": limit,
            "offset": offset,
            "ids": ids,
            "concurrency": concurrency,
            "page_size": page_size,
            "dry_run": dry_run,
        }
        import json  # noqa: PLC0415

        async with get_session_factory()() as session:
            job = await create_job(
                session,
                job_type=mode,
                status="pending",
                trigger_source=trigger_source,
                fetcher=(fetcher or settings.crawler_fetcher).lower(),
                adapter=(adapter or settings.crawler_adapter).lower(),
                params_json=json.dumps(params, ensure_ascii=False),
                concurrency=concurrency or settings.crawler_concurrency,
                message="已加入队列",
            )
            job_id = job.id
    except Exception:
        CRAWL_LOCK.release()
        raise

    task = asyncio.create_task(
        run_crawl(
            job_id,
            mode=mode,
            target=target,
            fetcher_name=fetcher,
            adapter_name=adapter,
            limit=limit,
            offset=offset,
            ids=ids,
            concurrency=concurrency,
            page_size=page_size,
            dry_run=dry_run,
        ),
        name=f"crawl-{job_id}",
    )
    TASK_REGISTRY[job_id] = task
    task.add_done_callback(_make_cleanup(job_id))
    logger.info("已创建爬取任务 #%s（%s / %s / %s）", job_id, mode, target, fetcher)
    return job_id


def _make_cleanup(job_id: int):
    def _cleanup(task: asyncio.Task) -> None:
        TASK_REGISTRY.pop(job_id, None)
        if CRAWL_LOCK.locked():
            CRAWL_LOCK.release()
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error("任务 #%s 未捕获异常：%s", job_id, exc)

    return _cleanup


async def cancel(job_id: int) -> str:
    task = TASK_REGISTRY.get(job_id)
    if task is not None and not task.done():
        async with get_session_factory()() as session:
            job = await session.get(CrawlJob, job_id)
            if job and job.status in ("pending", "running"):
                job.status = "cancelling"
                job.message = "正在取消…"
                await session.commit()
        return "cancelling"

    async with get_session_factory()() as session:
        job = await session.get(CrawlJob, job_id)
        if job is None:
            return "not_found"
        return job.status


async def get_job(job_id: int) -> CrawlJob | None:
    async with get_session_factory()() as session:
        return await session.get(CrawlJob, job_id)


async def list_jobs(*, status: str | None = None, page: int = 1, page_size: int = 20):
    from sqlalchemy import func, select  # noqa: PLC0415

    async with get_session_factory()() as session:
        stmt = select(CrawlJob)
        if status:
            stmt = stmt.where(CrawlJob.status == status)
        total = int(
            (
                await session.execute(
                    select(func.count()).select_from(stmt.subquery())
                )
            ).scalar_one()
        )
        rows = (
            (
                await session.execute(
                    stmt.order_by(CrawlJob.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return total, rows


async def delete_job(job_id: int) -> bool:
    from sqlalchemy import delete  # noqa: PLC0415

    task = TASK_REGISTRY.get(job_id)
    if task is not None and not task.done():
        return False
    async with get_session_factory()() as session:
        result = await session.execute(delete(CrawlJob).where(CrawlJob.id == job_id))
        await session.commit()
        return result.rowcount > 0


def eta_seconds(job: CrawlJob) -> int | None:
    if job.status in ("success", "failed", "cancelled") or not job.progress:
        return None
    if job.progress <= 0:
        return None
    elapsed = job.duration_ms or 0
    started = job.started_at
    if not started:
        return None
    from app.utils.time import parse_iso  # noqa: PLC0415

    start = parse_iso(started)
    if start is None:
        return None
    elapsed_ms = (utcnow() - start).total_seconds() * 1000
    remaining = elapsed_ms / job.progress * (100 - job.progress)
    return int(remaining / 1000)


def job_to_dict(job: CrawlJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "trigger_source": job.trigger_source,
        "fetcher": job.fetcher,
        "adapter": job.adapter,
        "total": job.total,
        "processed": job.processed,
        "inserted": job.inserted,
        "updated": job.updated,
        "skipped": job.skipped,
        "failed": job.failed,
        "progress": job.progress,
        "cursor": job.cursor,
        "request_count": job.request_count,
        "message": job.message,
        "error_detail": job.error_detail,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "duration_ms": job.duration_ms,
        "created_at": job.created_at,
        "eta_seconds": eta_seconds(job),
    }
