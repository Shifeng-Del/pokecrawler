"""静态抓取器：httpx（HTTP/2 + 连接池 + 压缩）。"""

from __future__ import annotations

import logging
import time

import httpx

from app.crawler.base import (
    BaseFetcher,
    FetchFailed,
    FetchRequest,
    FetchResponse,
    RetryableError,
)
from config.settings import Settings

logger = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}


def _retry_after_seconds(resp: httpx.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None  # HTTP-date 形式较罕见，交给指数退避


class HttpxFetcher(BaseFetcher):
    name = "httpx"

    def __init__(self, settings: Settings, **kwargs) -> None:
        super().__init__(settings, **kwargs)
        self._client: httpx.AsyncClient | None = None

    async def open(self) -> None:
        if self._client is None:
            concurrency = self.semaphore._value if self.semaphore else 6
            try:
                import h2  # noqa: F401,PLC0415

                http2 = True
            except ImportError:
                http2 = False  # 未装 h2 时降级到 HTTP/1.1
            try:
                import brotli  # noqa: F401,PLC0415

                encodings = "gzip, deflate, br"
            except ImportError:
                encodings = "gzip, deflate"  # 不支持 br 就不要声明，避免拿到无法解码的内容
            self._client = httpx.AsyncClient(
                http2=http2,
                follow_redirects=True,
                timeout=httpx.Timeout(
                    self.settings.crawler_timeout,
                    connect=self.settings.crawler_connect_timeout,
                ),
                limits=httpx.Limits(
                    max_connections=max(concurrency, 1),
                    max_keepalive_connections=max(concurrency, 1),
                    keepalive_expiry=30.0,
                ),
                headers={
                    "User-Agent": self.settings.user_agent,
                    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
                    "Accept-Encoding": encodings,
                },
            )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _do_fetch(self, req: FetchRequest) -> FetchResponse:
        assert self._client is not None, "请先调用 open()"
        started = time.perf_counter()
        try:
            resp = await self._client.request(
                req.method,
                req.url,
                params=req.params,
                headers=req.headers,
                timeout=req.timeout or self.settings.crawler_timeout,
            )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            self.stats["errors"] += 1
            raise RetryableError(f"网络异常 {req.url}: {exc}") from exc

        elapsed = int((time.perf_counter() - started) * 1000)

        if resp.status_code in RETRY_STATUS:
            self.stats["errors"] += 1
            raise RetryableError(
                f"HTTP {resp.status_code} {req.url}",
                retry_after=_retry_after_seconds(resp),
            )
        if resp.status_code >= 400:
            self.stats["errors"] += 1
            raise FetchFailed(f"HTTP {resp.status_code} {req.url}")

        text = resp.text
        json_data = None
        try:
            json_data = resp.json()
        except ValueError:
            logger.debug("响应不是 JSON，保留原始文本：%s", req.url)

        return FetchResponse(
            url=str(resp.url),
            status_code=resp.status_code,
            headers=dict(resp.headers),
            text=text,
            json_data=json_data,
            elapsed_ms=elapsed,
            fetcher=self.name,
        )


__all__ = ["HttpxFetcher", "FetchRequest"]
