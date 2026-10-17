"""健康检查。"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.database import check_db
from app.crawler.scheduler import scheduler
from app.services import crawl_service
from config.settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    from pathlib import Path  # noqa: PLC0415

    return {
        "status": "ok",
        "db": await check_db(),
        "version": settings.version,
        "active_job": crawl_service.active_job_id(),
        "scheduler_running": scheduler.running,
        "frontend": Path(settings.frontend_dist).exists(),
    }
