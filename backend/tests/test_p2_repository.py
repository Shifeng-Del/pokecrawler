"""P2 仓储层：四张深度表的幂等写入与增量更新语义。"""

from __future__ import annotations

import json

import pytest

from app.core.models import (
    AbilityDetail,
    EvolutionEdge,
    MoveDetail,
    PokemonSpecies,
)
from app.core.repository import (
    bulk_upsert_ability_detail,
    bulk_upsert_evolution,
    bulk_upsert_move_detail,
    bulk_upsert_species,
)
from app.crawler.adapters.pokeapi import (
    AbilityDetailAdapter,
    EvolutionAdapter,
    MoveDetailAdapter,
    SpeciesAdapter,
)
from config.settings import get_settings


def _species_record(**overrides):
    payload = {
        "id": 1,
        "name": "bulbasaur",
        "genera": [
            {"genus": "Seed Pokémon", "language": {"name": "en"}},
            {"genus": "种子宝可梦", "language": {"name": "zh-hans"}},
        ],
        "egg_groups": [{"name": "monster"}, {"name": "plant"}],
        "habitat": {"name": "grassland"},
        "capture_rate": 45,
    }
    payload.update(overrides)
    return SpeciesAdapter(fetcher=None, settings=get_settings()).map_payload(payload)


def _chain_record():
    payload = {
        "id": 1,
        "chain": {
            "species": {"name": "bulbasaur"},
            "evolves_to": [
                {
                    "species": {"name": "ivysaur"},
                    "evolution_details": [
                        {"trigger": {"name": "level-up"}, "min_level": 16}
                    ],
                    "evolves_to": [],
                }
            ],
        },
    }
    return EvolutionAdapter(fetcher=None, settings=get_settings()).map_payload(payload)


def _move_record():
    payload = {
        "name": "tackle",
        "power": 40,
        "accuracy": 100,
        "pp": 35,
        "priority": 0,
        "damage_class": {"name": "physical"},
        "type": {"name": "normal"},
        "generation": {"name": "generation-i"},
        "effect_entries": [{"effect": "Damage.", "language": {"name": "en"}}],
        "flavor_text_entries": [],
    }
    return MoveDetailAdapter(fetcher=None, settings=get_settings()).map_payload(payload)


def _ability_record():
    payload = {
        "name": "overgrow",
        "is_main_series": True,
        "generation": {"name": "generation-iii"},
        "effect_entries": [{"effect": "Buffs.", "language": {"name": "en"}}],
        "flavor_text_entries": [],
    }
    return AbilityDetailAdapter(fetcher=None, settings=get_settings()).map_payload(payload)


# ---------------------------------------------------------------- species
async def test_species_upsert_idempotent(db_session):
    record = _species_record()

    first = await bulk_upsert_species(db_session, [record], job_id=1)
    assert first == {"inserted": 1, "updated": 0, "skipped": 0}

    second = await bulk_upsert_species(db_session, [record], job_id=2)
    assert second == {"inserted": 0, "updated": 0, "skipped": 1}

    row = await db_session.get(PokemonSpecies, 1)
    assert row.genus_zh == "种子宝可梦"
    assert row.created_at  # created_at 有值且不被覆盖


async def test_species_updates_when_payload_changes(db_session):
    await bulk_upsert_species(db_session, [_species_record()], job_id=1)
    changed = _species_record(capture_rate=999)
    # map_payload 的 content_hash 覆盖整个 payload，capture_rate 变化必然改变哈希
    assert changed["content_hash"] != _species_record()["content_hash"]

    counter = await bulk_upsert_species(db_session, [changed], job_id=2)
    assert counter["updated"] == 1
    row = await db_session.get(PokemonSpecies, 1)
    assert row.capture_rate == 999


