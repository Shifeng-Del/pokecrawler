"""全局配置（pydantic-settings，支持 .env 覆盖）。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- 服务 ----
    app_name: str = "PokeCrawler"
    version: str = "1.0.0"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    # 默认关闭：开启 DEBUG 会把 aiosqlite 的每条 SQL 都打到日志里，
    # 正常运行时噪音过大，排障时再在 .env 里设 DEBUG=true。
    debug: bool = False
    api_prefix: str = "/api/v1"

    # ---- 数据库 ----
    database_url: str = Field(
        default=f"sqlite+aiosqlite:///{DATA_DIR / 'poke.db'}".replace("\\", "/")
    )
    db_echo: bool = False

    # ---- 数据源 ----
    pokeapi_base: str = "https://pokeapi.co"
    sprite_base: str = (
        "https://raw.githubusercontent.com/PokeAPI/sprites/master/"
        "sprites/pokemon/other/official-artwork"
    )

    # ---- 礼貌爬取 ----
    user_agent: str = "PokeCrawler/1.0 (+https://example.com/contact; python-httpx)"
    respect_robots: bool = True
    robots_on_error: str = "allow"  # allow | deny
    robots_cache_ttl: int = 86400

    crawler_fetcher: str = "httpx"  # httpx | playwright
    crawler_adapter: str = "pokeapi"  # pokeapi | generic_html
    crawler_parser: str = "json"  # json | css

    crawler_concurrency: int = 6
    crawler_rate_per_sec: float = 5.0
    crawler_min_interval_ms: int = 150
    crawler_timeout: float = 20.0
    crawler_connect_timeout: float = 10.0
    crawler_retries: int = 5
    crawler_page_size: int = 100

    # Playwright 更保守
    playwright_concurrency: int = 2
    playwright_rate_per_sec: float = 2.0
    playwright_min_interval_ms: int = 500
    playwright_timeout: float = 30.0

    # ---- 存储开关 ----
    store_raw_json: bool = False
    store_moves: bool = True

    # ---- 定时调度 ----
    scheduler_enabled: bool = True
    scheduler_incremental_hour: int = 3
    scheduler_full_day_of_week: str = "sun"
    scheduler_full_hour: int = 4

    # ---- 前端静态目录（构建后挂载）----
    frontend_dist: str = str(PROJECT_ROOT / "frontend" / "dist")

    @property
    def data_dir(self) -> Path:
        return DATA_DIR

    def fetcher_limits(self, fetcher: str) -> tuple[int, float, int, float]:
        """返回 (concurrency, rate_per_sec, min_interval_ms, timeout)。"""
        if fetcher == "playwright":
            return (
                self.playwright_concurrency,
                self.playwright_rate_per_sec,
                self.playwright_min_interval_ms,
                self.playwright_timeout,
            )
        return (
            self.crawler_concurrency,
            self.crawler_rate_per_sec,
            self.crawler_min_interval_ms,
            self.crawler_timeout,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
