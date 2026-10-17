"""P3 接口测试：分类筛选项 / 进化链组装 / 招式图鉴 / 特性明细。

数据经仓储层真实写入（不 mock 数据库），再用 TestClient 走完整 HTTP 链路，
覆盖「筛选 → 列表 → 详情 → 悬停批量」四个前端消费场景。
"""

from __future__ import annotations

import asyncio
import copy

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_session_factory
from app.core.repository import (
    bulk_upsert,
    bulk_upsert_ability_detail,
    bulk_upsert_evolution,
    bulk_upsert_move_detail,
    bulk_upsert_species,
)
from app.crawler.adapters.pokeapi import (
    AbilityDetailAdapter,
    EvolutionAdapter,
    MoveDetailAdapter,
    PokeAPIAdapter,
    SpeciesAdapter,
)
from config.settings import get_settings


# ---------------------------------------------------------------- fixtures
@pytest.fixture
def bulbasaur_species_payload() -> dict:
    """物种档案（结构对齐 PokeAPI /pokemon-species/{id}/，字段已裁剪）。"""
    return {
        "id": 1,
        "name": "bulbasaur",
        "capture_rate": 45,
        "gender_rate": 1,
        "hatch_counter": 20,
        "genera": [
            {"genus": "Seed Pokémon", "language": {"name": "en"}},
            {"genus": "种子宝可梦", "language": {"name": "zh-hans"}},
        ],
        "egg_groups": [{"name": "monster"}, {"name": "plant"}],
        "habitat": {"name": "grassland"},
        "color": {"name": "green"},
        "shape": {"name": "quadruped"},
        "growth_rate": {"name": "medium-slow"},
        "is_legendary": False,
        "is_mythical": False,
        "generation": {"name": "generation-i"},
        "evolution_chain": {"url": "https://pokeapi.co/api/v2/evolution-chain/1/"},
    }


@pytest.fixture
def tackle_payload() -> dict:
    return {
        "id": 1,
        "name": "tackle",
        "power": 40,
        "accuracy": 100,
        "pp": 35,
        "priority": 0,
        "effect_chance": None,
        "damage_class": {"name": "physical"},
        "type": {"name": "normal"},
        "generation": {"name": "generation-i"},
        "effect_entries": [
            {"effect": "Inflige des dégâts.", "language": {"name": "fr"}},
            {"effect": "Inflicts regular damage.", "language": {"name": "en"}},
            {"short_effect": "Deals damage.", "language": {"name": "en"}},
        ],
        "flavor_text_entries": [
            {"flavor_text": "Old flavor.", "language": {"name": "en"}, "version_group": {"name": "red-blue"}},
            {"flavor_text": "New flavor.", "language": {"name": "en"}, "version_group": {"name": "sword-shield"}},
        ],
    }


@pytest.fixture
def bulbasaur_chain_payload() -> dict:
    """进化链（bulbasaur -> ivysaur(16) -> venusaur(32)）。"""
    return {
        "id": 1,
        "chain": {
            "is_baby": False,
            "species": {"name": "bulbasaur", "url": "https://pokeapi.co/api/v2/pokemon-species/1/"},
            "evolution_details": [],
            "evolves_to": [
                {
                    "is_baby": False,
                    "species": {"name": "ivysaur", "url": "https://pokeapi.co/api/v2/pokemon-species/2/"},
                    "evolution_details": [
                        {
                            "trigger": {"name": "level-up"},
                            "min_level": 16,
                            "item": None,
                            "time_of_day": "",
                            "gender": None,
                            "held_item": None,
                            "known_move": None,
                            "location": None,
                            "min_happiness": None,
                            "needs_overworld_rain": False,
                            "turn_upside_down": False,
                        }
                    ],
                    "evolves_to": [
                        {
                            "is_baby": False,
                            "species": {"name": "venusaur", "url": "https://pokeapi.co/api/v2/pokemon-species/3/"},
                            "evolution_details": [
                                {
                                    "trigger": {"name": "level-up"},
                                    "min_level": 32,
                                    "item": None,
                                    "time_of_day": "",
                                }
                            ],
                            "evolves_to": [],
                        }
                    ],
                }
            ],
        },
    }


