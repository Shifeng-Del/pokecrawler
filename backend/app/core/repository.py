"""数据访问层：查询构造、幂等 upsert、批量写。

多值字段双写由这里统一维护，业务代码永不手写 JSON 列查询。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Sequence

from sqlalchemy import and_, bindparam, delete, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import (
    AbilityDetail,
    CrawlError,
    CrawlJob,
    EvolutionEdge,
    MoveDetail,
    Pokemon,
    PokemonAbility,
    PokemonMove,
    PokemonSpecies,
    PokemonStat,
    PokemonType,
)
from app.utils.hash import content_hash
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

SORTABLE = {
    "id": Pokemon.id,
    "name": Pokemon.name,
    "stat_total": Pokemon.stat_total,
    "height": Pokemon.height,
    "weight": Pokemon.weight,
    "base_experience": Pokemon.base_experience,
    "updated_at": Pokemon.updated_at,
}


# ---------------------------------------------------------------- 查询
def build_pokemon_query(
    *,
    q: str | None = None,
    types: Sequence[str] | None = None,
    type_any: Sequence[str] | None = None,
    ability: str | None = None,
    min_total: int | None = None,
    max_total: int | None = None,
    min_height: int | None = None,
    max_height: int | None = None,
    min_weight: int | None = None,
    max_weight: int | None = None,
    min_exp: int | None = None,
    max_exp: int | None = None,
    is_default: bool | None = None,
    ids: str | None = None,
    # P2 物种档案筛选（pokemon_species，按 species_name 关联到形态级 pokemon）
    genus: str | None = None,
    egg_group: str | None = None,
    habitat: str | None = None,
    color: str | None = None,
    shape: str | None = None,
    growth_rate: str | None = None,
    sort: str = "id",
    order: str = "asc",
):
    stmt = select(Pokemon)

    def species_scoped(condition):
        """形态级 → 物种级筛选：pokemon.species_name 关联 pokemon_species.name。

        必须按 species_name 关联：pokemon 主表含 Mega/地区形态（id 是形态 id），
        只有 species_name 才指向物种档案；按 pokemon_species.pokemon_id 匹配
        会漏掉全部替换形态（实测 medium-slow 336 → 261 即此 bug）。
        """
        return Pokemon.species_name.in_(select(PokemonSpecies.name).where(condition))

    if ids:
        # 限定 id 集合（前端「只看收藏」等场景）；非法片段静默忽略
        id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        if id_list:
            stmt = stmt.where(Pokemon.id.in_(id_list))
        else:
            stmt = stmt.where(Pokemon.id.in_([]))

    if q:
        pattern = f"%{q.lower()}%"
        # 同时支持英文 slug 与中文译名搜索
        stmt = stmt.where(
            or_(
                func.lower(Pokemon.name).like(pattern),
                Pokemon.name_zh.like(pattern),
            )
        )

    if types:
        # 需要同时具备所有指定属性
        for t in types:
            stmt = stmt.where(
                Pokemon.id.in_(
                    select(PokemonType.pokemon_id).where(PokemonType.type_name == t.lower())
                )
            )

    if type_any:
        stmt = stmt.where(
            Pokemon.id.in_(
                select(PokemonType.pokemon_id).where(
                    PokemonType.type_name.in_([t.lower() for t in type_any])
                )
            )
        )

    if ability:
        stmt = stmt.where(
            Pokemon.id.in_(
                select(PokemonAbility.pokemon_id).where(
                    func.lower(PokemonAbility.ability_name) == ability.lower()
                )
            )
        )

    if min_total is not None:
        stmt = stmt.where(Pokemon.stat_total >= min_total)
    if max_total is not None:
        stmt = stmt.where(Pokemon.stat_total <= max_total)
    if min_height is not None:
        stmt = stmt.where(Pokemon.height >= min_height)
    if max_height is not None:
        stmt = stmt.where(Pokemon.height <= max_height)
    if min_weight is not None:
        stmt = stmt.where(Pokemon.weight >= min_weight)
    if max_weight is not None:
        stmt = stmt.where(Pokemon.weight <= max_weight)
    if min_exp is not None:
        stmt = stmt.where(Pokemon.base_experience >= min_exp)
    if max_exp is not None:
        stmt = stmt.where(Pokemon.base_experience <= max_exp)
    if is_default is not None:
        stmt = stmt.where(Pokemon.is_default == int(is_default))

    # P2 物种档案筛选。genus 用英文原文（如 "Seed Pokémon"）匹配；
    # 蛋组是 JSON 数组列，带引号做 LIKE 精确匹配（避免 water 误中 water1）。
    if genus:
        stmt = stmt.where(species_scoped(func.lower(PokemonSpecies.genus_en) == genus.lower()))
    if egg_group:
        stmt = stmt.where(
            species_scoped(PokemonSpecies.egg_groups_json.like(f'%"{egg_group.lower()}"%'))
        )
    if habitat:
        stmt = stmt.where(species_scoped(PokemonSpecies.habitat == habitat.lower()))
    if color:
        stmt = stmt.where(species_scoped(PokemonSpecies.color == color.lower()))
    if shape:
        stmt = stmt.where(species_scoped(PokemonSpecies.shape == shape.lower()))
    if growth_rate:
        stmt = stmt.where(species_scoped(PokemonSpecies.growth_rate == growth_rate.lower()))

    column = SORTABLE.get(sort, Pokemon.id)
    stmt = stmt.order_by(column.desc() if order.lower() == "desc" else column.asc())
    return stmt


async def count_pokemon(session: AsyncSession, stmt) -> int:
    count_stmt = select(func.count()).select_from(stmt.subquery())
    result = await session.execute(count_stmt)
    return int(result.scalar_one())


async def list_pokemon(session: AsyncSession, stmt, *, page: int = 1, page_size: int = 20):
    total = await count_pokemon(session, stmt)
    offset = max((page - 1) * page_size, 0)
    rows = (
        (await session.execute(stmt.offset(offset).limit(page_size))).scalars().unique().all()
    )
    return total, rows


# ---------------------------------------------------------------- 写入
def _split(record: dict) -> tuple[dict, list, list, dict, list]:
    """拆出主表字段与子表数据。"""
    child_keys = {"_types", "_abilities", "_stats", "_moves", "_raw"}
    main = {k: v for k, v in record.items() if k not in child_keys}
    types = record.get("_types") or []
    abilities = record.get("_abilities") or []
    stats = record.get("_stats") or {}
    moves = record.get("_moves") or []
    return main, types, abilities, stats, moves


POKEMON_COLUMNS = {c.name for c in Pokemon.__table__.columns}
UPDATEABLE_COLUMNS = [c.name for c in Pokemon.__table__.columns if c.name != "id"]

# 批量更新语句：一次编译，executemany 执行，避免逐条往返
# 使用 Core 层语句（__table__）避开 ORM 的逐行同步路径，保证 executemany 生效
UPDATE_POKEMON = (
    update(Pokemon.__table__)
    .where(Pokemon.__table__.c.id == bindparam("_id"))
    .values(**{c: bindparam(c) for c in UPDATEABLE_COLUMNS})
)


async def upsert_pokemon(
    session: AsyncSession,
    record: dict,
    *,
    job_id: int | None = None,
    store_raw: bool = False,
    store_moves: bool = True,
) -> tuple[str, int | None]:
    """幂等写入单条（内部复用批量实现）。"""
    counter = await bulk_upsert(
        session,
        [record],
        job_id=job_id,
        store_raw=store_raw,
        store_moves=store_moves,
    )
    if counter["inserted"]:
        return "inserted", record.get("id")
    if counter["updated"]:
        return "updated", record.get("id")
    return "skipped", record.get("id")


async def bulk_upsert(
    session: AsyncSession,
    records: Iterable[dict],
    *,
    job_id: int | None = None,
    store_raw: bool = False,
    store_moves: bool = True,
) -> dict[str, int]:
    """批量写入，单事务、最少往返。

    做法：先一次性取出本批 id 的 content_hash 做增量判定，
    再分别用 executemany 做「新增插入 / 变更更新 / 子表重建」。
    """
    records = [r for r in records if r]
    if not records:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    now = utcnow().isoformat()
    ids = [r["id"] for r in records]

    rows = (
        await session.execute(
            select(Pokemon.id, Pokemon.content_hash, Pokemon.created_at).where(
                Pokemon.id.in_(ids)
            )
        )
    ).all()
    meta = {r[0]: (r[1], r[2]) for r in rows}

    to_insert: list[dict] = []
    to_update: list[dict] = []
    children: dict[int, tuple] = {}
    skipped = 0

    for record in records:
        main, types, abilities, stats, moves = _split(record)
        pid = main["id"]
        if pid in meta and meta[pid][0] == main.get("content_hash"):
            skipped += 1
            continue

        # 按列定义取值，保证每个 bindparam 都有值（缺失的列填 None）
        values = {c: main.get(c) for c in POKEMON_COLUMNS}
        values["crawl_job_id"] = job_id
        values["updated_at"] = now
        values["created_at"] = meta[pid][1] if pid in meta else now
        values["raw_json"] = (
            json.dumps(record.get("_raw"), ensure_ascii=False) if store_raw else None
        )

        if pid in meta:
            to_update.append(
                {"_id": pid, **{c: values[c] for c in UPDATEABLE_COLUMNS}}
            )
        else:
            to_insert.append(values)
        children[pid] = (types, abilities, stats, moves)

    try:
        if to_insert:
            await session.execute(insert(Pokemon.__table__), to_insert)
        if to_update:
            await session.execute(UPDATE_POKEMON, to_update)

        write_ids = list(children.keys())
        if write_ids:
            for table in (PokemonType, PokemonAbility, PokemonStat, PokemonMove):
                await session.execute(
                    delete(table).where(table.pokemon_id.in_(write_ids))
                )

            type_rows: list[dict] = []
            ability_rows: list[dict] = []
            stat_rows: list[dict] = []
            move_rows: list[dict] = []

            for pid, (types, abilities, stats, moves) in children.items():
                type_rows.extend(
                    {"pokemon_id": pid, "slot": i + 1, "type_name": t}
                    for i, t in enumerate(types)
                )
                ability_rows.extend(
                    {
                        "pokemon_id": pid,
                        "slot": a.get("slot") or (i + 1),
                        "ability_name": a["name"],
                        "is_hidden": int(bool(a.get("is_hidden"))),
                    }
                    for i, a in enumerate(abilities)
                )
                stat_rows.extend(
                    {"pokemon_id": pid, "stat_name": k, "base_stat": int(v)}
                    for k, v in stats.items()
                )
                if store_moves:
                    move_rows.extend(
                        {"pokemon_id": pid, "move_name": m}
                        for m in dict.fromkeys(moves)
                    )

            for table, payload in (
                (PokemonType, type_rows),
                (PokemonAbility, ability_rows),
                (PokemonStat, stat_rows),
                (PokemonMove, move_rows),
            ):
                if payload:
                    await session.execute(insert(table.__table__), payload)

        await session.commit()
    except Exception:
        await session.rollback()
        raise

    return {
        "inserted": len(to_insert),
        "updated": len(to_update),
        "skipped": skipped,
    }


# ---------------------------------------------------------------- P2 深度表写入
async def _upsert_by_hash(
    session: AsyncSession,
    model: type,
    records: Iterable[dict],
    *,
    job_id: int | None = None,
    compare_extra: tuple[str, ...] = (),
) -> dict[str, int]:
    """单表幂等 upsert：按 content_hash（+可选附加列）判定 增/改/跳。

    适用于 P2 四张深度表（species / evolution_edge / move_detail / ability_detail）：
    - 全表载入内存比对签名（表量级 ≤ 数千行，代价可忽略），
      避免复合主键在 SQLite 里做 IN 元组匹配的兼容性问题
    - 变更行用 `insert ... on conflict do update` 一次写入，created_at 不被覆盖
    - compare_extra 支持「内容没变但派生的中文列变了也要更新」（如 genus_zh 补录）
    """
    records = [r for r in records if r]
    if not records:
        return {"inserted": 0, "updated": 0, "skipped": 0}

    table = model.__table__
    pk_names = [c.name for c in table.primary_key.columns]
    all_columns = [c.name for c in table.columns]
    updatable = [c for c in all_columns if c not in pk_names and c != "created_at"]
    now = utcnow().isoformat()

    existing: dict[tuple, object] = {}
    for row in (await session.execute(select(table))).all():
        key = tuple(row._mapping[c] for c in pk_names)
        existing[key] = row

    def signature(record: dict, row: object | None) -> tuple:
        """record=None 时取记录侧签名，row=None 时取库内行侧签名。"""
        if row is None:
            return (record.get("content_hash"), *(record.get(c) for c in compare_extra))
        return (
            row._mapping.get("content_hash"),
            *(row._mapping.get(c) for c in compare_extra),
        )

    to_insert: list[dict] = []
    to_update: list[dict] = []
    inserted = updated = skipped = 0
    for record in records:
        key = tuple(record.get(c) for c in pk_names)
        old = existing.get(key)
        if old is not None and signature(record, None) == signature(record, old):
            skipped += 1
            continue
        if old is None:
            inserted += 1
            row = {c: record.get(c) for c in all_columns}
            row["created_at"] = now
            row["updated_at"] = now
            to_insert.append(row)
        else:
            updated += 1
            # created_at 不在 updatable 里，保留原值不被覆盖
            row = {f"_pk_{c}": key[i] for i, c in enumerate(pk_names)}
            row.update({c: record.get(c) for c in updatable})
            row["updated_at"] = now
            to_update.append(row)

    if to_insert:
        await session.execute(insert(table), to_insert)
    if to_update:
        stmt = (
            update(table)
            .where(and_(*[table.c[c] == bindparam(f"_pk_{c}") for c in pk_names]))
            .values(**{c: bindparam(c) for c in updatable})
        )
        await session.execute(stmt, to_update)
    await session.commit()

    return {"inserted": inserted, "updated": updated, "skipped": skipped}


async def bulk_upsert_species(
    session: AsyncSession,
    records: Iterable[dict],
    *,
    job_id: int | None = None,
    store_raw: bool = False,
    store_moves: bool = True,
) -> dict[str, int]:
    """物种档案写入。

    compare_extra 带 genus_zh：payload 的 content_hash 不含人工补录的译文，
    只有把 genus_zh 也纳入签名，补录 zh_genera.json 后重跑才能真正落库。
    """
    return await _upsert_by_hash(
        session,
        PokemonSpecies,
        records,
        job_id=job_id,
        compare_extra=("genus_zh",),
    )


# 进化边主键六列（顺序即匹配顺序，与 EvolutionEdge 模型一致）
EDGE_PK = ("from_species", "to_species", "trigger", "min_level", "item", "time_of_day")


def _merge_edges(records: Iterable[dict]) -> list[dict]:
    """把链级记录里的边按「进化方法」合并为待写行。

    PokeAPI 的实测数据里同一进化方法会出现多次：
    - 跨链重复：同一对物种写在多条链里，条件快照略有差异（如皮卡丘→雷丘）
    - 同链多变体：一条链里按地点等条件列多个变体（如小磁怪→三合一磁怪按岩石列了 4 次）
    以主键六列为方法标识合并成一行，避免同批次/跨批次主键冲突：
    - detail_json 存条件变体数组（排序后稳定），信息不丢
    - content_hash 覆盖六元组 + 全部变体，变体增减能被增量判定捕获
    """
    merged: dict[tuple, dict] = {}
    for record in records:
        if not record:
            continue
        for edge in record.get("_edges") or []:
            key = tuple(edge.get(c) for c in EDGE_PK)
            current = merged.get(key)
            if current is None:
                row = dict(edge)
                row["_variants"] = [json.loads(edge["detail_json"])]
                merged[key] = row
                continue
            variants = current["_variants"]
            condition = json.loads(edge["detail_json"])
            if condition not in variants:
                variants.append(condition)

    out: list[dict] = []
    for row in merged.values():
        variants = sorted(
            row["_variants"],
            key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False, default=str),
        )
        out.append(
            {
                **{c: row.get(c) for c in EDGE_PK},
                "detail_json": json.dumps(variants, ensure_ascii=False, sort_keys=True),
                "content_hash": content_hash(
                    {**{c: row.get(c) for c in EDGE_PK}, "variants": variants}
                ),
            }
        )
    return out


async def bulk_upsert_evolution(
    session: AsyncSession,
    records: Iterable[dict],
    *,
    job_id: int | None = None,
    store_raw: bool = False,
    store_moves: bool = True,
) -> dict[str, int]:
    """进化边写入：先按主键归并同方法边（含变体），再走通用增量 upsert。"""
    return await _upsert_by_hash(
        session, EvolutionEdge, _merge_edges(records), job_id=job_id
    )


async def bulk_upsert_move_detail(
    session: AsyncSession,
    records: Iterable[dict],
    *,
    job_id: int | None = None,
    store_raw: bool = False,
    store_moves: bool = True,
) -> dict[str, int]:
    return await _upsert_by_hash(
        session, MoveDetail, records, job_id=job_id
    )


async def bulk_upsert_ability_detail(
    session: AsyncSession,
    records: Iterable[dict],
    *,
    job_id: int | None = None,
    store_raw: bool = False,
    store_moves: bool = True,
) -> dict[str, int]:
    return await _upsert_by_hash(
        session, AbilityDetail, records, job_id=job_id
    )


# ---------------------------------------------------------------- 任务
async def create_job(session: AsyncSession, **fields) -> CrawlJob:
    job = CrawlJob(created_at=utcnow().isoformat(), **fields)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def update_job(session: AsyncSession, job_id: int, **fields) -> None:
    job = await session.get(CrawlJob, job_id)
    if job is None:
        return
    for key, value in fields.items():
        setattr(job, key, value)
    await session.commit()


async def record_error(
    session: AsyncSession,
    *,
    job_id: int | None,
    target: str,
    url: str | None,
    error: str,
) -> None:
    session.add(
        CrawlError(
            job_id=job_id,
            target=target,
            url=url,
            error=error[:2000],
            created_at=utcnow().isoformat(),
        )
    )
    await session.commit()


async def list_failed_targets(session: AsyncSession, limit: int = 200) -> list[str]:
    rows = (
        (await session.execute(select(CrawlError.target).limit(limit))).scalars().all()
    )
    return [r for r in rows if r]


__all__: list[Any] = [
    "build_pokemon_query",
    "list_pokemon",
    "count_pokemon",
    "bulk_upsert",
    "bulk_upsert_species",
    "bulk_upsert_evolution",
    "bulk_upsert_move_detail",
    "bulk_upsert_ability_detail",
    "create_job",
    "update_job",
    "record_error",
    "list_failed_targets",
]
