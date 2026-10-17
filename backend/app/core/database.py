"""异步数据库引擎与会话。"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import get_settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _ensure_sqlite_dir(url: str) -> None:
    if not url.startswith("sqlite"):
        return
    path = url.split("///", 1)[-1]
    if path and path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        s = get_settings()
        _ensure_sqlite_dir(s.database_url)
        _engine = create_async_engine(
            s.database_url, echo=s.db_echo, future=True, pool_pre_ping=True
        )

        if s.database_url.startswith("sqlite"):

            @event.listens_for(_engine.sync_engine, "connect")
            def _sqlite_pragmas(dbapi_conn, _record):  # type: ignore[no-untyped-def]
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.execute("PRAGMA busy_timeout=5000")
                cur.execute("PRAGMA foreign_keys=ON")
                cur.close()

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False, autoflush=False
        )
    return _session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：每个请求一个会话。"""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """建表 + 轻量增量迁移（幂等）。

    SQLAlchemy 的 create_all 只负责"没有的表"，已存在的表加了新列不会同步，
    这里补一段 ALTER TABLE ADD COLUMN，保证老库平滑升级而不丢数据。
    """
    from sqlalchemy import text

    from app.core.models import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _add_missing_columns(conn, Base.metadata)


# 表 -> (列名, DDL 类型)。新增列时在此登记一次即可。
_MIGRATIONS: dict[str, list[tuple[str, str]]] = {
    "pokemon": [("name_zh", "VARCHAR(64)")],
}


async def _add_missing_columns(conn, metadata) -> None:
    for table_name, columns in _MIGRATIONS.items():
        if table_name not in metadata.tables:
            continue
        rows = (await conn.execute(text(f"PRAGMA table_info({table_name})"))).all()
        existing = {r[1] for r in rows}
        for col, ddl in columns:
            if col in existing:
                continue
            await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} {ddl}"))
            logger.info("已为表 %s 补充列 %s", table_name, col)


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def check_db() -> bool:
    try:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
