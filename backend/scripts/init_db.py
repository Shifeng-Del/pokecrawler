"""初始化数据库（幂等）。"""

from __future__ import annotations

import asyncio

from _bootstrap import BACKEND_DIR  # noqa: F401  (触发 sys.path 引导)

from app.core.database import dispose_engine, init_db
from app.core.models import Base, Pokemon
from config.settings import get_settings


async def main() -> None:
    settings = get_settings()
    await init_db()
    print(f"数据库已就绪：{settings.database_url}")
    print(f"数据表：{', '.join(sorted(Base.metadata.tables))}")
    print(f"字段数（pokemon）：{len(Pokemon.__table__.columns)}")
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
