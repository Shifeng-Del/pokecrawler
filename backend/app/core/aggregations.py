"""统计聚合：全部走 SQL GROUP BY，不把全表拉进内存。"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import (
    CrawlJob,
    Pokemon,
    PokemonAbility,
    PokemonType,
)
from app.utils.time import utcnow
from app.utils.zh_glossary import glossary_zh

logger = logging.getLogger(__name__)

STAT_COLUMNS = {
    "hp": Pokemon.stat_hp,
    "attack": Pokemon.stat_attack,
    "defense": Pokemon.stat_defense,
    "special_attack": Pokemon.stat_special_attack,
    "special_defense": Pokemon.stat_special_defense,
    "speed": Pokemon.stat_speed,
    "stat_total": Pokemon.stat_total,
    "height": Pokemon.height,
    "weight": Pokemon.weight,
    "base_experience": Pokemon.base_experience,
}


async def overview(session: AsyncSession) -> dict[str, Any]:
    total = int((await session.execute(select(func.count(Pokemon.id)))).scalar_one())
    type_count = int(
        (
            await session.execute(
                select(func.count(func.distinct(PokemonType.type_name)))
            )
        ).scalar_one()
    )
    ability_count = int(
        (
            await session.execute(
                select(func.count(func.distinct(PokemonAbility.ability_name)))
            )
        ).scalar_one()
    )
    avg = (
        await session.execute(
            select(
                func.avg(Pokemon.stat_total),
                func.avg(Pokemon.height),
                func.avg(Pokemon.weight),
                func.avg(Pokemon.base_experience),
            )
        )
    ).one()

    last_job = (
        await session.execute(
            select(CrawlJob).order_by(CrawlJob.id.desc()).limit(1)
        )
    ).scalars().first()

    return {
        "total": total,
        "type_count": type_count,
        "ability_count": ability_count,
        "avg_stat_total": round(avg[0] or 0, 1),
        "avg_height": round(avg[1] or 0, 2),
        "avg_weight": round(avg[2] or 0, 2),
        "avg_base_experience": round(avg[3] or 0, 1),
        "last_crawl_at": last_job.finished_at if last_job else None,
        "last_job_status": last_job.status if last_job else None,
        "last_job_id": last_job.id if last_job else None,
        "updated_at": utcnow().isoformat(),
    }


async def type_distribution(session: AsyncSession, metric: str = "count") -> list[dict]:
    value = (
        func.avg(Pokemon.stat_total)
        if metric == "avg_total"
        else func.count(Pokemon.id)
    )
    stmt = (
        select(
            PokemonType.type_name.label("type"),
            func.count(Pokemon.id).label("count"),
            func.avg(Pokemon.stat_total).label("avg_stat_total"),
            func.avg(Pokemon.height).label("avg_height"),
            func.avg(Pokemon.weight).label("avg_weight"),
            func.avg(Pokemon.stat_hp).label("hp"),
            func.avg(Pokemon.stat_attack).label("attack"),
            func.avg(Pokemon.stat_defense).label("defense"),
            func.avg(Pokemon.stat_special_attack).label("special_attack"),
            func.avg(Pokemon.stat_special_defense).label("special_defense"),
            func.avg(Pokemon.stat_speed).label("speed"),
        )
        .join(Pokemon, Pokemon.id == PokemonType.pokemon_id)
        .group_by(PokemonType.type_name)
        .order_by(value.desc())
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "type": r.type,
            "count": int(r.count),
            "avg_stat_total": round(r.avg_stat_total or 0, 1),
            "avg_height": round(r.avg_height or 0, 2),
            "avg_weight": round(r.avg_weight or 0, 2),
            "hp": round(r.hp or 0, 1),
            "attack": round(r.attack or 0, 1),
            "defense": round(r.defense or 0, 1),
            "special_attack": round(r.special_attack or 0, 1),
            "special_defense": round(r.special_defense or 0, 1),
            "speed": round(r.speed or 0, 1),
        }
        for r in rows
    ]


async def type_matrix(session: AsyncSession) -> list[dict]:
    stmt = (
        select(
            Pokemon.type_primary.label("primary"),
            Pokemon.type_secondary.label("secondary"),
            func.count(Pokemon.id).label("count"),
        )
        .where(Pokemon.type_primary.isnot(None))
        .group_by(Pokemon.type_primary, Pokemon.type_secondary)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "primary": r.primary,
            "secondary": r.secondary or "",
            "count": int(r.count),
        }
        for r in rows
    ]


async def ability_top(session: AsyncSession, limit: int = 20) -> list[dict]:
    stmt = (
        select(
            PokemonAbility.ability_name.label("ability"),
            func.count(PokemonAbility.pokemon_id).label("count"),
        )
        .group_by(PokemonAbility.ability_name)
        .order_by(func.count(PokemonAbility.pokemon_id).desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "ability": r.ability,
            "ability_zh": glossary_zh("abilities", r.ability),
            "count": int(r.count),
        }
        for r in rows
    ]


async def height_weight(
    session: AsyncSession, mode: str = "scatter", type_name: str | None = None
) -> list[dict]:
    if mode == "hist":
        stmt = select(
            func.count(Pokemon.id).label("count"),
            Pokemon.height.label("height"),
        ).group_by(Pokemon.height).order_by(Pokemon.height)
        if type_name:
            stmt = stmt.where(Pokemon.type_primary == type_name)
        rows = (await session.execute(stmt)).all()
        return [
            {"bin": f"{r.height}", "count": int(r.count)} for r in rows if r.height is not None
        ]

    stmt = select(
        Pokemon.id,
        Pokemon.name,
        Pokemon.name_zh,
        Pokemon.height,
        Pokemon.weight,
        Pokemon.type_primary,
        Pokemon.stat_total,
        Pokemon.image_url,
    ).where(Pokemon.height.isnot(None), Pokemon.weight.isnot(None))
    if type_name:
        stmt = stmt.where(Pokemon.type_primary == type_name)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "name_zh": r.name_zh,
            "height": r.height,
            "weight": r.weight,
            "type_primary": r.type_primary,
            "stat_total": r.stat_total,
            "image_url": r.image_url,
        }
        for r in rows
    ]


async def ranking(
    session: AsyncSession, metric: str = "stat_total", limit: int = 20, order: str = "desc"
) -> list[dict]:
    column = STAT_COLUMNS.get(metric, Pokemon.stat_total)
    stmt = select(
        Pokemon.id,
        Pokemon.name,
        Pokemon.name_zh,
        column.label("value"),
        Pokemon.type_primary,
        Pokemon.type_secondary,
        Pokemon.image_url,
        Pokemon.stat_total,
    ).where(column.isnot(None))
    stmt = stmt.order_by(column.desc() if order == "desc" else column.asc()).limit(limit)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "name_zh": r.name_zh,
            "value": r.value,
            "type_primary": r.type_primary,
            "type_secondary": r.type_secondary,
            "image_url": r.image_url,
            "stat_total": r.stat_total,
        }
        for r in rows
    ]


async def radar(session: AsyncSession, ids: list[int] | None = None, q: str | None = None, limit: int = 3) -> list[dict]:
    stmt = select(Pokemon)
    if ids:
        stmt = stmt.where(Pokemon.id.in_(ids))
    elif q:
        stmt = stmt.where(or_(Pokemon.name.like(f"%{q.lower()}%"), Pokemon.name_zh.like(f"%{q}%")))
    stmt = stmt.order_by(Pokemon.id).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "name_zh": p.name_zh,
            "type_primary": p.type_primary,
            "image_url": p.image_url,
            "stats": {
                "hp": p.stat_hp,
                "attack": p.stat_attack,
                "defense": p.stat_defense,
                "special_attack": p.stat_special_attack,
                "special_defense": p.stat_special_defense,
                "speed": p.stat_speed,
            },
            "stat_total": p.stat_total,
        }
        for p in rows
    ]


async def crawl_trend(session: AsyncSession, days: int = 7) -> list[dict]:
    stmt = (
        select(
            func.substr(CrawlJob.finished_at, 1, 10).label("date"),
            func.count(CrawlJob.id).label("total"),
            func.sum(CrawlJob.processed).label("items"),
        )
        .where(CrawlJob.finished_at.isnot(None))
        .group_by("date")
        .order_by("date")
    )
    rows = (await session.execute(stmt)).all()
    return [
        {"date": r.date, "total": int(r.total), "items": int(r.items or 0)}
        for r in rows
    ][-days:]
