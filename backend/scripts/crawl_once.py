"""命令行一次性抓取，便于调试与全量入库。

示例：
    python scripts/crawl_once.py --limit 5 --dry-run
    python scripts/crawl_once.py --mode range --limit 100
    python scripts/crawl_once.py --fetcher playwright --limit 5
    python scripts/crawl_once.py --mode full
    # P2 深度目标（与 pokemon 同源不同端点）：
    python scripts/crawl_once.py --target species --limit 20 --dry-run
    python scripts/crawl_once.py --target species --mode full --limit 100000
    python scripts/crawl_once.py --target evolution --mode full --limit 100000
    python scripts/crawl_once.py --target move-detail --mode full --limit 100000
    python scripts/crawl_once.py --target ability-detail --mode full --limit 100000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from _bootstrap import BACKEND_DIR  # noqa: F401

from app.core.database import dispose_engine, init_db
from app.core.repository import create_job
from app.crawler.pipeline import TARGETS, run_crawl
from app.crawler.scheduler import scheduler  # noqa: F401
from app.utils.time import utcnow
from config.logging_config import setup_logging
from config.settings import get_settings


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="宝可梦数据抓取")
    p.add_argument("--mode", default="range", choices=["full", "incremental", "range", "ids"])
    p.add_argument(
        "--target",
        default="pokemon",
        choices=sorted(TARGETS),
        help="抓取目标：pokemon 主表 / species 物种档案 / evolution 进化链 / move-detail 招式明细 / ability-detail 特性明细",
    )
    p.add_argument("--fetcher", default=None, choices=["httpx", "playwright"])
    p.add_argument("--adapter", default=None, choices=["pokeapi", "generic_html"])
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--ids", default="", help="逗号分隔的 id 列表")
    p.add_argument("--concurrency", type=int, default=None)
    p.add_argument("--page-size", type=int, default=None)
    p.add_argument("--dry-run", action="store_true", help="只抓取不入库")
    p.add_argument("--resume", type=int, default=None, help="从某个任务的断点续跑")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    setup_logging("DEBUG" if args.verbose else "INFO")
    settings = get_settings()
    await init_db()

    ids = [int(x) for x in args.ids.split(",") if x.strip()] or None
    cursor = None
    if args.resume:
        from app.core.database import get_session_factory  # noqa: PLC0415
        from app.core.models import CrawlJob  # noqa: PLC0415

        async with get_session_factory()() as session:
            job = await session.get(CrawlJob, args.resume)
            if job:
                cursor = job.cursor
                print(f"从任务 #{args.resume} 的断点 {cursor} 续跑")

    from app.core.database import get_session_factory  # noqa: PLC0415

    # 深度目标（species/evolution/move-detail/ability-detail）的适配器由 target 决定，
    # 显式传 --adapter 会触发 pipeline 的严格校验，这里直接忽略并登记实际适配器
    effective_adapter = (
        args.adapter
        if args.target == "pokemon"
        else TARGETS[args.target]["adapter"]
    )

    async with get_session_factory()() as session:
        job = await create_job(
            session,
            job_type=args.mode,
            status="pending",
            trigger_source="cli",
            fetcher=(args.fetcher or settings.crawler_fetcher),
            adapter=effective_adapter,
            params_json=json.dumps(vars(args), ensure_ascii=False, default=str),
            cursor=cursor,
        )
        job_id = job.id

    summary = await run_crawl(
        job_id,
        mode=args.mode,
        target=args.target,
        fetcher_name=args.fetcher,
        adapter_name=effective_adapter,
        limit=args.limit,
        offset=args.offset,
        ids=ids,
        concurrency=args.concurrency,
        page_size=args.page_size,
        dry_run=args.dry_run,
    )

    print("\n===== 抓取结果 =====")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    if args.dry_run and summary.get("samples"):
        print("\n===== 样本字段 =====")
        for sample in summary["samples"]:
            print(
                json.dumps(
                    {k: v for k, v in sample.items() if not k.startswith("_")},
                    ensure_ascii=False,
                )
            )
    await dispose_engine()
    return 0 if summary.get("status") in ("success", "cancelled") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