@pytest.fixture
def ivysaur_payload():
    """ivysaur 形态级 payload（species 指向 ivysaur）。"""
    return {
        "id": 2,
        "name": "ivysaur",
        "order": 2,
        "is_default": True,
        "base_experience": 142,
        "height": 10,
        "weight": 130,
        "species": {"name": "ivysaur", "url": "https://pokeapi.co/api/v2/pokemon-species/2/"},
        "types": [{"slot": 1, "type": {"name": "grass"}}, {"slot": 2, "type": {"name": "poison"}}],
        "abilities": [{"slot": 1, "is_hidden": False, "ability": {"name": "overgrow"}}],
        "stats": [
            {"base_stat": 60, "stat": {"name": "hp"}},
            {"base_stat": 62, "stat": {"name": "attack"}},
            {"base_stat": 63, "stat": {"name": "defense"}},
            {"base_stat": 80, "stat": {"name": "special-attack"}},
            {"base_stat": 80, "stat": {"name": "special-defense"}},
            {"base_stat": 60, "stat": {"name": "speed"}},
        ],
        "moves": [{"move": {"name": "tackle"}}],
        "sprites": {"other": {"official-artwork": {"front_default": "https://example.com/2.png"}}},
        "cries": {"latest": "https://example.com/2.ogg"},
    }


@pytest.fixture
def ivysaur_species_payload(bulbasaur_species_payload):
    payload = copy.deepcopy(bulbasaur_species_payload)
    payload["id"] = 2
    payload["name"] = "ivysaur"
    payload["shape"] = {"name": "upright"}  # 与 bulbasaur 的 quadruped 区分
    return payload


@pytest.fixture
def snorlax_species_payload(bulbasaur_species_payload):
    """单段进化物种（无任何边），用于验证孤立节点渲染。"""
    payload = copy.deepcopy(bulbasaur_species_payload)
    payload["id"] = 143
    payload["name"] = "snorlax"
    payload["habitat"] = {"name": "mountain"}
    payload["color"] = {"name": "black"}
    payload["shape"] = {"name": "ball"}
    payload["growth_rate"] = {"name": "slow"}
    return payload


@pytest.fixture
def eevee_chain_payload():
    """伊布分支链：一个根、三种进化方式（升级/道具/亲密度）。"""
    def detail(**kw):
        base = {
            "trigger": {"name": "level-up"},
            "min_level": None,
            "item": None,
            "time_of_day": "",
            "gender": None,
            "held_item": None,
            "known_move": None,
            "location": None,
            "min_happiness": None,
            "needs_overworld_rain": False,
            "turn_upside_down": False,
        }
        base.update(kw)
        return base

    def child(name, details):
        return {
            "is_baby": False,
            "species": {"name": name, "url": f"https://pokeapi.co/api/v2/pokemon-species/x/"},
            "evolution_details": details,
            "evolves_to": [],
        }

    return {
        "id": 67,
        "chain": {
            "is_baby": False,
            "species": {"name": "eevee", "url": "https://pokeapi.co/api/v2/pokemon-species/133/"},
            "evolution_details": [],
            "evolves_to": [
                child("vaporeon", [detail(item={"name": "water-stone"})]),
                child("jolteon", [detail(item={"name": "thunder-stone"})]),
                child(
                    "umbreon",
                    [detail(min_happiness=160, time_of_day="night")],
                ),
            ],
        },
    }


@pytest.fixture
def growl_payload(tackle_payload):
    """变化招式：power 为 None，验证空值排序与展示。"""
    payload = copy.deepcopy(tackle_payload)
    payload["id"] = 45
    payload["name"] = "growl"
    payload["power"] = None
    payload["accuracy"] = 100
    payload["pp"] = 40
    payload["damage_class"] = {"name": "status"}
    payload["type"] = {"name": "normal"}
    return payload


@pytest.fixture
def overgrow_payload():
    return {
        "id": 1,
        "name": "overgrow",
        "generation": {"name": "generation-iii"},
        "is_main_series": True,
        "effect_entries": [
            {"effect": "Boosts grass moves at 1/3 HP.", "language": {"name": "en"}},
        ],
        "flavor_text_entries": [
            {"flavor_text": "Powers up grass moves.", "language": {"name": "en"}},
        ],
    }


def _seed(*record_groups) -> None:
    """在独立事件循环里清表并写入，避免与 TestClient 的事件循环冲突。

    先清空全部表：本文件不用 db_session 夹具，但测试库文件跨文件共用，
    不清表会受到其他测试文件残留数据的影响（断言数量将不确定）。
    """

    async def _run():
        from sqlalchemy import delete

        from app.core.database import dispose_engine, get_session_factory, init_db
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

        await init_db()
        async with get_session_factory()() as session:
            for table in (
                PokemonType,
                PokemonAbility,
                PokemonStat,
                PokemonMove,
                CrawlError,
                CrawlJob,
                Pokemon,
                EvolutionEdge,
                MoveDetail,
                AbilityDetail,
                PokemonSpecies,
            ):
                await session.execute(delete(table))
            await session.commit()
            for writer, records in record_groups:
                await writer(session, records, job_id=1)
        await dispose_engine()

    asyncio.run(_run())


