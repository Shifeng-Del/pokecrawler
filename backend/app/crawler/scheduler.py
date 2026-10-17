"""定时调度：APScheduler（与 uvicorn 共享同一事件循环）。"""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services import crawl_service
from config.settings import get_settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")

JOBS: dict[str, dict[str, Any]] = {
    "daily-incremental": {
        "name": "每日增量爬取",
        "mode": "incremental",
        "description": "每天定时增量更新宝可梦数据",
    },
    "weekly-full": {
        "name": "每周全量爬取",
        "mode": "full",
        "description": "每周定时全量刷新",
    },
}


async def _run(mode: str) -> None:
    logger.info("定时任务触发：%s", mode)
    try:
        await crawl_service.trigger(mode=mode, trigger_source="scheduler")
    except crawl_service.JobConflict as exc:
        logger.warning("定时任务跳过（%s）", exc)


def setup_scheduler() -> None:
    settings = get_settings()
    if not settings.scheduler_enabled:
        logger.info("定时调度已关闭")
        return
    if scheduler.running:
        return

    scheduler.add_job(
        _run,
        CronTrigger(hour=settings.scheduler_incremental_hour, minute=0),
        args=["incremental"],
        id="daily-incremental",
        name="每日增量爬取",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run,
        CronTrigger(
            day_of_week=settings.scheduler_full_day_of_week,
            hour=settings.scheduler_full_hour,
            minute=0,
        ),
        args=["full"],
        id="weekly-full",
        name="每周全量爬取",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("定时调度已启动")


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("定时调度已停止")


def describe() -> list[dict[str, Any]]:
    out = []
    for job in scheduler.get_jobs():
        out.append(
            {
                "id": job.id,
                "name": job.name,
                "description": JOBS.get(job.id, {}).get("description", ""),
                "mode": JOBS.get(job.id, {}).get("mode", ""),
                "cron": str(job.trigger),
                "next_run_at": job.next_run_time.isoformat() if job.next_run_time else None,
                "enabled": True,
            }
        )
    return out


async def run_now(job_id: str) -> int:
    mode = JOBS.get(job_id, {}).get("mode", "incremental")
    return await crawl_service.trigger(mode=mode, trigger_source="scheduler")


def pause(job_id: str) -> bool:
    job = scheduler.get_job(job_id)
    if job:
        scheduler.pause_job(job_id)
        return True
    return False


def resume(job_id: str) -> bool:
    job = scheduler.get_job(job_id)
    if job:
        scheduler.resume_job(job_id)
        return True
    return False
