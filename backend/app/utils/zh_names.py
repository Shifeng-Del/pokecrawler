"""宝可梦简体中文译名查询。

数据源为随仓库提交的离线映射 `app/data/zh_names.json`（由
`scripts/fetch_zh_names.py` 从 Wikidata 生成）。离线化是为了让运行期不再依赖外网，
也避免每次请求都去做一次 SPARQL 查询。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "zh_names.json"


@lru_cache(maxsize=1)
def load_zh_names() -> dict[str, str]:
    """加载英文 slug -> 简体中文的映射（进程内缓存）。"""
    if not DATA_FILE.exists():
        return {}
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return payload.get("pokemon", {})


def to_chinese(name: str | None, *, fallback: str | None = None) -> str | None:
    """把 PokeAPI 的英文 slug 转成简体中文名。

    查不到时返回 fallback（默认原英文名），保证展示层永远不出现空值。
    """
    if not name:
        return None
    mapping = load_zh_names()
    return mapping.get(name.lower().strip(), fallback if fallback is not None else name)


def zh_name_or_none(name: str | None) -> str | None:
    """查不到返回 None（用于入库，避免把英文写进中文字段）。"""
    if not name:
        return None
    return load_zh_names().get(name.lower().strip())
