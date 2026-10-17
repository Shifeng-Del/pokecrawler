"""仓储层：幂等 upsert 与筛选查询。"""

from sqlalchemy import func, select

from app.core.models import Pokemon, PokemonStat, PokemonType
from app.core.repository import (
    build_pokemon_query,
    bulk_upsert,
    list_pokemon,
)
from app.crawler.adapters.pokeapi import PokeAPIAdapter
from config.settings import get_settings


def _record(bulbasaur_payload):
    adapter = PokeAPIAdapter(fetcher=None, settings=get_settings())
    return adapter.map_payload(bulbasaur_payload)


async def test_upsert_is_idempotent(db_session, bulbasaur_payload):
    record = _record(bulbasaur_payload)

    first = await bulk_upsert(db_session, [record], job_id=1)
    assert first["inserted"] == 1

    second = await bulk_upsert(db_session, [record], job_id=2)
    assert second["skipped"] == 1
    assert second["inserted"] == 0

    # 内容变化后应更新
    changed = dict(bulbasaur_payload)
    changed["base_experience"] = 999
    third = await bulk_upsert(db_session, [_record(changed)], job_id=3)
    assert third["updated"] == 1

    pokemon = await db_session.get(Pokemon, 1)
    assert pokemon.base_experience == 999
    assert pokemon.stat_total == 318


async def test_child_tables_written(db_session, bulbasaur_payload):
    await bulk_upsert(db_session, [_record(bulbasaur_payload)], job_id=1)

    types = (
        (await db_session.execute(select(PokemonType).where(PokemonType.pokemon_id == 1)))
        .scalars()
        .all()
    )
    assert sorted(t.type_name for t in types) == ["grass", "poison"]

    stats = (
        (await db_session.execute(select(PokemonStat).where(PokemonStat.pokemon_id == 1)))
        .scalars()
        .all()
    )
    assert len(stats) == 6
    assert {s.stat_name: s.base_stat for s in stats}["hp"] == 45


async def test_filters(db_session, bulbasaur_payload):
    await bulk_upsert(db_session, [_record(bulbasaur_payload)], job_id=1)

    # 属性筛选（同时满足）
    stmt = build_pokemon_query(types=["grass", "poison"])
    total, rows = await list_pokemon(db_session, stmt)
    assert total == 1
    assert rows[0].name == "bulbasaur"

    # 不满足的属性组合
    stmt = build_pokemon_query(types=["fire"])
    total, _ = await list_pokemon(db_session, stmt)
    assert total == 0

    # 关键词搜索
    stmt = build_pokemon_query(q="bulb")
    total, _ = await list_pokemon(db_session, stmt)
    assert total == 1

    stmt = build_pokemon_query(q="pikachu")
    total, _ = await list_pokemon(db_session, stmt)
    assert total == 0

    # 种族值区间
    stmt = build_pokemon_query(min_total=300, max_total=400)
    total, _ = await list_pokemon(db_session, stmt)
    assert total == 1

    stmt = build_pokemon_query(min_total=600)
    total, _ = await list_pokemon(db_session, stmt)
    assert total == 0

    count = int(
        (await db_session.execute(select(func.count(Pokemon.id)))).scalar_one()
    )
    assert count == 1
