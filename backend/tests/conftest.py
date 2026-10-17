"""测试夹具：使用独立的测试数据库。

注意：环境变量必须在导入任何 app 模块之前设置，
因为 config.settings 在模块导入时就会实例化并缓存 Settings。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_DB = BACKEND_DIR / "data" / "test.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB.as_posix()}"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["DEBUG"] = "false"
os.environ["DB_ECHO"] = "false"

from app.core.loop import setup_event_loop_policy  # noqa: E402

setup_event_loop_policy()


@pytest.fixture
async def db_session():
    """每个用例使用干净的表（共用同一个测试库文件，但清空数据）。"""
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
            # P2 深度表（无外键约束，顺序无关）
            EvolutionEdge,
            MoveDetail,
            AbilityDetail,
            PokemonSpecies,
        ):
            await session.execute(delete(table))
        await session.commit()
        yield session
    await dispose_engine()


@pytest.fixture
def bulbasaur_payload() -> dict:
    return {
        "id": 1,
        "name": "bulbasaur",
        "order": 1,
        "is_default": True,
        "base_experience": 64,
        "height": 7,
        "weight": 69,
        "species": {"name": "bulbasaur", "url": "https://pokeapi.co/api/v2/pokemon-species/1/"},
        "types": [
            {"slot": 1, "type": {"name": "grass"}},
            {"slot": 2, "type": {"name": "poison"}},
        ],
        "abilities": [
            {"slot": 1, "is_hidden": False, "ability": {"name": "overgrow"}},
            {"slot": 3, "is_hidden": True, "ability": {"name": "chlorophyll"}},
        ],
        "stats": [
            {"base_stat": 45, "stat": {"name": "hp"}},
            {"base_stat": 49, "stat": {"name": "attack"}},
            {"base_stat": 49, "stat": {"name": "defense"}},
            {"base_stat": 65, "stat": {"name": "special-attack"}},
            {"base_stat": 65, "stat": {"name": "special-defense"}},
            {"base_stat": 45, "stat": {"name": "speed"}},
        ],
        "moves": [{"move": {"name": "tackle"}}, {"move": {"name": "growl"}}],
        "sprites": {"other": {"official-artwork": {"front_default": "https://example.com/1.png"}}},
        "cries": {"latest": "https://example.com/1.ogg"},
    }
