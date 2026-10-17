"""聚合 /api/v1 路由。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import crawl, export, health, moves, pokemon, stats

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(pokemon.router)
api_router.include_router(stats.router)
api_router.include_router(crawl.router)
api_router.include_router(export.router)
api_router.include_router(moves.router)
api_router.include_router(moves.ability_router)
