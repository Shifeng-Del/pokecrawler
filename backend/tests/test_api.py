"""API 冒烟测试。"""

import asyncio
import json

from fastapi.testclient import TestClient

from app.core.database import get_session_factory
from app.core.repository import bulk_upsert
from app.crawler.adapters.pokeapi import PokeAPIAdapter
from config.settings import get_settings


def seed(payload: dict) -> None:
    """在独立事件循环中预置数据，结束后释放引擎，避免与 TestClient 的循环冲突。"""

    async def _run():
        from app.core.database import dispose_engine, init_db

        await init_db()
        adapter = PokeAPIAdapter(fetcher=None, settings=get_settings())
        async with get_session_factory()() as session:
            await bulk_upsert(session, [adapter.map_payload(payload)], job_id=1)
        await dispose_engine()

    asyncio.run(_run())


def test_health_and_endpoints(bulbasaur_payload):
    seed(bulbasaur_payload)

    from app.main import app

    with TestClient(app) as client:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["db"] is True

        resp = client.get("/api/v1/pokemon?page_size=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["name"] == "bulbasaur"
        assert body["items"][0]["stat_total"] == 318

        resp = client.get("/api/v1/pokemon/1")
        assert resp.status_code == 200
        assert resp.json()["types"] == ["grass", "poison"]

        resp = client.get("/api/v1/pokemon/bulbasaur")
        assert resp.status_code == 200

        resp = client.get("/api/v1/pokemon/99999")
        assert resp.status_code == 404

        resp = client.get("/api/v1/pokemon?type=fire")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

        resp = client.get("/api/v1/stats/overview")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = client.get("/api/v1/stats/type-distribution")
        assert resp.status_code == 200
        assert any(i["type"] == "grass" for i in resp.json()["items"])

        resp = client.get("/api/v1/stats/ranking?metric=stat_total&limit=5")
        assert resp.status_code == 200
        assert resp.json()["items"][0]["value"] == 318

        resp = client.get("/api/v1/stats/radar?ids=1")
        assert resp.status_code == 200
        assert resp.json()["items"][0]["stats"]["hp"] == 45

        resp = client.get("/api/v1/crawl/jobs")
        assert resp.status_code == 200

        resp = client.get("/api/v1/crawl/fetchers")
        assert resp.status_code == 200
        assert "httpx" in resp.json()["available"]

        resp = client.get("/api/v1/export?format=csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "bulbasaur" in resp.text

        resp = client.get("/api/v1/export?format=json")
        assert resp.status_code == 200
        assert json.loads(resp.text)[0]["name"] == "bulbasaur"

        # 参数校验失败应返回 422
        resp = client.get("/api/v1/pokemon?order=bad")
        assert resp.status_code == 422
