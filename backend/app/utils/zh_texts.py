"""招式/特性英文长文案的中文译文（zh_texts 管线运行时侧）。

与 utils/zh_glossary.py 的分工：
- glossary 管「短名」（招式名/特性名/封闭枚举），本模块管「长文」（效果说明/图鉴描述）
- 同样**不落库**：move_detail/ability_detail 的 content_hash 只覆盖上游 payload，
  重爬时存量记录判 skipped，译文入库反而拿不到；静态 JSON 随仓库提交最稳
- 文件由 scripts/zh_texts_merge.py 从 app/data/zh_texts/zh/ 分批译文合并产出，
  术语表见同目录 TERMS.md

缓存约定：两个文件各一个 lru_cache 条目；改完 JSON 或测试注入后需显式 reload_texts()。
返回内部缓存对象，调用方只读，禁止原地修改。
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "zh_texts"
MOVE_FILE = DATA_DIR / "move_texts.json"
ABILITY_FILE = DATA_DIR / "ability_texts.json"


@lru_cache(maxsize=2)
def _load(path: Path) -> dict[str, dict[str, str]]:
    """加载一个译文文件；缺失或损坏时降级为空表（界面回落英文），绝不抛异常。"""
    if not path.exists():
        logger.warning("译文文件不存在，全部回退英文：%s", path)
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        logger.exception("译文文件解析失败，全部回退英文：%s", path)
        return {}
    if not isinstance(payload, dict):
        logger.error("译文文件格式非法（顶层不是对象）：%s", path)
        return {}
    return payload.get("items") or {}


def reload_texts() -> None:
    """清空进程内缓存，用于改完 JSON 后热重载或测试注入。"""
    _load.cache_clear()


def _text(table: dict[str, dict[str, str]], name: str | None, field: str) -> str | None:
    if not name:
        return None
    entry = table.get(name.lower().strip())
    if not entry:
        return None
    v = entry.get(field)
    return v if isinstance(v, str) and v.strip() else None


def move_text_zh(name: str | None) -> dict[str, str | None]:
    """招式长文译文：{"effect": zh|None, "flavor": zh|None}。"""
    table = _load(MOVE_FILE)
    return {
        "effect": _text(table, name, "effect"),
        "flavor": _text(table, name, "flavor"),
    }


def ability_text_zh(name: str | None) -> dict[str, str | None]:
    """特性长文译文：{"effect": zh|None, "flavor": zh|None}。"""
    table = _load(ABILITY_FILE)
    return {
        "effect": _text(table, name, "effect"),
        "flavor": _text(table, name, "flavor"),
    }


def out_pair(en: Any, zh: str | None) -> dict[str, Any]:
    """效果/描述的标准输出对：中文优先、英文兜底、都有则都给（前端做原文切换）。"""
    return {"zh": zh, "en": en if isinstance(en, str) and en.strip() else None}