async def test_species_updates_when_only_genus_zh_changes(db_session):
    """hash 没变但 genus_zh 补录了（zh_genera.json 落地）也要能更新——compare_extra 的用途。"""
    record = _species_record()
    record["genus_zh"] = None  # 模拟官方缺失、首轮未补录
    await bulk_upsert_species(db_session, [record], job_id=1)
    row = await db_session.get(PokemonSpecies, 1)
    assert row.genus_zh is None

    filled = dict(record)
    filled["genus_zh"] = "种子宝可梦"  # content_hash 不变
    counter = await bulk_upsert_species(db_session, [filled], job_id=2)
    assert counter == {"inserted": 0, "updated": 1, "skipped": 0}
    row = await db_session.get(PokemonSpecies, 1)
    # 会话 expire_on_commit=False：跨事务断言前必须 refresh，否则读到身份映射里的旧值
    await db_session.refresh(row)
    assert row.genus_zh == "种子宝可梦"


# ---------------------------------------------------------------- evolution
async def test_evolution_upsert_flattens_edges(db_session):
    counter = await bulk_upsert_evolution(db_session, [_chain_record()], job_id=1)
    assert counter == {"inserted": 1, "updated": 0, "skipped": 0}

    edges = (
        (await db_session.execute(EvolutionEdge.__table__.select()))
        .mappings()
        .all()
    )
    assert len(edges) == 1
    edge = edges[0]
    assert edge["from_species"] == "bulbasaur"
    assert edge["to_species"] == "ivysaur"
    assert edge["trigger"] == "level-up"
    assert edge["min_level"] == 16
    assert edge["item"] == ""  # 无条件字段 NOT NULL 化为 ""
    # detail_json 入库时是条件变体数组（这里只有一个变体）
    variants = json.loads(edge["detail_json"])
    assert isinstance(variants, list) and len(variants) == 1
    assert variants[0]["trigger"]["name"] == "level-up"


async def test_evolution_upsert_idempotent_with_composite_pk(db_session):
    record = _chain_record()
    await bulk_upsert_evolution(db_session, [record], job_id=1)
    second = await bulk_upsert_evolution(db_session, [record], job_id=2)
    assert second == {"inserted": 0, "updated": 0, "skipped": 1}

    # 同一起点同终点的不同触发条件是不同行（复合主键区分）
    branched = {
        "id": 99,
        "chain": {
            "species": {"name": "eevee"},
            "evolves_to": [
                {
                    "species": {"name": "vaporeon"},
                    "evolution_details": [{"trigger": {"name": "use-item"}, "item": {"name": "water-stone"}}],
                },
                {
                    "species": {"name": "jolteon"},
                    "evolution_details": [{"trigger": {"name": "use-item"}, "item": {"name": "thunder-stone"}}],
                },
            ],
        },
    }
    mapped = EvolutionAdapter(fetcher=None, settings=get_settings()).map_payload(branched)
    counter = await bulk_upsert_evolution(db_session, [mapped], job_id=3)
    assert counter["inserted"] == 2
    total = len(
        (await db_session.execute(EvolutionEdge.__table__.select())).mappings().all()
    )
    assert total == 3


async def test_evolution_skips_null_level_duplicates(db_session):
    """NULL 等级条件的边重复出现时必须去重（NOT NULL 化正是为了这个）。"""
    chain = {
        "id": 7,
        "chain": {
            "species": {"name": "golbat"},
            "evolves_to": [
                {
                    "species": {"name": "crobat"},
                    "evolution_details": [{"trigger": {"name": "level-up"}}],
                }
            ],
        },
    }
    record = EvolutionAdapter(fetcher=None, settings=get_settings()).map_payload(chain)
    assert record["_edges"][0]["min_level"] == 0
    await bulk_upsert_evolution(db_session, [record], job_id=1)
    counter = await bulk_upsert_evolution(db_session, [record], job_id=2)
    assert counter["skipped"] == 1
    total = len(
        (await db_session.execute(EvolutionEdge.__table__.select())).mappings().all()
    )
    assert total == 1


def _chain_with_details(chain_id: int, from_name: str, to_name: str, details: list[dict]) -> dict:
    return {
        "id": chain_id,
        "chain": {
            "species": {"name": from_name},
            "evolves_to": [
                {
                    "species": {"name": to_name},
                    "evolution_details": details,
                    "evolves_to": [],
                }
            ],
        },
    }


