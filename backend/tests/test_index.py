"""GET /pokemon/index 轻量索引端点测试（供前端全局搜索本地过滤）。"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient


def seed(payload: dict) -> None:
    async def _run():
        from app.core.database import dispose_engine, init_db, get_session_factory
        from app.core.repository import bulk_upsert
        from app.crawler.adapters.pokeapi import PokeAPIAdapter
        from config.settings import get_settings

        await init_db()
        adapter = PokeAPIAdapter(fetcher=None, settings=get_settings())
        async with get_session_factory()() as session:
            await bulk_upsert(session, [adapter.map_payload(payload)], job_id=1)
        await dispose_engine()

    asyncio.run(_run())


def test_index_returns_lightweight_items(bulbasaur_payload):
    seed(bulbasaur_payload)

    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/pokemon/index")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        item = body["items"][0]
        # 关键字段齐全
        assert item["id"] == 1
        assert item["name"] == "bulbasaur"
        assert item["name_zh"] == "妙蛙种子"
        assert item["type"] == "grass"
        # 轻量：不带招式/特性明细等重字段
        assert "abilities" not in item
        assert "moves" not in item


def _reset_cache() -> None:
    from app.api.v1 import pokemon as pokemon_api

    pokemon_api._index_cache.update(ts=0.0, items=None)


def test_index_is_cached_on_second_call(bulbasaur_payload):
    _reset_cache()
    seed(bulbasaur_payload)

    from app.main import app

    with TestClient(app) as client:
        first = client.get("/api/v1/pokemon/index").json()
        second = client.get("/api/v1/pokemon/index").json()
        assert first["cached"] is False
        assert second["cached"] is True
        assert first["items"] == second["items"]


def test_index_route_not_swallowed_by_dynamic_route(bulbasaur_payload):
    """/index 是静态路径，绝不能被 /{id_or_name} 动态路由吞掉（404）。"""
    seed(bulbasaur_payload)

    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/pokemon/index")
        assert resp.status_code == 200
        assert "items" in resp.json()
