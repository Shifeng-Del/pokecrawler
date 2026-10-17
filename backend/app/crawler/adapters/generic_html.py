"""通用 HTML 适配器：由 CSS 选择器配置驱动，换站不改代码。

配置示例见 config/selectors.example.json
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urljoin

from app.crawler.adapters.base import BaseAdapter
from app.crawler.base import BaseFetcher, FetchRequest
from app.crawler.parser import CSSSelectorParser
from config.settings import Settings

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "selectors.example.json"


class GenericHtmlAdapter(BaseAdapter):
    name = "generic_html"

    def __init__(
        self,
        fetcher: BaseFetcher,
        settings: Settings,
        config_path: str | None = None,
    ) -> None:
        super().__init__(fetcher, settings)
        self.parser = CSSSelectorParser()
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG
        self.config = self._load_config()

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            logger.warning("未找到选择器配置：%s", self.config_path)
            return {}
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    async def discover_total(self) -> int:
        """HTML 站点通常拿不到总数，退化为按配置的最大页数估算。"""
        list_cfg = self.config.get("list", {})
        start = int(list_cfg.get("start_page", 1))
        end = int(list_cfg.get("max_page", 1))
        per_page = int(list_cfg.get("per_page", 20))
        return max((end - start + 1) * per_page, 0)

    async def iter_list(
        self, page_size: int = 20, start: int = 0, stop: int | None = None
    ) -> AsyncIterator[dict]:
        list_cfg = self.config.get("list", {})
        url_tpl = list_cfg.get("url")
        if not url_tpl:
            logger.error("缺少 list.url 配置")
            return

        first_page = int(list_cfg.get("start_page", 1))
        max_page = int(list_cfg.get("max_page", 1))
        wait_selector = list_cfg.get("wait_selector")

        for page in range(first_page, max_page + 1):
            url = url_tpl.replace("{page}", str(page))
            resp = await self.fetcher.fetch(
                FetchRequest(
                    url=url, wait_selector=wait_selector, wait_until="domcontentloaded"
                )
            )
            items = self.parser.parse_list(resp.text, list_cfg)
            if not items:
                break
            for item in items:
                href = item.get("url") or ""
                if href and not href.startswith("http"):
                    item["url"] = urljoin(url, href)
                yield item

    async def fetch_detail(self, ref: dict) -> dict:
        url = ref.get("url") or self.config.get("detail", {}).get("url", "").replace(
            "{id}", str(ref.get("id", ""))
        )
        if not url:
            raise ValueError(f"条目缺少详情 URL：{ref}")
        detail_cfg = self.config.get("detail", {})
        resp = await self.fetcher.fetch(
            FetchRequest(
                url=url,
                wait_selector=detail_cfg.get("wait_selector"),
                wait_until="networkidle" if detail_cfg.get("wait_selector") else "domcontentloaded",
            )
        )
        fields = self.parser.parse_detail(resp.text, detail_cfg)
        fields.setdefault("source_url", url)
        fields["content_hash"] = str(hash(resp.text))
        fields["_raw"] = resp.text[:20000]
        return fields