@pytest.fixture
def seeded(
    bulbasaur_payload,
    ivysaur_payload,
    bulbasaur_species_payload,
    ivysaur_species_payload,
    snorlax_species_payload,
    bulbasaur_chain_payload,
    eevee_chain_payload,
    tackle_payload,
    growl_payload,
    overgrow_payload,
):
    settings = get_settings()
    poke = PokeAPIAdapter(fetcher=None, settings=settings)
    species = SpeciesAdapter(fetcher=None, settings=settings)
    evo = EvolutionAdapter(fetcher=None, settings=settings)
    move = MoveDetailAdapter(fetcher=None, settings=settings)
    ability = AbilityDetailAdapter(fetcher=None, settings=settings)
    _seed(
        (bulk_upsert, [poke.map_payload(bulbasaur_payload), poke.map_payload(ivysaur_payload)]),
        (
            bulk_upsert_species,
            [
                species.map_payload(bulbasaur_species_payload),
                species.map_payload(ivysaur_species_payload),
                species.map_payload(snorlax_species_payload),
            ],
        ),
        (
            bulk_upsert_evolution,
            [evo.map_payload(bulbasaur_chain_payload), evo.map_payload(eevee_chain_payload)],
        ),
        (bulk_upsert_move_detail, [move.map_payload(tackle_payload), move.map_payload(growl_payload)]),
        (bulk_upsert_ability_detail, [ability.map_payload(overgrow_payload)]),
    )


# ---------------------------------------------------------------- 分类筛选
def test_filter_options_structure(seeded):
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/pokemon/filter-options")
        assert resp.status_code == 200
        body = resp.json()
        for key in ("genus", "egg_groups", "habitats", "colors", "shapes", "growth_rates"):
            assert key in body and isinstance(body[key], list)

        genus = {g["value"]: g for g in body["genus"]}
        assert "Seed Pokémon" in genus
        assert "种子" in genus["Seed Pokémon"]["label"]
        assert genus["Seed Pokémon"]["count"] == 2  # bulbasaur + ivysaur

        habitats = {h["value"]: h for h in body["habitats"]}
        assert habitats["grassland"]["count"] == 2
        # snorlax 只有物种行、没有形态行，计数为 0 但不丢选项
        assert habitats["mountain"]["count"] == 0

        eggs = {e["value"]: e for e in body["egg_groups"]}
        assert eggs["monster"]["count"] == 2
        assert eggs["plant"]["count"] == 2

        shapes = {s["value"]: s for s in body["shapes"]}
        assert shapes["quadruped"]["count"] == 1
        assert shapes["upright"]["count"] == 1


@pytest.mark.parametrize(
    "query,expected",
    [
        ({"genus": "Seed Pokémon"}, 2),
        ({"egg_group": "plant"}, 2),
        ({"egg_group": "water1"}, 0),
        ({"habitat": "grassland"}, 2),
        ({"habitat": "mountain"}, 0),
        ({"color": "green"}, 2),
        ({"shape": "upright"}, 1),
        ({"growth_rate": "medium-slow"}, 2),
        ({"growth_rate": "slow"}, 0),
    ],
)
def test_species_filters_apply(seeded, query, expected):
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/pokemon", params=query)
        assert resp.status_code == 200
        assert resp.json()["total"] == expected


def test_species_filter_combines_with_type(seeded):
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/pokemon", params={"habitat": "grassland", "type": "grass"})
        assert resp.json()["total"] == 2
        resp = client.get("/api/v1/pokemon", params={"habitat": "grassland", "type": "fire"})
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------- 进化链
def test_evolution_chain_tree(seeded):
    from app.main import app

    with TestClient(app) as client:
        for entry, expected in (("bulbasaur", "bulbasaur"), ("1", "bulbasaur"), ("ivysaur", "ivysaur")):
            resp = client.get(f"/api/v1/pokemon/{entry}/evolution")
            assert resp.status_code == 200, entry
            body = resp.json()
            assert body["species"] == expected
            assert body["total_nodes"] == 3
            assert len(body["roots"]) == 1
            root = body["roots"][0]
            assert root["species"] == "bulbasaur"
            assert root["pokemon_id"] == 1
            assert len(root["children"]) == 1
            ivy = root["children"][0]
            assert ivy["species"] == "ivysaur"
            assert ivy["pokemon_id"] == 2
            assert len(ivy["conditions"]) == 1
            cond = ivy["conditions"][0]
            assert cond["trigger"] == "level-up"
            assert cond["min_level"] == 16
            assert cond["item"] == ""
            assert cond["time_of_day"] == ""
            assert isinstance(cond["variants"], list) and cond["variants"]
            venusaur = ivy["children"][0]
            assert venusaur["species"] == "venusaur"
            assert venusaur["conditions"][0]["min_level"] == 32
            assert venusaur["children"] == []


