"""P2 深度适配器：species / evolution / move-detail / ability-detail 的映射与分页。"""

from __future__ import annotations

import json

import pytest

from app.crawler.adapters.pokeapi import (
    AbilityDetailAdapter,
    EvolutionAdapter,
    MoveDetailAdapter,
    SpeciesAdapter,
    flatten_chain,
)
from app.utils.zh_genera import genus_zh_fallback
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
            {"genus": "たねポケモン", "language": {"name": "ja"}},
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
        # 数组顺序故意把非英文放前面，验证按语言过滤
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
def overgrow_payload() -> dict:
    return {
        "id": 1,
        "name": "overgrow",
        "is_main_series": True,
        "generation": {"name": "generation-iii"},
        "effect_entries": [
            {"effect": "Buffs moves.", "language": {"name": "en"}},
            {"effect": "法文效果", "language": {"name": "fr"}},
        ],
        "flavor_text_entries": [
            {"flavor_text": "Boosts GRASS moves.", "language": {"name": "en"}},
        ],
    }


class _FakeFetcher:
    """最小假 fetcher：按 URL（+排序后的 query）返回预置 payload，记录请求。"""

    def __init__(self, routes: dict[str, dict]):
        self.routes = routes
        self.stats = {"requests": 0}
        self.calls: list[tuple[str, dict | None]] = []

    def _key(self, url: str, params: dict | None) -> str:
        if not params:
            return url
        qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{url}?{qs}"

    async def fetch_json(self, url: str, params: dict | None = None) -> dict:
        self.stats["requests"] += 1
        self.calls.append((url, params))
        key = self._key(url, params)
        if key not in self.routes:
            raise AssertionError(f"未预置的路由：{key}")
        return self.routes[key]


# ---------------------------------------------------------------- species
def test_species_map_payload(bulbasaur_species_payload):
    adapter = SpeciesAdapter(fetcher=None, settings=get_settings())
    record = adapter.map_payload(bulbasaur_species_payload)

    assert record["pokemon_id"] == 1
    assert record["name"] == "bulbasaur"
    # genus 双列：英文原文 + 官方简中（抓取时直接入库，不依赖机翻）
    assert record["genus_en"] == "Seed Pokémon"
    assert record["genus_zh"] == "种子宝可梦"
    assert record["capture_rate"] == 45
    assert record["gender_rate"] == 1  # 八分之一为雌
    assert record["hatch_counter"] == 20
    assert json.loads(record["egg_groups_json"]) == ["monster", "plant"]
    assert record["habitat"] == "grassland"
    assert record["color"] == "green"
    assert record["shape"] == "quadruped"
    assert record["growth_rate"] == "medium-slow"
    assert record["is_legendary"] == 0
    assert record["is_mythical"] == 0
    assert record["generation"] == "generation-i"
    assert record["chain_url"].endswith("/evolution-chain/1/")
    assert record["content_hash"]


def test_species_genus_zh_missing_returns_none(bulbasaur_species_payload):
    """官方 zh-hans 缺失且无手工补录时，genus_zh 必须是 None（不写英文占位）。"""
    payload = dict(bulbasaur_species_payload)
    payload["genera"] = [{"genus": "Seed Pokémon", "language": {"name": "en"}}]
    adapter = SpeciesAdapter(fetcher=None, settings=get_settings())
    record = adapter.map_payload(payload)
    assert record["genus_en"] == "Seed Pokémon"
    assert record["genus_zh"] is None


def test_genus_zh_fallback_reads_manual_file(tmp_path, monkeypatch):
    """官方缺失时回退到手工补录文件；文件不存在视为空表。"""
    from app.utils import zh_genera

    monkeypatch.setattr(zh_genera, "DATA_FILE", tmp_path / "missing.json")
    zh_genera.reload_genera()
    assert genus_zh_fallback("Seed Pokémon") is None

    (tmp_path / "zh_genera.json").write_text(
        json.dumps({"genera": {"seed pokemon": "种子宝可梦"}}), encoding="utf-8"
    )
    monkeypatch.setattr(zh_genera, "DATA_FILE", tmp_path / "zh_genera.json")
    zh_genera.reload_genera()
    assert genus_zh_fallback("Seed Pokémon") == "种子宝可梦"
    assert genus_zh_fallback("不存在") is None
    assert genus_zh_fallback(None) is None


# ---------------------------------------------------------------- evolution
def test_flatten_chain_produces_edges(bulbasaur_chain_payload):
    edges = flatten_chain(bulbasaur_chain_payload["chain"])
    assert len(edges) == 2

    first, second = edges
    assert (first["from_species"], first["to_species"]) == ("bulbasaur", "ivysaur")
    assert first["trigger"] == "level-up"
    assert first["min_level"] == 16
    assert (second["from_species"], second["to_species"]) == ("ivysaur", "venusaur")
    assert second["min_level"] == 32

    # 主键列 NOT NULL 化：无条件字段规范为 0 / ""
    assert first["item"] == ""
    assert first["time_of_day"] == ""
    # detail_json 是单变体条件（多变体归并在 writer 层）
    conditions = json.loads(first["detail_json"])
    assert conditions["trigger"]["name"] == "level-up"
    assert conditions["needs_overworld_rain"] is False
    # 每条边带独立内容哈希
    assert first["content_hash"] and first["content_hash"] != second["content_hash"]


