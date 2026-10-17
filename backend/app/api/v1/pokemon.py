"""宝可梦查询接口：列表 / 搜索 / 筛选 / 详情。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import pokemon_filters, stmt_from_filters
from app.core.constants import STAT_INFO, TYPE_INFO
from app.core.database import get_session
from app.core.models import Pokemon
from app.core.repository import build_pokemon_query, list_pokemon
from app.core.schemas import (
    AbilityOut,
    EvolutionConditionOut,
    EvolutionNodeOut,
    EvolutionOut,
    FilterOptionItem,
    FilterOptionsOut,
    MoveOut,
    PagedPokemon,
    PokemonOut,
)
from app.utils.zh_glossary import ability_out, glossary_zh, move_out
from sqlalchemy import func, select

router = APIRouter(prefix="/pokemon", tags=["pokemon"])

# ---------------------------------------------------------------- 轻量索引
# 供前端全局搜索（Ctrl+K）一次性拉取本地过滤：约 1351 条 / 150KB 级，
# 5 分钟内存缓存，避免每次唤起搜索面板都打数据库。
_INDEX_TTL = 300.0
_index_cache: dict = {"ts": 0.0, "items": None}


@router.get("/index")
async def pokemon_index(session: AsyncSession = Depends(get_session)) -> dict:
    import time  # noqa: PLC0415

    now = time.monotonic()
    if _index_cache["items"] is not None and now - _index_cache["ts"] < _INDEX_TTL:
        return {"total": len(_index_cache["items"]), "items": _index_cache["items"], "cached": True}
    rows = (
        await session.execute(
            select(Pokemon.id, Pokemon.name, Pokemon.name_zh, Pokemon.type_primary, Pokemon.stat_total)
            .order_by(Pokemon.id)
        )
    ).all()
    items = [
        {
            "id": r[0],
            "name": r[1],
            "name_zh": r[2],
            "type": r[3],
            "stat_total": r[4],
        }
        for r in rows
    ]
    _index_cache.update(ts=now, items=items)
    return {"total": len(items), "items": items, "cached": False}


def _to_out(p: Pokemon) -> PokemonOut:
    try:
        types = json.loads(p.types_json or "[]")
    except ValueError:
        types = []
    try:
        abilities = json.loads(p.abilities_json or "[]")
    except ValueError:
        abilities = []
    try:
        stats = json.loads(p.stats_json or "{}")
    except ValueError:
        stats = {}
    return PokemonOut(
        id=p.id,
        name=p.name,
        name_zh=p.name_zh,
        species_name=p.species_name,
        type_primary=p.type_primary,
        type_secondary=p.type_secondary,
        types=types,
        # 逐条补齐中文名；脏数据（非 dict / 缺 name）由 ability_out 过滤掉
        abilities=[AbilityOut(**a) for a in (ability_out(x) for x in abilities) if a],
        stats=stats,
        stat_total=p.stat_total,
        height=p.height,
        weight=p.weight,
        base_experience=p.base_experience,
        moves_count=p.moves_count,
        image_url=p.image_url,
        cry_url=p.cry_url,
        is_default=bool(p.is_default),
        updated_at=p.updated_at,
    )


@router.get("", response_model=PagedPokemon)
async def list_pokemons(
    filters: dict = Depends(pokemon_filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    stmt = stmt_from_filters(filters)
    total, rows = await list_pokemon(session, stmt, page=page, page_size=page_size)
    return PagedPokemon(
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_out(p) for p in rows],
    )


@router.get("/meta/types")
async def meta_types() -> dict:
    return {
        "types": [
            {"name": name, "zh": info["zh"], "color": info["color"]}
            for name, info in TYPE_INFO.items()
        ],
        "stats": [{"name": k, "zh": v} for k, v in STAT_INFO.items()],
    }


@router.get("/meta/abilities")
async def meta_abilities(limit: int = Query(500, ge=1, le=3000)) -> dict:
    from app.core.models import PokemonAbility  # noqa: PLC0415

    stmt = (
        select(PokemonAbility.ability_name, func.count(PokemonAbility.pokemon_id))
        .group_by(PokemonAbility.ability_name)
        .order_by(func.count(PokemonAbility.pokemon_id).desc())
        .limit(limit)
    )
    rows = (await session_execute(stmt)).all()
    return {
        "abilities": [
            {
                "name": r[0],
                "name_zh": glossary_zh("abilities", r[0]),
                "count": int(r[1]),
            }
            for r in rows
        ]
    }


async def session_execute(stmt):
    from app.core.database import get_session_factory  # noqa: PLC0415

    async with get_session_factory()() as session:
        return await session.execute(stmt)


@router.get("/filter-options", response_model=FilterOptionsOut)
async def pokemon_filter_options(
    session: AsyncSession = Depends(get_session),
) -> FilterOptionsOut:
    """图鉴分类筛选项（P2 物种档案维度）。

    计数口径为形态级 pokemon 行数：Mega/地区形态计入其物种的分类，
    与列表页筛选结果的数量保持一致。
    """
    from app.core.models import PokemonSpecies  # noqa: PLC0415

    rows = (
        await session.execute(
            select(
                PokemonSpecies.name,
                PokemonSpecies.genus_en,
                PokemonSpecies.genus_zh,
                PokemonSpecies.egg_groups_json,
                PokemonSpecies.habitat,
                PokemonSpecies.color,
                PokemonSpecies.shape,
                PokemonSpecies.growth_rate,
            )
        )
    ).all()
    counts = dict(
        (
            await session.execute(
                select(Pokemon.species_name, func.count()).group_by(Pokemon.species_name)
            )
        ).all()
    )

    def bump(bucket: dict, key: str | None, label: str, label_en: str | None, n: int) -> None:
        if not key:
            return
        item = bucket.get(key)
        if item is None:
            item = FilterOptionItem(value=key, label=label, label_en=label_en, count=0)
            bucket[key] = item
        item.count += n

    genus: dict[str, FilterOptionItem] = {}
    egg_groups: dict[str, FilterOptionItem] = {}
    habitats: dict[str, FilterOptionItem] = {}
    colors: dict[str, FilterOptionItem] = {}
    shapes: dict[str, FilterOptionItem] = {}
    growth_rates: dict[str, FilterOptionItem] = {}

    for name, genus_en, genus_zh, egg_json, habitat, color, shape, growth in rows:
        n = int(counts.get(name or "", 0))
        bump(genus, genus_en, genus_zh or genus_en or "", genus_en, n)
        try:
            groups = json.loads(egg_json or "[]")
        except ValueError:
            groups = []
        for g in groups if isinstance(groups, list) else []:
            bump(egg_groups, g, glossary_zh("egg-groups", g) or g, g, n)
        bump(habitats, habitat, glossary_zh("habitats", habitat) or habitat or "", habitat, n)
        bump(colors, color, glossary_zh("colors", color) or color or "", color, n)
        bump(shapes, shape, glossary_zh("shapes", shape) or shape or "", shape, n)
        bump(growth_rates, growth, glossary_zh("growth-rates", growth) or growth or "", growth, n)

    def ranked(bucket: dict) -> list[FilterOptionItem]:
        # 数量多的在前，同数量按字母序，保证每次渲染顺序稳定
        return sorted(bucket.values(), key=lambda i: (-i.count, i.value))

    return FilterOptionsOut(
        genus=ranked(genus),
        egg_groups=ranked(egg_groups),
        habitats=ranked(habitats),
        colors=ranked(colors),
        shapes=ranked(shapes),
        growth_rates=ranked(growth_rates),
    )


@router.get("/{id_or_name}/evolution", response_model=EvolutionOut)
async def get_evolution(
    id_or_name: str, session: AsyncSession = Depends(get_session)
) -> EvolutionOut:
    """进化链：由扁平边表组装成树，支持分支（伊布）与合流。

    入口兼容 id / 形态名 / 物种 slug。返回的是该物种所在的整棵进化树，
    由前端高亮当前物种——这样从家族任意成员进入都能看到完整链。
    """
    from app.core.models import EvolutionEdge, PokemonSpecies  # noqa: PLC0415

    species: str | None = None
    if id_or_name.isdigit():
        species = (
            await session.execute(
                select(Pokemon.species_name).where(Pokemon.id == int(id_or_name))
            )
        ).scalar_one_or_none()
    else:
        key = id_or_name.lower()
        species = (
            await session.execute(
                select(Pokemon.species_name).where(Pokemon.name == key).limit(1)
            )
        ).scalar_one_or_none()
        if species is None:
            species = (
                await session.execute(
                    select(PokemonSpecies.name).where(PokemonSpecies.name == key).limit(1)
                )
            ).scalar_one_or_none()
    if not species:
        # 边表本身就是物种名的权威来源：主表/档案表缺失时仍应能看链
        # （如上游物种档案未抓全，但进化边已入库）
        probe = id_or_name.lower()
        hit = (
            await session.execute(
                select(EvolutionEdge.from_species)
                .where(EvolutionEdge.from_species == probe)
                .limit(1)
            )
        ).scalar_one_or_none()
        if hit is None:
            hit = (
                await session.execute(
                    select(EvolutionEdge.to_species)
                    .where(EvolutionEdge.to_species == probe)
                    .limit(1)
                )
            ).scalar_one_or_none()
        species = hit
    if not species:
        raise HTTPException(status_code=404, detail=f"未找到宝可梦：{id_or_name}")

    # 514 条边全量载入即可，无需按需查询
    edges = (await session.execute(select(EvolutionEdge))).scalars().all()
    children: dict[str, list] = {}
    parents: dict[str, set[str]] = {}
    for e in edges:
        children.setdefault(e.from_species, []).append(e)
        parents.setdefault(e.to_species, set()).add(e.from_species)

    # 无向 BFS 取连通分量：分支/合流都能完整覆盖（如伊布八分支）
    component = {species}
    queue = [species]
    while queue:
        cur = queue.pop()
        for e in children.get(cur, []):
            if e.to_species not in component:
                component.add(e.to_species)
                queue.append(e.to_species)
        for src in parents.get(cur, ()):
            if src not in component:
                component.add(src)
                queue.append(src)

    # 根 = 分量内没有入边的节点（连通分量对边闭合，入边来源必在分量内）
    roots = sorted(s for s in component if not parents.get(s))

    # 节点元数据：默认形态优先作代表，其次 id 最小
    best: dict[str, dict] = {}
    meta = (
        await session.execute(
            select(
                Pokemon.species_name,
                Pokemon.id,
                Pokemon.name_zh,
                Pokemon.image_url,
                Pokemon.is_default,
            ).where(Pokemon.species_name.in_(component))
        )
    ).all()
    for sn, pid, pzh, img, is_def in meta:
        if not sn:
            continue
        rank = (0 if is_def else 1, pid)
        cur = best.get(sn)
        if cur is None or rank < cur[0]:
            best[sn] = (rank, {"pokemon_id": pid, "name_zh": pzh, "image_url": img})

    def to_condition(e) -> EvolutionConditionOut:
        try:
            variants = json.loads(e.detail_json or "[]")
        except ValueError:
            variants = []
        if not isinstance(variants, list):
            variants = []
        # P4：条件里引用的招式名附加官方译名（前端常量只覆盖封闭枚举，
        # 招式名走后端 glossary，前端取 name_zh 回落 name）
        for v in variants:
            if not isinstance(v, dict):
                continue
            km = v.get("known_move")
            if isinstance(km, dict) and km.get("name"):
                km["name_zh"] = glossary_zh("moves", km["name"])
        return EvolutionConditionOut(
            trigger=e.trigger,
            trigger_zh=glossary_zh("evolution-trigger", e.trigger),
            min_level=e.min_level or 0,
            item=e.item or "",
            time_of_day=e.time_of_day or "",
            variants=variants,
        )

    def build(species_name: str, path: frozenset[str]) -> EvolutionNodeOut:
        info = best.get(species_name, (None, {}))[1]
        node = EvolutionNodeOut(
            species=species_name,
            name_zh=info.get("name_zh"),
            pokemon_id=info.get("pokemon_id"),
            image_url=info.get("image_url"),
        )
        if species_name in path:  # 数据成环防御：只渲染节点本身
            return node
        grouped: dict[str, list] = {}
        for e in children.get(species_name, []):
            grouped.setdefault(e.to_species, []).append(e)
        deeper = path | {species_name}
        for to_name in sorted(grouped):
            child = build(to_name, deeper)
            child.conditions = [to_condition(e) for e in grouped[to_name]]
            node.children.append(child)
        return node

    root_nodes = [build(r, frozenset()) for r in roots] or [build(species, frozenset())]
    return EvolutionOut(
        species=species,
        name_zh=best.get(species, (None, {}))[1].get("name_zh"),
        roots=root_nodes,
        total_nodes=len(component),
    )


async def _load_moves(session: AsyncSession, pokemon_id: int) -> list[dict]:
    """加载某只宝可梦的招式明细（带中文）。

    只在详情接口调用：列表接口若也带上，100 条/页 × 平均 76 个招式会让 payload 爆炸。
    """
    from app.core.models import PokemonMove  # noqa: PLC0415

    rows = (
        await session.execute(
            select(PokemonMove.move_name)
            .where(PokemonMove.pokemon_id == pokemon_id)
            .order_by(PokemonMove.move_name)
        )
    ).scalars().all()
    return [move_out(m) for m in rows]


@router.get("/{id_or_name}", response_model=PokemonOut)
async def get_pokemon(
    id_or_name: str, session: AsyncSession = Depends(get_session)
) -> PokemonOut:
    if id_or_name.isdigit():
        pokemon = await session.get(Pokemon, int(id_or_name))
    else:
        pokemon = (
            (
                await session.execute(
                    select(Pokemon).where(Pokemon.name == id_or_name.lower())
                )
            )
            .scalars()
            .first()
        )
    if pokemon is None:
        raise HTTPException(status_code=404, detail=f"未找到宝可梦：{id_or_name}")
    out = _to_out(pokemon)
    out.moves = [MoveOut(**m) for m in await _load_moves(session, pokemon.id)]
    return out


__all__ = ["router", "build_pokemon_query"]