def test_evolution_chain_branching(seeded):
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/pokemon/eevee/evolution")
        assert resp.status_code == 200
        body = resp.json()
        assert body["species"] == "eevee"
        assert len(body["roots"]) == 1
        root = body["roots"][0]
        assert root["species"] == "eevee"
        kids = {c["species"]: c for c in root["children"]}
        assert set(kids) == {"vaporeon", "jolteon", "umbreon"}
        assert kids["vaporeon"]["conditions"][0]["item"] == "water-stone"
        assert kids["jolteon"]["conditions"][0]["item"] == "thunder-stone"
        assert kids["umbreon"]["conditions"][0]["time_of_day"] == "night"


def test_evolution_single_stage(seeded):
    """无进化边时返回单节点树，前端据此展示「没有进化形态」。"""
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/pokemon/snorlax/evolution")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_nodes"] == 1
        assert len(body["roots"]) == 1
        assert body["roots"][0]["species"] == "snorlax"
        assert body["roots"][0]["children"] == []


def test_evolution_unknown_species_404(seeded):
    from app.main import app

    with TestClient(app) as client:
        assert client.get("/api/v1/pokemon/nope/evolution").status_code == 404


# ---------------------------------------------------------------- 招式图鉴
def test_moves_list_and_filters(seeded):
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/moves")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        # 默认按威力降序：tackle(40) 在 growl(NULL) 前
        assert [m["name"] for m in body["items"]] == ["tackle", "growl"]

        resp = client.get("/api/v1/moves", params={"damage_class": "status"})
        assert [m["name"] for m in resp.json()["items"]] == ["growl"]

        resp = client.get("/api/v1/moves", params={"type_name": "fire"})
        assert resp.json()["total"] == 0

        resp = client.get("/api/v1/moves", params={"sort": "name", "order": "asc"})
        assert [m["name"] for m in resp.json()["items"]] == ["growl", "tackle"]


def test_moves_batch_names(seeded):
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/moves", params={"names": "tackle, growl ,unknown"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert {m["name"] for m in body["items"]} == {"tackle", "growl"}
        # 批量模式不分页
        assert body["page"] == 1


def test_move_detail(seeded):
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/moves/tackle")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "tackle"
        assert body["power"] == 40
        assert body["accuracy"] == 100
        assert body["pp"] == 35
        assert body["priority"] == 0
        assert body["damage_class"] == "physical"
        assert body["type_name"] == "normal"
        assert body["effect_en"] == "Inflicts regular damage."
        assert body["flavor_en"] == "New flavor."
        assert body["learner_count"] == 2  # bulbasaur + ivysaur

        assert client.get("/api/v1/moves/unknown").status_code == 404


def test_move_search_by_zh_name(seeded, monkeypatch):
    """中文搜索：词典命中 slug 后再查库（词典注入受控数据，不依赖真实译名）。"""
    import json
    import tempfile
    from pathlib import Path

    from app.utils import zh_glossary

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "zh_glossary.json"
        p.write_text(json.dumps({"moves": {"tackle": "撞击"}}), encoding="utf-8")
        monkeypatch.setattr(zh_glossary, "DATA_FILE", p)
        zh_glossary.reload_glossary()
        from app.main import app

        with TestClient(app) as client:
            resp = client.get("/api/v1/moves", params={"q": "撞击"})
            assert resp.status_code == 200
            assert [m["name"] for m in resp.json()["items"]] == ["tackle"]
            resp = client.get("/api/v1/moves", params={"q": "tack"})
            assert [m["name"] for m in resp.json()["items"]] == ["tackle"]


# ---------------------------------------------------------------- 特性明细
def test_ability_detail(seeded):
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/abilities/overgrow")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "overgrow"
        assert body["effect_en"] == "Boosts grass moves at 1/3 HP."
        assert body["flavor_en"] == "Powers up grass moves."
        assert body["is_main_series"] is True
        assert body["holder_count"] == 2

        assert client.get("/api/v1/abilities/unknown").status_code == 404


def test_abilities_batch_names(seeded):
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/abilities", params={"names": "overgrow"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "overgrow"
        assert body["items"][0]["holder_count"] == 2


def test_abilities_list(seeded):
    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/abilities")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
