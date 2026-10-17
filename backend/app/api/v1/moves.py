"""招式图鉴 / 特性明细接口（P2 深度数据的读取侧）。

与 pokemon 路由的分工：pokemon 回答「这只宝可梦会什么」，
本路由回答「这个招式/特性本身是什么」——图鉴页与详情悬停都走这里。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.models import AbilityDetail, MoveDetail, PokemonAbility, PokemonMove
from app.core.schemas import (
    AbilityDetailOut,
    AbilityListItemOut,
    MoveDetailOut,
    MoveListItemOut,
    PagedAbilities,
    PagedMoves,
)
from app.utils.zh_glossary import glossary_zh, load_glossary
from app.utils.zh_texts import ability_text_zh, move_text_zh

router = APIRouter(prefix="/moves", tags=["moves"])
ability_router = APIRouter(prefix="/abilities", tags=["abilities"])

# 排序白名单：威力/命中/PP/优先级/名称，防排序字段注入
MOVE_SORTABLE = {
    "name": MoveDetail.move_name,
    "power": MoveDetail.power,
    "accuracy": MoveDetail.accuracy,
    "pp": MoveDetail.pp,
    "priority": MoveDetail.priority,
}

# names 批量模式上限：抽屉悬停一次拿全（单只宝可梦招式数峰值 375，见 data 实测）
BATCH_MAX = 400


def _move_item(m: MoveDetail) -> MoveListItemOut:
    return MoveListItemOut(
        name=m.move_name,
        name_zh=glossary_zh("moves", m.move_name),
        type_name=m.type_name,
        damage_class=m.damage_class,
        power=m.power,
        accuracy=m.accuracy,
        pp=m.pp,
        priority=m.priority,
    )


@router.get("", response_model=PagedMoves)
async def list_moves(
    type_name: str | None = Query(None, description="属性 slug，如 fire"),
    damage_class: str | None = Query(None, description="类别：physical / special / status"),
    generation: str | None = Query(None, description="世代 slug，如 generation-i"),
    q: str | None = Query(None, description="名称模糊搜索（中文或英文）"),
    names: str | None = Query(None, description="批量查询，逗号分隔（不分页，供悬停明细）"),
    sort: str = Query("power", description="排序字段"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> PagedMoves:
    stmt = select(MoveDetail)
    if type_name:
        stmt = stmt.where(MoveDetail.type_name == type_name.lower())
    if damage_class:
        stmt = stmt.where(MoveDetail.damage_class == damage_class.lower())
    if generation:
        stmt = stmt.where(MoveDetail.generation == generation.lower())

    if names:
        # 批量模式：命中集合直接查，不分页
        wanted = [n.strip().lower() for n in names.split(",") if n.strip()][:BATCH_MAX]
        if not wanted:
            return PagedMoves(total=0, page=1, page_size=0, items=[])
        stmt = stmt.where(MoveDetail.move_name.in_(wanted))
        rows = (await session.execute(stmt)).scalars().all()
        items = [_move_item(m) for m in rows]
        return PagedMoves(total=len(items), page=1, page_size=len(items), items=items)

    if q:
        kw = q.lower()
        # 英文 slug 走 SQL；中文译名在词典里（读取时翻译、不入库），
        # 因此中文搜索先在内存词典里找 slug，再并集查询
        zh_slugs = {
            slug for slug, zh in load_glossary().get("moves", {}).items() if kw in zh.lower()
        }
        all_names = (await session.execute(select(MoveDetail.move_name))).scalars().all()
        hit = {n for n in all_names if kw in n} | {n for n in zh_slugs if n in set(all_names)}
        stmt = stmt.where(MoveDetail.move_name.in_(hit))

    total = int(
        (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )
    column = MOVE_SORTABLE.get(sort, MoveDetail.power)
    stmt = stmt.order_by(column.desc() if order.lower() == "desc" else column.asc())
    rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return PagedMoves(
        total=total,
        page=page,
        page_size=page_size,
        items=[_move_item(m) for m in rows],
    )


@router.get("/{name}", response_model=MoveDetailOut)
async def get_move(name: str, session: AsyncSession = Depends(get_session)) -> MoveDetailOut:
    move = (
        await session.execute(select(MoveDetail).where(MoveDetail.move_name == name.lower()))
    ).scalar_one_or_none()
    if move is None:
        raise HTTPException(status_code=404, detail=f"未找到招式：{name}")
    learners = (
        await session.execute(
            select(func.count(func.distinct(PokemonMove.pokemon_id))).where(
                PokemonMove.move_name == move.move_name
            )
        )
    ).scalar_one()
    return MoveDetailOut(
        **_move_item(move).model_dump(),
        effect_chance=move.effect_chance,
        generation=move.generation,
        effect_en=move.effect_en,
        flavor_en=move.flavor_en,
        effect_zh=move_text_zh(move.move_name)["effect"],
        flavor_zh=move_text_zh(move.move_name)["flavor"],
        learner_count=int(learners or 0),
    )


def _ability_item(a: AbilityDetail, holder_count: int) -> AbilityListItemOut:
    return AbilityListItemOut(
        name=a.ability_name,
        name_zh=glossary_zh("abilities", a.ability_name),
        generation=a.generation,
        effect_en=a.effect_en,
        effect_zh=ability_text_zh(a.ability_name)["effect"],
        holder_count=holder_count,
    )


@ability_router.get("", response_model=PagedAbilities)
async def list_abilities(
    q: str | None = Query(None, description="名称模糊搜索（中文或英文）"),
    names: str | None = Query(None, description="批量查询，逗号分隔（不分页，供悬停明细）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> PagedAbilities:
    stmt = select(AbilityDetail)

    if names:
        wanted = [n.strip().lower() for n in names.split(",") if n.strip()][:BATCH_MAX]
        if not wanted:
            return PagedAbilities(total=0, page=1, page_size=0, items=[])
        stmt = stmt.where(AbilityDetail.ability_name.in_(wanted))
        rows = (await session.execute(stmt)).scalars().all()
        counts = await _holder_counts(session, [a.ability_name for a in rows])
        items = [_ability_item(a, counts.get(a.ability_name, 0)) for a in rows]
        return PagedAbilities(total=len(items), page=1, page_size=len(items), items=items)

    if q:
        kw = q.lower()
        zh_slugs = {
            slug
            for slug, zh in load_glossary().get("abilities", {}).items()
            if kw in zh.lower()
        }
        all_names = (await session.execute(select(AbilityDetail.ability_name))).scalars().all()
        hit = {n for n in all_names if kw in n} | {n for n in zh_slugs if n in set(all_names)}
        stmt = stmt.where(AbilityDetail.ability_name.in_(hit))

    total = int(
        (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )
    stmt = stmt.order_by(AbilityDetail.ability_name)
    rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    counts = await _holder_counts(session, [a.ability_name for a in rows])
    return PagedAbilities(
        total=total,
        page=page,
        page_size=page_size,
        items=[_ability_item(a, counts.get(a.ability_name, 0)) for a in rows],
    )


async def _holder_counts(session: AsyncSession, names: list[str]) -> dict[str, int]:
    """批量统计特性持有者数量（一次 group by，避免逐条查询）。"""
    if not names:
        return {}
    rows = (
        await session.execute(
            select(PokemonAbility.ability_name, func.count(func.distinct(PokemonAbility.pokemon_id)))
            .where(PokemonAbility.ability_name.in_(names))
            .group_by(PokemonAbility.ability_name)
        )
    ).all()
    return {name: int(n) for name, n in rows}


@ability_router.get("/{name}", response_model=AbilityDetailOut)
async def get_ability(name: str, session: AsyncSession = Depends(get_session)) -> AbilityDetailOut:
    ability = (
        await session.execute(
            select(AbilityDetail).where(AbilityDetail.ability_name == name.lower())
        )
    ).scalar_one_or_none()
    if ability is None:
        raise HTTPException(status_code=404, detail=f"未找到特性：{name}")
    holders = (
        await session.execute(
            select(func.count(func.distinct(PokemonAbility.pokemon_id))).where(
                PokemonAbility.ability_name == ability.ability_name
            )
        )
    ).scalar_one()
    return AbilityDetailOut(
        name=ability.ability_name,
        name_zh=glossary_zh("abilities", ability.ability_name),
        generation=ability.generation,
        is_main_series=bool(ability.is_main_series),
        effect_en=ability.effect_en,
        flavor_en=ability.flavor_en,
        effect_zh=ability_text_zh(ability.ability_name)["effect"],
        flavor_zh=ability_text_zh(ability.ability_name)["flavor"],
        holder_count=int(holders or 0),
    )