async def test_evolution_merges_variants_within_batch(db_session):
    """同一方法（六元组相同）的多条边必须归并成一行，变体进 detail_json 数组。

    真实数据里的两种情形：
    - 同链多变体：小磁怪→三合一磁怪按地点列了 4 个 level-up 变体
    - 跨链重复：同一对物种写在多条链里，条件快照略有差异
    """
    magnemite_a = _chain_with_details(
        10,
        "magnemite",
        "magneton",
        [
            {"trigger": {"name": "level-up"}, "min_level": 30, "location": {"name": "mt-coronet"}},
            {"trigger": {"name": "level-up"}, "min_level": 30, "location": {"name": "route-13"}},
        ],
    )
    # 跨链重复：另一条链里同一方法、条件快照不同（location 为空）
    magnemite_b = _chain_with_details(
        999,
        "magnemite",
        "magneton",
        [{"trigger": {"name": "level-up"}, "min_level": 30, "location": None}],
    )
    records = [
        EvolutionAdapter(fetcher=None, settings=get_settings()).map_payload(p)
        for p in (magnemite_a, magnemite_b)
    ]
    # 适配器层先产出 3 条边（六元组全部相同）
    assert sum(len(r["_edges"]) for r in records) == 3

    counter = await bulk_upsert_evolution(db_session, records, job_id=1)
    assert counter == {"inserted": 1, "updated": 0, "skipped": 0}

    edges = (
        (await db_session.execute(EvolutionEdge.__table__.select())).mappings().all()
    )
    assert len(edges) == 1
    variants = json.loads(edges[0]["detail_json"])
    # 三个条件快照去重后剩 3 个变体（location 各不相同）
    assert len(variants) == 3
    assert {v.get("location") and v["location"]["name"] for v in variants} == {
        "mt-coronet",
        "route-13",
        None,
    }

    # 重跑：变体集合不变 -> 跳过
    counter = await bulk_upsert_evolution(db_session, records, job_id=2)
    assert counter == {"inserted": 0, "updated": 0, "skipped": 1}


async def test_evolution_updates_when_new_variant_appears(db_session):
    """后续抓取新增了变体（content_hash 覆盖变体集合）必须触发更新。"""
    first = _chain_with_details(1, "magnemite", "magneton", [{"trigger": {"name": "level-up"}, "min_level": 30}])
    await bulk_upsert_evolution(
        db_session,
        [EvolutionAdapter(fetcher=None, settings=get_settings()).map_payload(first)],
        job_id=1,
    )

    second = _chain_with_details(
        2,
        "magnemite",
        "magneton",
        [
            {"trigger": {"name": "level-up"}, "min_level": 30},
            {"trigger": {"name": "level-up"}, "min_level": 30, "location": {"name": "route-13"}},
        ],
    )
    counter = await bulk_upsert_evolution(
        db_session,
        [EvolutionAdapter(fetcher=None, settings=get_settings()).map_payload(second)],
        job_id=2,
    )
    assert counter == {"inserted": 0, "updated": 1, "skipped": 0}
    edges = (
        (await db_session.execute(EvolutionEdge.__table__.select())).mappings().all()
    )
    assert len(edges) == 1
    assert len(json.loads(edges[0]["detail_json"])) == 2


# ---------------------------------------------------------------- move / ability
async def test_move_detail_upsert(db_session):
    record = _move_record()
    first = await bulk_upsert_move_detail(db_session, [record], job_id=1)
    assert first == {"inserted": 1, "updated": 0, "skipped": 0}

    second = await bulk_upsert_move_detail(db_session, [record], job_id=2)
    assert second["skipped"] == 1

    row = await db_session.get(MoveDetail, "tackle")
    assert row.power == 40
    assert row.type_name == "normal"
    assert row.damage_class == "physical"


async def test_ability_detail_upsert(db_session):
    record = _ability_record()
    first = await bulk_upsert_ability_detail(db_session, [record], job_id=1)
    assert first == {"inserted": 1, "updated": 0, "skipped": 0}

    row = await db_session.get(AbilityDetail, "overgrow")
    assert row.effect_en == "Buffs."
    assert row.is_main_series == 1


async def test_empty_records_are_noop(db_session):
    for writer in (
        bulk_upsert_species,
        bulk_upsert_evolution,
        bulk_upsert_move_detail,
        bulk_upsert_ability_detail,
    ):
        assert await writer(db_session, []) == {"inserted": 0, "updated": 0, "skipped": 0}
