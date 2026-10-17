"""中文特性 / 招式在 API 与导出中的契约测试。

注意：本文件只做「并列新增」验证——英文 slug（name / ability）必须原样保留，
因为后端筛选与既有前端逻辑都依赖它。
"""

from __future__ import annotations

import asyncio
import csv
import io
import json

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_session_factory
from app.core.repository import bulk_upsert
from app.crawler.adapters.pokeapi import PokeAPIAdapter
from app.utils import zh_glossary
from config.settings import get_settings


@pytest.fixture
def stub_glossary(tmp_path, monkeypatch):
    """注入受控词典，让用例不依赖真实词典的具体译名。"""
    path = tmp_path / "zh_glossary.json"
    path.write_text(
        json.dumps(
            {
                "abilities": {"overgrow": "茂盛", "chlorophyll": "叶绿素"},
                "moves": {"tackle": "撞击", "growl": "叫声"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(zh_glossary, "DATA_FILE", path)
    zh_glossary.reload_glossary()
    yield
    monkeypatch.undo()
    zh_glossary.reload_glossary()


def seed(payload: dict) -> None:
    """在独立事件循环中预置数据，避免与 TestClient 的循环冲突。"""

    async def _run():
        from app.core.database import dispose_engine, init_db

        await init_db()
        adapter = PokeAPIAdapter(fetcher=None, settings=get_settings())
        async with get_session_factory()() as session:
            await bulk_upsert(session, [adapter.map_payload(payload)], job_id=1)
        await dispose_engine()

    asyncio.run(_run())


def test_abilities_keep_english_slug_and_gain_zh(bulbasaur_payload, stub_glossary):
    seed(bulbasaur_payload)

    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/pokemon?page_size=10")
        assert resp.status_code == 200
        item = resp.json()["items"][0]

        # 英文 slug 契约不变（筛选与旧前端都依赖它）
        assert item["abilities"][0]["name"] == "overgrow"
        assert item["abilities"][1]["name"] == "chlorophyll"
        # 新增中文
        assert item["abilities"][0]["name_zh"] == "茂盛"
        assert item["abilities"][1]["name_zh"] == "叶绿素"
        # 隐藏标记与槽位保持
        assert item["abilities"][0]["is_hidden"] is False
        assert item["abilities"][1]["is_hidden"] is True
        assert item["abilities"][1]["slot"] == 3


def test_moves_only_in_detail(bulbasaur_payload, stub_glossary):
    seed(bulbasaur_payload)

    from app.main import app

    with TestClient(app) as client:
        listing = client.get("/api/v1/pokemon?page_size=10").json()["items"][0]
        assert listing["moves"] == [], "列表接口不应返回招式明细（payload 会爆炸）"

        detail = client.get("/api/v1/pokemon/1").json()
        assert detail["moves"] == [
            {"name": "growl", "name_zh": "叫声"},
            {"name": "tackle", "name_zh": "撞击"},
        ]


def test_meta_and_stats_endpoints_have_zh(bulbasaur_payload, stub_glossary):
    seed(bulbasaur_payload)

    from app.main import app

    with TestClient(app) as client:
        meta = client.get("/api/v1/pokemon/meta/abilities").json()["abilities"]
        by_name = {a["name"]: a for a in meta}
        assert by_name["overgrow"]["name_zh"] == "茂盛"
        assert by_name["overgrow"]["count"] == 1

        # ability-top 按 count 降序，同 count 时顺序不稳定，故按 key 取值断言
        top = client.get("/api/v1/stats/ability-top?limit=5").json()["items"]
        by_ab = {i["ability"]: i for i in top}
        assert by_ab["overgrow"]["ability_zh"] == "茂盛"
        assert by_ab["chlorophyll"]["ability_zh"] == "叶绿素"


def test_csv_header_matches_values(bulbasaur_payload, stub_glossary):
    """CSV 表头与每行列数必须一致——这里同时锁住此前的「20 头 / 18 值」错位问题。"""
    seed(bulbasaur_payload)

    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/export?format=csv")
        assert resp.status_code == 200
        rows = list(csv.reader(io.StringIO(resp.text)))
        header, first = rows[0], rows[1]

        assert len(header) == len(first), f"表头 {len(header)} 列 vs 数据 {len(first)} 列"
        assert header[2] == "name_zh"
        assert "abilities_zh" in header
        assert first[2] == "妙蛙种子"
        assert first[header.index("abilities")] == "overgrow/chlorophyll"
        assert first[header.index("abilities_zh")] == "茂盛/叶绿素"


def test_json_export_has_zh(bulbasaur_payload, stub_glossary):
    seed(bulbasaur_payload)

    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/export?format=json")
        assert resp.status_code == 200
        first = json.loads(resp.text)[0]
        assert first["name_zh"] == "妙蛙种子"
        assert first["abilities"][0]["name"] == "overgrow"
        assert first["abilities"][0]["name_zh"] == "茂盛"


def test_missing_glossary_falls_back_to_english(bulbasaur_payload, tmp_path, monkeypatch):
    """词典缺失时接口必须照常可用，中文为 null，绝不报错。"""
    monkeypatch.setattr(zh_glossary, "DATA_FILE", tmp_path / "nope.json")
    zh_glossary.reload_glossary()
    try:
        seed(bulbasaur_payload)

        from app.main import app

        with TestClient(app) as client:
            item = client.get("/api/v1/pokemon?page_size=10").json()["items"][0]
            assert item["abilities"][0]["name"] == "overgrow"
            assert item["abilities"][0]["name_zh"] is None
            detail = client.get("/api/v1/pokemon/1").json()
            assert all(m["name_zh"] is None for m in detail["moves"])
    finally:
        monkeypatch.undo()
        zh_glossary.reload_glossary()
