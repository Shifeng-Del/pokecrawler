"""robots.txt 策略：拉取、缓存、判定。

PokeAPI 的 robots.txt 没有任何 Disallow 规则，但能力必须真实存在并对外可见，
这样未来换站点时无需改代码即可合规。
"""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from config.settings import Settings

logger = logging.getLogger(__name__)


class RobotsPolicy:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, tuple[float, RobotFileParser | None]] = {}
        self._fetched_at: dict[str, str] = {}
        self._raw: dict[str, str] = {}

    def _base(self, url: str) -> str:
        parts = urlparse(url)
        return f"{parts.scheme}://{parts.netloc}"

    async def _load(self, url: str) -> RobotFileParser | None:
        base = self._base(url)
        now = time.monotonic()
        cached = self._cache.get(base)
        if cached and now - cached[0] < self.settings.robots_cache_ttl:
            return cached[1]

        robots_url = f"{base}/robots.txt"
        parser: RobotFileParser | None = None
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(
                    robots_url, headers={"User-Agent": self.settings.user_agent}
                )
            if resp.status_code == 200:
                parser = RobotFileParser()
                self._raw[base] = resp.text
                parser.parse(resp.text.splitlines())
                self._fetched_at[base] = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                )
                logger.info("已加载 robots.txt：%s", robots_url)
            else:
                logger.warning("robots.txt 不可用（HTTP %s）：%s", resp.status_code, robots_url)
        except Exception as exc:
            logger.warning("拉取 robots.txt 失败（%s）：%s", robots_url, exc)

        self._cache[base] = (now, parser)
        return parser

    async def can_fetch(self, url: str, user_agent: str) -> bool:
        parser = await self._load(url)
        if parser is None:
            # 拉取失败：allow=放行并告警，deny=严格禁止
            return self.settings.robots_on_error != "deny"
        try:
            return bool(parser.can_fetch(user_agent, url))
        except Exception as exc:
            logger.warning("robots 判定异常（%s）：%s", url, exc)
            return self.settings.robots_on_error != "deny"

    async def crawl_delay(self, url: str, user_agent: str) -> float | None:
        parser = await self._load(url)
        if parser is None:
            return None
        try:
            value = parser.crawl_delay(user_agent)
            return float(value) if value is not None else None
        except Exception:
            return None

    async def describe(self, url: str) -> dict:
        """暴露给前端/接口的 robots 状态。"""
        base = self._base(url)
        parser = await self._load(url)
        raw = self._raw.get(base, "")
        has_disallow = any(
            line.strip().lower().startswith("disallow:")
            and len(line.split(":", 1)[1].strip()) > 0
            for line in raw.splitlines()
        )
        allowed = await self.can_fetch(url, self.settings.user_agent)
        delay = await self.crawl_delay(url, self.settings.user_agent)
        rate = None
        if parser is not None:
            try:
                rate = parser.request_rate(self.settings.user_agent)
            except Exception:
                rate = None
        return {
            "user_agent": self.settings.user_agent,
            "robots_url": f"{base}/robots.txt",
            "fetched_at": self._fetched_at.get(base),
            "allowed": allowed,
            "has_disallow": has_disallow,
            "crawl_delay": delay,
            "request_rate": ({"requests": rate.requests, "seconds": rate.seconds} if rate else None),
            "effective_delay_ms": self.settings.crawler_min_interval_ms,
            "raw": raw[:4000],
        }
