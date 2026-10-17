"""爬取流水线：分批并发 → 解析 → 幂等入库 → 进度/断点/取消。"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from sqlalchemy import select

from app.core.database import get_session_factory
from app.core.models import CrawlJob
from app.core.repository import (
    bulk_upsert,
    bulk_upsert_ability_detail,
    bulk_upsert_evolution,
    bulk_upsert_move_detail,
    bulk_upsert_species,
    record_error,
)
from app.crawler.base import CrawlerError
from app.crawler.factory import AdapterFactory, FetcherFactory
from app.crawler.robots import RobotsPolicy
from app.utils.time import utcnow
from config.settings import get_settings

logger = logging.getLogger(__name__)

TERMINAL = {"success", "failed", "cancelled"}

# 抓取目标 -> (适配器, 写入函数, 错误记录前缀)。
# pokemon 保持既有行为（适配器可由参数覆盖，writer 走带 raw/moves 开关的 bulk_upsert）；
# 其余四个 P2 深度目标与适配器一一对应，写入函数签名单一化。
TARGETS: dict[str, dict[str, Any]] = {
    "pokemon": {"adapter": "pokeapi", "writer": None, "prefix": "pokemon"},
    "species": {
        "adapter": "pokeapi-species",
        "writer": bulk_upsert_species,
        "prefix": "species",
    },
    "evolution": {
        "adapter": "pokeapi-evolution",
        "writer": bulk_upsert_evolution,
        "prefix": "evolution",
    },
    "move-detail": {
        "adapter": "pokeapi-move-detail",
        "writer": bulk_upsert_move_detail,
        "prefix": "move",
    },
    "ability-detail": {
        "adapter": "pokeapi-ability-detail",
        "writer": bulk_upsert_ability_detail,
        "prefix": "ability",
    },
}


async def _touch(job_id: int, **fields: Any) -> None:
    """每次更新用独立的短事务，保证进度对外可见。"""
    async with get_session_factory()() as session:
        job = await session.get(CrawlJob, job_id)
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)
        await session.commit()


async def _job_status(job_id: int) -> str | None:
    async with get_session_factory()() as session:
        job = await session.get(CrawlJob, job_id)
        return job.status if job else None


async def _is_cancelling(job_id: int) -> bool:
    return await _job_status(job_id) == "cancelling"


async def _collect_refs(
    adapter,
    *,
    mode: str,
    total: int,
    offset: int,
    limit: int | None,
    ids: list[int] | None,
    page_size: int,
    resume_offset: int,
) -> list[dict]:
    """按模式收集待抓取的条目引用。"""
    if ids:
        return [{"id": i} for i in ids]

    if mode == "range":
        refs = []
        async for ref in adapter.iter_list(
            page_size=page_size, start=offset, max_items=limit
        ):
            refs.append(ref)
            if limit is not None and len(refs) >= limit:
                break
        return refs

    # full / incremental：从 cursor 续跑，limit 是条数上限而非 id 上界
    start = resume_offset or offset
    refs = []
    async for ref in adapter.iter_list(page_size=page_size, start=start, max_items=limit):
        refs.append(ref)
        if limit is not None and len(refs) >= limit:
            break
    return refs


async def run_crawl(
    job_id: int,
    *,
    mode: str = "full",
    target: str = "pokemon",
    fetcher_name: str | None = None,
    adapter_name: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    ids: list[int] | None = None,
    concurrency: int | None = None,
    page_size: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """执行一次爬取任务。返回统计摘要。"""
    settings = get_settings()
    started_at = utcnow()
    t0 = time.perf_counter()

    spec = TARGETS.get(target)
    if spec is None:
        raise ValueError(f"未知抓取目标：{target}，可选 {sorted(TARGETS)}")

    fetcher_name = (fetcher_name or settings.crawler_fetcher).lower()
    if target == "pokemon":
        adapter_name = (adapter_name or settings.crawler_adapter).lower()
    else:
        # 深度目标与适配器一一对应：显式传入别的适配器属于配置错误，直接报错而不是静默忽略
        if adapter_name and adapter_name.lower() != spec["adapter"]:
            raise ValueError(
                f"目标 {target} 需要适配器 {spec['adapter']}，收到 {adapter_name}"
            )
        adapter_name = spec["adapter"]
    page_size = page_size or settings.crawler_page_size

    summary: dict[str, Any] = {
        "job_id": job_id,
        "mode": mode,
        "target": target,
        "fetcher": fetcher_name,
        "adapter": adapter_name,
        "total": 0,
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "dry_run": dry_run,
        "samples": [],
    }

    try:
        await _touch(
            job_id,
            status="running",
            started_at=started_at.isoformat(),
            fetcher=fetcher_name,
            adapter=adapter_name,
            message="正在初始化抓取器…",
        )

        robots = RobotsPolicy(settings)
        fetcher = FetcherFactory.create(
            fetcher_name, settings, concurrency=concurrency, robots=robots
        )
        adapter = AdapterFactory.create(adapter_name, fetcher, settings)

        async with fetcher:
            total = await adapter.discover_total()
            resume_offset = 0
            if mode in ("full", "incremental"):
                async with get_session_factory()() as session:
                    job = await session.get(CrawlJob, job_id)
                    if job and job.cursor and not ids:
                        try:
                            cursor_offset = int(job.cursor)
                            if cursor_offset > 0:
                                resume_offset = cursor_offset
                                logger.info("从断点 offset=%s 续跑", resume_offset)
                        except ValueError:
                            pass

            refs = await _collect_refs(
                adapter,
                mode=mode,
                total=total,
                offset=offset,
                limit=limit,
                ids=ids,
                page_size=page_size,
                resume_offset=resume_offset,
            )
            planned_total = len(refs)
            await _touch(
                job_id,
                total=planned_total,
                cursor=str(offset if ids else (resume_offset or offset)),
                concurrency=concurrency or settings.crawler_concurrency,
                message=f"待抓取 {planned_total} 条",
            )
            summary["total"] = planned_total

            batch_size = max(page_size, 1)
            processed = 0
            failed = 0
            agg = {"inserted": 0, "updated": 0, "skipped": 0}

            for batch_start in range(0, planned_total, batch_size):
                if await _is_cancelling(job_id):
                    await _touch(
                        job_id, status="cancelled", message="已被用户取消",
                        finished_at=utcnow().isoformat(),
                        duration_ms=int((time.perf_counter() - t0) * 1000),
                    )
                    summary["status"] = "cancelled"
                    return summary

                batch = refs[batch_start : batch_start + batch_size]
                results = await asyncio.gather(
                    *(adapter.fetch_detail(ref) for ref in batch),
                    return_exceptions=True,
                )

                ok_records: list[dict] = []
                for ref, result in zip(batch, results, strict=False):
                    if isinstance(result, BaseException):
                        failed += 1
                        reason = (
                            result.message
                            if isinstance(result, CrawlerError)
                            else repr(result)
                        )
                        logger.warning("抓取失败 id=%s：%s", ref.get("id"), reason)
                        async with get_session_factory()() as session:
                            await record_error(
                                session,
                                job_id=job_id,
                                target=f"{spec['prefix']}:{ref.get('id')}",
                                url=ref.get("url"),
                                error=str(reason),
                            )
                        continue
                    ok_records.append(result)

                if dry_run:
                    summary["samples"].extend(ok_records[:3])
                    if len(summary["samples"]) >= 3:
                        pass
                elif target == "pokemon":
                    # 既有路径：raw_json / moves 子表开关由 settings 决定
                    async with get_session_factory()() as session:
                        counter = await bulk_upsert(
                            session,
                            ok_records,
                            job_id=job_id,
                            store_raw=settings.store_raw_json,
                            store_moves=settings.store_moves,
                        )
                    for key in agg:
                        agg[key] += counter.get(key, 0)
                else:
                    async with get_session_factory()() as session:
                        counter = await spec["writer"](
                            session, ok_records, job_id=job_id
                        )
                    for key in agg:
                        agg[key] += counter.get(key, 0)

                processed += len(batch)
                progress = round(processed / planned_total * 100, 2) if planned_total else 100.0
                await _touch(
                    job_id,
                    processed=processed,
                    progress=progress,
                    inserted=agg["inserted"],
                    updated=agg["updated"],
                    skipped=agg["skipped"],
                    failed=failed,
                    request_count=fetcher.stats["requests"],
                    cursor=str(
                        processed + (offset if ids else (resume_offset or offset))
                    ),
                    message=f"已完成 {processed}/{planned_total}",
                )

            summary.update(
                {
                    "processed": processed,
                    "inserted": agg["inserted"],
                    "updated": agg["updated"],
                    "skipped": agg["skipped"],
                    "failed": failed,
                    "request_count": fetcher.stats["requests"],
                }
            )
            status = "success" if failed == 0 or processed > failed else "failed"
            await _touch(
                job_id,
                status=status,
                progress=100.0,
                finished_at=utcnow().isoformat(),
                duration_ms=int((time.perf_counter() - t0) * 1000),
                message=(
                    f"完成：新增 {agg['inserted']}，更新 {agg['updated']}，"
                    f"未变化 {agg['skipped']}，失败 {failed}"
                ),
            )
            summary["status"] = status
            return summary

    except asyncio.CancelledError:
        await _touch(
            job_id,
            status="cancelled",
            finished_at=utcnow().isoformat(),
            message="任务被取消",
        )
        summary["status"] = "cancelled"
        return summary
    except Exception as exc:
        logger.exception("爬取任务 #%s 异常终止", job_id)
        await _touch(
            job_id,
            status="failed",
            finished_at=utcnow().isoformat(),
            duration_ms=int((time.perf_counter() - t0) * 1000),
            message=f"任务失败：{exc}",
            error_detail=str(exc)[:4000],
        )
        summary["status"] = "failed"
        summary["error"] = str(exc)
        return summary


async def mark_stale_jobs() -> int:
    """进程重启时把残留的 running 任务标记为失败。"""
    async with get_session_factory()() as session:
        rows = (
            (await session.execute(select(CrawlJob).where(CrawlJob.status == "running")))
            .scalars()
            .all()
        )
        for job in rows:
            job.status = "failed"
            job.message = "进程重启中断"
            job.finished_at = utcnow().isoformat()
        if rows:
            await session.commit()
        return len(rows)
