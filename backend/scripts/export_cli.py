"""命令行导出：python scripts/export_cli.py --format csv --type grass"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from _bootstrap import BACKEND_DIR  # noqa: F401  (触发 sys.path 引导)

from app.core.database import dispose_engine, init_db
from app.core.repository import build_pokemon_query
from app.services import export_service
from config.logging_config import setup_logging
from config.settings import DATA_DIR as CFG_DATA_DIR


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="导出宝可梦数据")
    p.add_argument("--format", default="csv", choices=["csv", "json"])
    p.add_argument("--q", default=None)
    p.add_argument("--type", default=None, action="append")
    p.add_argument("--min-total", type=int, default=None)
    p.add_argument("--max-total", type=int, default=None)
    p.add_argument("--sort", default="id")
    p.add_argument("--order", default="asc", choices=["asc", "desc"])
    p.add_argument("--out", default=None, help="输出文件名，默认写入 backend/data/exports/")
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    setup_logging("INFO")
    await init_db()

    stmt = build_pokemon_query(
        q=args.q,
        types=args.type,
        min_total=args.min_total,
        max_total=args.max_total,
        sort=args.sort,
        order=args.order,
    )

    out_dir = CFG_DATA_DIR / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = Path(args.out) if args.out else out_dir / export_service.filename(args.format)

    producer = (
        export_service.iter_csv(stmt)
        if args.format == "csv"
        else export_service.iter_json(stmt)
    )
    with target.open("wb") as fh:
        async for chunk in producer:
            fh.write(chunk)

    print(f"已导出：{target}（{target.stat().st_size / 1024:.1f} KB）")
    await dispose_engine()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