def test_flatten_chain_handles_branching_and_missing_fields():
    """分支链（一拳->三个进化）与缺字段节点都不能炸。"""
    chain = {
        "species": {"name": "tyrogue"},
        "evolves_to": [
            {
                "species": {"name": "hitmonlee"},
                "evolution_details": [{"trigger": {"name": "level-up"}, "min_level": 20}],
            },
            {
                "species": {"name": "hitmonchan"},
                "evolution_details": [{"trigger": {"name": "level-up"}, "min_level": 20}],
            },
            {
                "species": {"name": "hitmontop"},
                # 缺 evolution_details：按一条无条件边处理
                "evolves_to": [],
            },
            {"species": None, "evolution_details": [{}]},  # 脏数据：无 species
        ],
    }
    edges = flatten_chain(chain)
    assert len(edges) == 3
    assert [e["to_species"] for e in edges] == ["hitmonlee", "hitmonchan", "hitmontop"]
    assert edges[2]["min_level"] == 0  # 缺 details -> 规范化默认值


def test_evolution_map_payload_wraps_edges(bulbasaur_chain_payload):
    adapter = EvolutionAdapter(fetcher=None, settings=get_settings())
    record = adapter.map_payload(bulbasaur_chain_payload)
    assert record["id"] == 1
    assert record["name"] == "chain-1"
    assert record["edge_count"] == 2
    assert len(record["_edges"]) == 2


# ---------------------------------------------------------------- move / ability
def test_move_detail_map_payload(tackle_payload):
    adapter = MoveDetailAdapter(fetcher=None, settings=get_settings())
    record = adapter.map_payload(tackle_payload)

    assert record["move_name"] == "tackle"
    assert record["power"] == 40
    assert record["accuracy"] == 100
    assert record["pp"] == 35
    assert record["priority"] == 0
    assert record["damage_class"] == "physical"
    assert record["type_name"] == "normal"
    assert record["generation"] == "generation-i"
    # 效果长文只取英文、不机翻
    assert record["effect_en"] == "Inflicts regular damage."
    # 描述取最后一个英文版本（最新）
    assert record["flavor_en"] == "New flavor."
    assert record["content_hash"]


def test_ability_detail_map_payload(overgrow_payload):
    adapter = AbilityDetailAdapter(fetcher=None, settings=get_settings())
    record = adapter.map_payload(overgrow_payload)

    assert record["ability_name"] == "overgrow"
    assert record["effect_en"] == "Buffs moves."
    assert record["flavor_en"] == "Boosts GRASS moves."
    assert record["generation"] == "generation-iii"
    assert record["is_main_series"] == 1


# ---------------------------------------------------------------- 分页装配
async def test_species_adapter_pagination_and_detail(bulbasaur_species_payload):
    """假 fetcher 端到端：discover_total -> iter_list 分页 -> fetch_detail 映射。"""
    base = "https://pokeapi.co"
    page1 = {
        "count": 3,
        "next": f"{base}/api/v2/pokemon-species?limit=2&offset=2",
        "results": [
            {"name": "bulbasaur", "url": f"{base}/api/v2/pokemon-species/1/"},
            {"name": "ivysaur", "url": f"{base}/api/v2/pokemon-species/2/"},
        ],
    }
    page2 = {
        "count": 3,
        "next": None,
        "results": [
            {"name": "venusaur", "url": f"{base}/api/v2/pokemon-species/3/"},
        ],
    }
    routes = {
        f"{base}/api/v2/pokemon-species?limit=1&offset=0": {
            "count": 3,
            "next": None,
            "results": [],
        },
        f"{base}/api/v2/pokemon-species?limit=2&offset=0": page1,
        f"{base}/api/v2/pokemon-species?limit=2&offset=2": page2,
        f"{base}/api/v2/pokemon-species/1/": bulbasaur_species_payload,
    }
    fetcher = _FakeFetcher(routes)
    adapter = SpeciesAdapter(fetcher=fetcher, settings=get_settings())

    assert await adapter.discover_total() == 3

    refs = [ref async for ref in adapter.iter_list(page_size=2)]
    assert [r["id"] for r in refs] == [1, 2, 3]
    assert [r["name"] for r in refs] == ["bulbasaur", "ivysaur", "venusaur"]

    # max_items 截断
    refs_limited = [ref async for ref in adapter.iter_list(page_size=2, max_items=2)]
    assert len(refs_limited) == 2

    record = await adapter.fetch_detail({"id": 1})
    assert record["genus_zh"] == "种子宝可梦"
    assert record["source_url"].endswith("/pokemon-species/1/")
    # 1(count) + 2(完整分页) + 1(max_items 截断只取第一页) + 1(详情)
    assert fetcher.stats["requests"] == 5


async def test_evolution_adapter_detail_flattening(bulbasaur_chain_payload):
    base = "https://pokeapi.co"
    fetcher = _FakeFetcher(
        {
            f"{base}/api/v2/evolution-chain?limit=1&offset=0": {
                "count": 540,
                "next": None,
                "results": [],
            },
            f"{base}/api/v2/evolution-chain/1/": bulbasaur_chain_payload,
        }
    )
    adapter = EvolutionAdapter(fetcher=fetcher, settings=get_settings())
    assert await adapter.discover_total() == 540

    record = await adapter.fetch_detail({"id": 1})
    assert record["edge_count"] == 2
    assert record["_edges"][0]["from_species"] == "bulbasaur"
