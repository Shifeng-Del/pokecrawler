"""中文词典 loader 的降级、缓存与词条规范测试。"""

from __future__ import annotations

import json

import pytest

from app.utils import zh_glossary


@pytest.fixture
def tmp_glossary(tmp_path, monkeypatch):
    """把 loader 指向临时词典文件，并在用例结束后恢复缓存。"""
    path = tmp_path / "zh_glossary.json"
    monkeypatch.setattr(zh_glossary, "DATA_FILE", path)
    zh_glossary.reload_glossary()
    yield path
    monkeypatch.undo()
    zh_glossary.reload_glossary()


def test_missing_file_degrades_to_empty(tmp_glossary):
    """文件缺失时返回空词典且不抛异常，保证服务可用。"""
    data = zh_glossary.load_glossary()
    assert data == {ns: {} for ns in zh_glossary.NAMESPACES}
    assert zh_glossary.glossary_zh("abilities", "overgrow") is None


def test_broken_json_degrades_to_empty(tmp_glossary):
    """JSON 损坏同样只降级告警，不把整条查询链路打挂。"""
    tmp_glossary.write_text("{oops", encoding="utf-8")
    assert zh_glossary.load_glossary() == {ns: {} for ns in zh_glossary.NAMESPACES}


def test_non_object_payload_degrades_to_empty(tmp_glossary):
    tmp_glossary.write_text("[1, 2, 3]", encoding="utf-8")
    assert zh_glossary.load_glossary() == {ns: {} for ns in zh_glossary.NAMESPACES}


def test_unknown_namespace_ignored(tmp_glossary):
    """未知命名空间不影响已知命名空间的加载，也不出现在返回值里。"""
    tmp_glossary.write_text(
        json.dumps(
            {
                "_source": "test",
                "abilities": {"overgrow": "茂盛"},
                "moves": {"tackle": "撞击"},
                "items": {"poke-ball": "精灵球"},
            }
        ),
        encoding="utf-8",
    )
    data = zh_glossary.load_glossary()
    assert set(data) == set(zh_glossary.NAMESPACES)
    assert "items" not in data
    assert data["abilities"]["overgrow"] == "茂盛"


def test_reload_picks_up_change(tmp_glossary):
    """改完词典后 reload 能立即生效（热重载能力由 lru_cache 清理保证）。"""
    tmp_glossary.write_text(json.dumps({"abilities": {"overgrow": "茂盛"}}), encoding="utf-8")
    assert zh_glossary.glossary_zh("abilities", "overgrow") == "茂盛"

    tmp_glossary.write_text(json.dumps({"abilities": {"overgrow": "新译名"}}), encoding="utf-8")
    assert zh_glossary.glossary_zh("abilities", "overgrow") == "茂盛"  # 未 reload 前仍是旧值

    zh_glossary.reload_glossary()
    assert zh_glossary.glossary_zh("abilities", "overgrow") == "新译名"


def test_glossary_zh_normalizes_input(tmp_glossary):
    """大小写与前后空格都要能命中；查不到返回 None 而不是英文。"""
    tmp_glossary.write_text(json.dumps({"abilities": {"overgrow": "茂盛"}}), encoding="utf-8")
    zh_glossary.reload_glossary()

    assert zh_glossary.glossary_zh("abilities", "Overgrow") == "茂盛"
    assert zh_glossary.glossary_zh("abilities", "  overgrow ") == "茂盛"
    assert zh_glossary.glossary_zh("abilities", "not-exist") is None
    assert zh_glossary.glossary_zh("abilities", None) is None
    assert zh_glossary.glossary_zh("abilities", "") is None


def test_ability_out_handles_dirty_data(tmp_glossary):
    """abilities_json 里可能是 str、可能缺 slot，都要能容错。"""
    tmp_glossary.write_text(json.dumps({"abilities": {"overgrow": "茂盛"}}), encoding="utf-8")
    zh_glossary.reload_glossary()

    assert zh_glossary.ability_out("overgrow")["name_zh"] == "茂盛"
    assert zh_glossary.ability_out({"name": "overgrow"}) == {
        "name": "overgrow",
        "name_zh": "茂盛",
        "is_hidden": False,
        "slot": 0,
    }
    assert zh_glossary.ability_out({"slot": 3, "is_hidden": 1, "name": "chlorophyll"}) == {
        "name": "chlorophyll",
        "name_zh": None,
        "is_hidden": True,
        "slot": 3,
    }
    assert zh_glossary.ability_out({}) == {}
    assert zh_glossary.ability_out(12345) == {}


def test_real_glossary_file_is_well_formed():
    """仓库里的正式词典必须是合规的 slug -> 中文映射（文件不存在则跳过）。"""
    import re

    from app.utils.zh_glossary import DATA_FILE

    if not DATA_FILE.exists():
        pytest.skip("正式词典尚未生成")

    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    slug_re = re.compile(r"^[a-z0-9]+(-+[a-z0-9]+)*$")
    for ns in zh_glossary.NAMESPACES:
        entries = payload.get(ns) or {}
        assert entries, f"{ns} 命名空间为空"
        for key, value in entries.items():
            assert slug_re.match(key), f"非法 slug：{key}"
            assert value.strip() and value != key, f"无效译文：{key} -> {value}"
            assert len(value) <= 24, f"译文过长：{key} -> {value}"


def test_enum_namespaces_cover_pokeapi_values():
    """封闭枚举命名空间必须完整覆盖 PokeAPI 的实际取值（2026-10 快照）。"""
    from app.utils.zh_glossary import DATA_FILE

    if not DATA_FILE.exists():
        pytest.skip("正式词典尚未生成")
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    expected = {
        "egg-groups": 15,
        "habitats": 9,
        "colors": 10,
        "shapes": 14,
        "growth-rates": 6,
        "evolution-trigger": 18,
    }
    for ns, count in expected.items():
        entries = payload.get(ns) or {}
        assert len(entries) == count, f"{ns} 应有 {count} 条，实际 {len(entries)}"
        # 抽查每个命名空间的锚点词条
    assert payload["habitats"]["waters-edge"] == "水边"
    assert payload["egg-groups"]["humanshape"] == "人形"
    assert payload["evolution-trigger"]["use-item"] == "使用道具"
