"""适配器抽象：把「某个具体数据源」的差异收敛到这一层。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from app.crawler.base import BaseFetcher
from config.settings import Settings


class BaseAdapter(ABC):
    name = "base"

    def __init__(self, fetcher: BaseFetcher, settings: Settings) -> None:
        self.fetcher = fetcher
        self.settings = settings

    @abstractmethod
    async def discover_total(self) -> int:
        """返回数据源中的条目总数。"""

    @abstractmethod
    def iter_list(
        self, page_size: int, start: int = 0, stop: int | None = None
    ) -> AsyncIterator[dict]:
        """分页遍历列表，产出条目引用。"""

    @abstractmethod
    async def fetch_detail(self, ref: dict) -> dict:
        """抓取单条详情并映射为入库字段。"""

    def iter_ids(self, ids: list[int]) -> AsyncIterator[dict]:
        """按指定 id 列表直接抓取（range / retry_failed 用）。"""

        async def _gen():
            for i in ids:
                yield {"id": i}

        return _gen()

    def map_payload(self, payload: Any) -> dict:
        raise NotImplementedError
