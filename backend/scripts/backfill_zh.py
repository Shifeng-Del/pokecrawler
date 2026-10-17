"""把简体中文译名回填到已有数据。

用法：
    python scripts/backfill_zh.py            # 实际回填
    python scripts/backfill_zh.py --dry-run  # 只看覆盖率，不写库

说明：
- 中文译名是**物种级**的，由 species_name 查表；形态（如 deoxys-attack）
  与基础共用同一个译名，这是符合官方命名习惯的
- 新抓取的数据由 adapter 直接写入 name_zh，无需再跑本脚本
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.loop import setup_event_loop_policy  # noqa: E402

setup_event_loop_policy()

from app.core.database import dispose_engine, get_session_factory, init_db  # noqa: E402
from app.utils.zh_names import load_zh_names  # noqa: E402

from config.logging_config import setup_logging  # noqa: E402

setup_logging("INFO")
logger = logging.getLogger("backfill_zh")


async def main(dry_run: bool) -> int:
    from sqlalchemy import bindparam, select, update

    from app.core.models import Pokemon

    await init_db()  # 顺带补上 name_zh 列

    mapping = load_zh_names()
    if not mapping:
        logger.error("未找到中文映射数据，请先运行 scripts/fetch_zh_names.py")
        return 1

    async with get_session_factory()() as session:
        rows = (
            await session.execute(select(Pokemon.id, Pokemon.name, Pokemon.species_name))
        ).all()

    updates: list[dict] = []
    missing: list[str] = []
    for pid, name, species in rows:
        zh = mapping.get((species or name or "").lower().strip())
        if zh:
            updates.append({"_id": pid, "_zh": zh})
        else:
            missing.append(f"#{pid} {name} (species={species})")

    total = len(rows)
    logger.info("库内记录 %d 条，可回填 %d 条，未命中 %d 条", total, len(updates), len(missing))
    if missing:
        logger.warning("未命中样例：%s", "；".join(missing[:10]))

    if dry_run:
        logger.info("--dry-run：未写入数据库")
    elif updates:
        stmt = (
            update(Pokemon.__table__)
            .where(Pokemon.__table__.c.id == bindparam("_id"))
            .values(name_zh=bindparam("_zh"))
            .execution_options(synchronize_session=None)
        )
        async with get_session_factory()() as session:
            for i in range(0, len(updates), 500):
                await session.execute(stmt, updates[i : i + 500])
            await session.commit()
        logger.info("已回填 %d 条 name_zh", len(updates))

    rate = len(updates) / total * 100 if total else 0
    logger.info("覆盖率：%.2f%%", rate)
    await dispose_engine()
    return 0 if not missing else 2


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.exit(asyncio.run(main(args.dry_run)))
