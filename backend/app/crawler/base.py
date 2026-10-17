"""抓取器抽象层。

BaseFetcher.fetch() 是模板方法，统一编排：
    robots 校验 → 令牌桶限速 → 并发信号量 → 指数退避重试
子类只需实现 _do_fetch()（真正发出一次请求）与资源生命周期。
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.crawler.throttle import TokenBucket

logger = logging.getLogger(__name__)


class CrawlerError(Exception):
    """爬虫基础异常。"""


class RobotsDenied(CrawlerError):
    """robots.txt 明确禁止访问。"""


class FetcherUnavailable(CrawlerError):
    """抓取器依赖缺失（如未安装 Playwright 内核）。"""


class RetryableError(CrawlerError):
    """可重试错误，可携带服务端给出的 Retry-After。"""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class FetchFailed(CrawlerError):
    """不可重试错误（如 404）。"""


@dataclass(slots=True)
class FetchRequest:
    url: str
    method: str = "GET"
    params: dict[str, Any] | None = None
    headers: dict[str, str] | None = None
    timeout: float | None = None
    respect_robots: bool = True
    wait_selector: str | None = None  # 仅 Playwright 生效
    wait_until: str = "domcontentloaded"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FetchResponse:
    url: str
    status_code: int
    headers: dict[str, str]
    text: str
    json_data: Any | None
    elapsed_ms: int
    fetcher: str
    from_cache: bool = False


async def retry_with_backoff(
    fn,
    *,
    retries: int = 5,
    base: float = 0.5,
    factor: float = 2.0,
    max_delay: float = 30.0,
    jitter: float = 0.3,
) -> Any:
    """指数退避重试。429/503 优先遵循服务端 Retry-After。"""
    last_exc: BaseException | None = None
    for attempt in range(retries + 1):
        try:
            return await fn()
        except asyncio.CancelledError:
            raise
        except RetryableError as exc:
            last_exc = exc
            if attempt >= retries:
                break
            delay = exc.retry_after or min(max_delay, base * factor**attempt)
            delay += random.uniform(0, jitter * delay)
            logger.debug("第 %s 次重试，%.2fs 后继续：%s", attempt + 1, delay, exc)
            await asyncio.sleep(delay)
        except FetchFailed:
            raise
        except Exception as exc:  # 网络类异常统一视为可重试
            last_exc = exc
            if attempt >= retries:
                break
            delay = min(max_delay, base * factor**attempt)
            delay += random.uniform(0, jitter * delay)
            logger.debug("第 %s 次重试（网络异常），%.2fs 后继续：%s", attempt + 1, delay, exc)
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc


class BaseFetcher(ABC):
    name: str = "base"

    def __init__(
        self,
        settings,
        robots=None,
        limiter: TokenBucket | None = None,
        semaphore: asyncio.Semaphore | None = None,
        retries: int = 5,
    ) -> None:
        self.settings = settings
        self.robots = robots
        self.limiter = limiter or TokenBucket(5.0, 5.0, 0.15)
        self.semaphore = semaphore or asyncio.Semaphore(6)
        self.retries = retries
        self.stats: dict[str, int] = {
            "requests": 0,
            "errors": 0,
            "retries": 0,
            "bytes": 0,
        }

    # ---------- 生命周期 ----------
    async def open(self) -> None:
        """子类按需建立连接/浏览器。"""

    async def aclose(self) -> None:
        """子类按需释放资源。"""

    async def __aenter__(self) -> BaseFetcher:
        await self.open()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.aclose()

    # ---------- 模板方法 ----------
    async def fetch(self, req: FetchRequest) -> FetchResponse:
        await self._check_robots(req)
        await self.limiter.acquire()
        started = time.perf_counter()
        async with self.semaphore:
            resp = await retry_with_backoff(
                lambda: self._do_fetch(req), retries=self.retries
            )
        resp.elapsed_ms = int((time.perf_counter() - started) * 1000)
        self.stats["requests"] += 1
        self.stats["bytes"] += len(resp.text)
        return resp

    async def fetch_json(self, url: str, **kwargs: Any) -> Any:
        resp = await self.fetch(FetchRequest(url=url, **kwargs))
        if resp.json_data is None:
            raise FetchFailed(f"响应不是合法 JSON：{url}")
        return resp.json_data

    async def fetch_text(self, url: str, **kwargs: Any) -> str:
        resp = await self.fetch(FetchRequest(url=url, **kwargs))
        return resp.text

    async def _check_robots(self, req: FetchRequest) -> None:
        if not (req.respect_robots and self.settings.respect_robots and self.robots):
            return
        allowed = await self.robots.can_fetch(req.url, self.settings.user_agent)
        if not allowed:
            raise RobotsDenied(f"robots.txt 禁止访问：{req.url}")

    @abstractmethod
    async def _do_fetch(self, req: FetchRequest) -> FetchResponse: ...
