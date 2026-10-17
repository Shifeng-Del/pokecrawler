import json

from app.crawler.adapters.pokeapi import PokeAPIAdapter, parse_id_from_url
from config.settings import get_settings


def test_parse_id_from_url():
    assert parse_id_from_url("https://pokeapi.co/api/v2/pokemon/25/") == 25
    assert parse_id_from_url("https://pokeapi.co/api/v2/pokemon/1") == 1
    assert parse_id_from_url("not-a-url") is None


def test_map_payload_matches_known_values(bulbasaur_payload):
    adapter = PokeAPIAdapter(fetcher=None, settings=get_settings())
    record = adapter.map_payload(bulbasaur_payload)

    assert record["id"] == 1
    assert record["name"] == "bulbasaur"
    assert record["height"] == 7
    assert record["weight"] == 69
    assert record["base_experience"] == 64
    assert record["type_primary"] == "grass"
    assert record["type_secondary"] == "poison"
    assert json.loads(record["types_json"]) == ["grass", "poison"]
    assert record["stat_hp"] == 45
    assert record["stat_attack"] == 49
    assert record["stat_defense"] == 49
    assert record["stat_special_attack"] == 65
    assert record["stat_special_defense"] == 65
    assert record["stat_speed"] == 45
    assert record["stat_total"] == 318  # 关键校验锚点
    assert record["moves_count"] == 2
    assert record["image_url"] == "https://example.com/1.png"
    assert record["cry_url"] == "https://example.com/1.ogg"
    assert record["content_hash"]

    abilities = json.loads(record["abilities_json"])
    assert abilities[0]["name"] == "overgrow"
    assert abilities[0]["is_hidden"] == 0
    assert abilities[1]["name"] == "chlorophyll"
    assert abilities[1]["is_hidden"] == 1


def test_map_payload_is_hash_stable(bulbasaur_payload):
    adapter = PokeAPIAdapter(fetcher=None, settings=get_settings())
    a = adapter.map_payload(bulbasaur_payload)["content_hash"]
    b = adapter.map_payload(bulbasaur_payload)["content_hash"]
    assert a == b

    changed = dict(bulbasaur_payload)
    changed["base_experience"] = 65
    assert adapter.map_payload(changed)["content_hash"] != a
