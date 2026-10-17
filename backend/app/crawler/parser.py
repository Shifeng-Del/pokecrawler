"""解析器：JSON 字段映射 + 通用 CSS 选择器。

两套并存的意义：换网站时只需替换配置（selectors），无需改代码。
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    name = "base"

    @abstractmethod
    def parse_list(self, payload: Any, rules: dict) -> list[dict]:
        """从列表页数据中提取条目引用（至少含 url/id）。"""

    @abstractmethod
    def parse_detail(self, payload: Any, rules: dict) -> dict:
        """从详情数据中提取字段。"""


class JsonPathParser(BaseParser):
    """JSON 解析器。

    规则形如：
        {"name": "name", "types": "types[].type.name", "hp": "stats[hp].base_stat"}
    支持：
        a.b.c            逐层取值
        a[].b            列表展开
        a[k=v].b         按字段过滤后取值
        | 默认值：路径后跟 "|0"
    """

    name = "json"

    def parse_list(self, payload: Any, rules: dict) -> list[dict]:
        items_path = rules.get("items") or "results"
        raw_items = self._get(payload, items_path) or []
        out: list[dict] = []
        for item in raw_items:
            record = {}
            for key, path in (rules.get("fields") or {}).items():
                record[key] = self._extract(item, path)
            out.append(record)
        return out

    def parse_detail(self, payload: Any, rules: dict) -> dict:
        fields = rules.get("fields") or {}
        return {key: self._extract(payload, path) for key, path in fields.items()}

    # ---------- 内部实现 ----------
    @staticmethod
    def _get(data: Any, path: str) -> Any:
        cur = data
        for token in path.split("."):
            if token.endswith("[]"):
                key = token[:-2]
                cur = cur.get(key, []) if isinstance(cur, dict) else []
            else:
                if isinstance(cur, dict):
                    cur = cur.get(token)
                else:
                    return None
            if cur is None:
                return None
        return cur

    def _extract(self, data: Any, path: str) -> Any:
        default = None
        if "|" in path:
            path, _, default_raw = path.rpartition("|")
            default = self._coerce(default_raw)
        value = self._get(data, path)
        return default if value is None else value

    @staticmethod
    def _coerce(raw: str) -> Any:
        raw = raw.strip()
        if raw in ("", "null", "None"):
            return None
        if re.fullmatch(r"-?\d+", raw):
            return int(raw)
        if re.fullmatch(r"-?\d+\.\d+", raw):
            return float(raw)
        return raw


class CSSSelectorParser(BaseParser):
    """CSS 选择器解析器（BeautifulSoup）。

    规则形如：
      {
        "item": ".product",
        "fields": {
          "name":   {"sel": ".title", "attr": "text"},
          "url":    {"sel": "a",      "attr": "href"},
          "price":  {"sel": ".price", "attr": "text", "regex": "([\\d.]+)"}
        }
      }
    """

    name = "css"

    @staticmethod
    def _soup(payload: Any):
        from bs4 import BeautifulSoup  # noqa: PLC0415

        html = payload if isinstance(payload, str) else str(payload)
        return BeautifulSoup(html, "lxml")

    def parse_list(self, payload: Any, rules: dict) -> list[dict]:
        soup = self._soup(payload)
        nodes = soup.select(rules["item"])
        fields = rules.get("fields") or {}
        out = []
        for node in nodes:
            record = {}
            for key, spec in fields.items():
                record[key] = self._pick(node, spec)
            out.append(record)
        return out

    def parse_detail(self, payload: Any, rules: dict) -> dict:
        soup = self._soup(payload)
        fields = rules.get("fields") or {}
        return {key: self._pick(soup, spec) for key, spec in fields.items()}

    def _pick(self, node, spec: dict) -> Any:
        selector = spec.get("sel")
        element = node.select_one(selector) if selector else node
        if element is None:
            return spec.get("default")

        attr = spec.get("attr", "text")
        if attr == "text":
            value = element.get_text(strip=True)
        else:
            value = element.get(attr)
            if isinstance(value, list):
                value = " ".join(value)
        if value is None:
            return spec.get("default")

        value = str(value).strip()
        regex = spec.get("regex")
        if regex:
            match = re.search(regex, value)
            if match:
                value = match.group(1) if match.groups() else match.group(0)
            else:
                return spec.get("default")

        if spec.get("type") == "int":
            try:
                return int(float(value))
            except ValueError:
                return spec.get("default")
        if spec.get("type") == "float":
            try:
                return float(value)
            except ValueError:
                return spec.get("default")
        return value


PARSER_REGISTRY: dict[str, type[BaseParser]] = {
    "json": JsonPathParser,
    "css": CSSSelectorParser,
}
