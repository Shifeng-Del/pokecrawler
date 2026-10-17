"""动态抓取器：Playwright 无头 Chromium。

要点：
- 复用 Browser/Context，Page 短生命周期
- aclose() 必须逐级关闭，否则 Windows 会残留 chromium 进程
- 未安装内核时抛出友好异常，不阻断 httpx 模式
"""

from __future__ import annotations

import logging
import time

import asyncio

from app.crawler.base import (
    BaseFetcher,
    FetchFailed,
    FetcherUnavailable,
    FetchRequest,
    FetchResponse,
    RetryableError,
)

logger = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}

# 关闭单步的超时上限（秒）。
CONTEXT_CLOSE_TIMEOUT = 10.0
DRIVER_STOP_TIMEOUT = 60.0


class PlaywrightFetcher(BaseFetcher):
    name = "playwright"

    def __init__(self, settings, **kwargs) -> None:
        super().__init__(settings, **kwargs)
        self._pw = None
        self._browser = None
        self._context = None

    async def open(self) -> None:
        try:
            from playwright.async_api import async_playwright  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise FetcherUnavailable(
                "未安装 playwright，请先执行：pip install playwright && "
                "python -m playwright install chromium"
            ) from exc

        self._pw = await async_playwright().start()
        try:
            self._browser = await self._pw.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
            )
        except Exception as exc:  # 内核未下载
            await self._pw.stop()
            self._pw = None
            raise FetcherUnavailable(
                f"Chromium 启动失败，请先执行 python -m playwright install chromium（{exc}）"
            ) from exc

        self._context = await self._browser.new_context(
            user_agent=self.settings.user_agent,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            java_script_enabled=True,
        )
        logger.info("Playwright 无头浏览器已启动")

    async def _close_safely(self, what: str, coro, timeout: float) -> None:
        """单步关闭，超时则放弃并继续。"""
        try:
            await asyncio.wait_for(coro, timeout)
        except asyncio.TimeoutError:
            logger.warning("关闭 %s 超时（%ss），跳过并继续", what, timeout)
        except Exception as exc:  # noqa: BLE001
            logger.warning("关闭 %s 出错：%s", what, exc)

    async def aclose(self) -> None:
        if self._context is not None:
            await self._close_safely("浏览器上下文", self._context.close(), CONTEXT_CLOSE_TIMEOUT)
            self._context = None

        # 这里**故意不调用** browser.close()。
        # 实测（Windows + Proactor）：只要页面导航过，browser.close() 就会无限等待
        # —— 单独 launch 关闭仅 1.7s、加了 context 也只要 2.0s，但一旦 page.goto 过
        # 就 >60s 不返回，且与启动参数无关（试过 --disable-background-networking 等
        # 9 个降噪参数均无效）。
        # 而 pw.stop() 会连带终止 driver 自己拉起的浏览器进程：实测约 32s 返回，
        # 进程数 3 → 0，干净回收。因此收尾直接交给 driver。
        self._browser = None

        if self._pw is not None:
            await self._close_safely("Playwright 驱动", self._pw.stop(), DRIVER_STOP_TIMEOUT)
            self._pw = None

    async def _do_fetch(self, req: FetchRequest) -> FetchResponse:
        if self._context is None:
            await self.open()
        assert self._context is not None

        timeout_ms = int((req.timeout or self.settings.playwright_timeout) * 1000)
        started = time.perf_counter()
        page = await self._context.new_page()
        try:
            resp = await page.goto(
                req.url, wait_until=req.wait_until, timeout=timeout_ms
            )
            if req.wait_selector:
                await page.wait_for_selector(req.wait_selector, timeout=timeout_ms)
            content = await page.content()
            status = resp.status if resp else 0
            headers = dict(resp.headers) if resp else {}
            json_data = None
            if resp is not None and "json" in (headers.get("content-type") or ""):
                try:
                    json_data = await resp.json()
                except Exception:
                    json_data = None
            if json_data is None and "json" in (headers.get("content-type") or ""):
                # 兜底：直接从页面文本解析
                import json  # noqa: PLC0415

                try:
                    json_data = json.loads(await page.inner_text("pre") or content)
                except Exception:
                    json_data = None
        except Exception as exc:  # 超时/导航失败
            self.stats["errors"] += 1
            raise RetryableError(f"Playwright 抓取失败 {req.url}: {exc}") from exc
        finally:
            await page.close()

        elapsed = int((time.perf_counter() - started) * 1000)

        if status in RETRY_STATUS:
            self.stats["errors"] += 1
            raise RetryableError(f"HTTP {status} {req.url}")
        if status >= 400:
            self.stats["errors"] += 1
            raise FetchFailed(f"HTTP {status} {req.url}")

        return FetchResponse(
            url=req.url,
            status_code=status,
            headers=headers,
            text=content,
            json_data=json_data,
            elapsed_ms=elapsed,
            fetcher=self.name,
        )
