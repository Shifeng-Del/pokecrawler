"""物种分类（genus）中文补录查询。

数据优先级：
1. PokeAPI species payload 自带的 zh-hans 官方译名（抓取时直接写库，见 SpeciesAdapter）
2. 本文件对应的手工补录 `app/data/zh_genera.json`（官方缺失时的补充）
3. 都没有则返回 None，由展示层回退英文（绝不把英文写进中文字段）

文件格式（与 zh_glossary.json 同构，顶层键为 genera）：
    {"_source": "...", "genera": {"seed pokemon": "种子宝可梦"}}
key 用英文 genus 原文经过去重音/小写/去空格的形式，例如 "Seed Pokémon" -> "seed pokemon"。
文件不存在时视为空表，不报错。
"""
from __future__ import annotations

import json
import logging
import unicodedata
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "zh_genera.json"


def _norm(text: str) -> str:
    """归一化英文 genus：去重音（Pokémon -> pokemon）、小写、去首尾空格。

    PokeAPI 的 genus 原文带 é（Pokémon），手工补录时按去重音后的形式写 key，
    例如 "Seed Pokémon" -> "seed pokemon"。
    """
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    return ascii_only.lower().strip()


@lru_cache(maxsize=1)
def load_genera() -> dict[str, str]:
    """加载手工补录的 genus 英->中映射（进程内缓存）。文件缺失/损坏时降级为空表。"""
    if not DATA_FILE.exists():
        return {}
    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        logger.exception("zh_genera.json 解析失败，回退为空表")
        return {}
    genera = payload.get("genera") if isinstance(payload, dict) else None
    if not isinstance(genera, dict):
        return {}
    return {_norm(str(k)): v for k, v in genera.items() if isinstance(v, str) and v}


def reload_genera() -> None:
    """清空进程内缓存（改完 JSON 后热重载或测试注入用）。"""
    load_genera.cache_clear()


def genus_zh_fallback(genus_en: str | None) -> str | None:
    """官方 zh-hans 缺失时查手工补录表；查不到返回 None。"""
    if not genus_en:
        return None
    return load_genera().get(_norm(genus_en))
