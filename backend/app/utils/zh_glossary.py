"""特性 / 招式等多命名空间中文词典。

与 utils/zh_names.py 的分工：
- zh_names 只管「宝可梦物种译名」，且被爬虫写入路径依赖（adapter 入库时写 name_zh）
- 本模块只管「展示层翻译」，**不落库**：读取时按英文 slug 查表动态附加 zh

不入库的原因：`content_hash` 只覆盖原始 payload，不含 abilities_json，
重爬时存量记录会被判定为 skipped，把译文写进库里反而拿不到；
而 pokemon_move 有近 10 万行，加列会让每次 upsert 白白搬运静态数据。

缓存约定：整份文件共用一个 lru_cache 条目，不存在跨命名空间污染；
改完 JSON 或测试注入后需显式调用 reload_glossary()。
注意：返回的是内部缓存对象，调用方只读，禁止原地修改。
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "zh_glossary.json"
# abilities/moves：宝可梦详情展示用；后六个是 P2 物种档案的封闭枚举
# （蛋组/栖息地/体色/体型/成长率/进化触发条件），数量固定、100% 可控；
# 最后三个是 P4 进化链条件词汇（携带道具/地点/性格），前端 EvolutionChain 同源消费
NAMESPACES: tuple[str, ...] = (
    "abilities",
    "moves",
    "egg-groups",
    "habitats",
    "colors",
    "shapes",
    "growth-rates",
    "evolution-trigger",
    "evolution-items",
    "locations",
    "natures",
)


@lru_cache(maxsize=1)
def load_glossary() -> dict[str, dict[str, str]]:
    """加载全部命名空间的英->中映射。文件缺失或损坏时降级为空词典，绝不抛异常。"""
    if not DATA_FILE.exists():
        logger.warning("中文词典不存在，全部回退英文：%s", DATA_FILE)
        return {ns: {} for ns in NAMESPACES}
    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        logger.exception("中文词典解析失败，全部回退英文：%s", DATA_FILE)
        return {ns: {} for ns in NAMESPACES}
    if not isinstance(payload, dict):
        logger.error("中文词典格式非法（顶层不是对象），全部回退英文")
        return {ns: {} for ns in NAMESPACES}
    result = {ns: payload.get(ns) or {} for ns in NAMESPACES}
    extra = [k for k in payload if not k.startswith("_") and k not in NAMESPACES]
    if extra:
        logger.info("忽略词典中的未知命名空间：%s", ", ".join(extra))
    return result


def reload_glossary() -> None:
    """清空进程内缓存，用于改完 JSON 后热重载或测试注入。"""
    load_glossary.cache_clear()


def glossary_zh(namespace: str, name: str | None) -> str | None:
    """查中文名；查不到返回 None，由展示层自行回退英文（不要把英文伪装成中文）。"""
    if not name:
        return None
    return load_glossary().get(namespace, {}).get(name.lower().strip())


def ability_out(raw: Any) -> dict:
    """把 abilities_json 里的条目补齐 name_zh 输出，兼容 str / 缺字段的脏数据。"""
    if isinstance(raw, str):
        name, hidden, slot = raw, 0, 0
    elif isinstance(raw, dict):
        name = raw.get("name") or ""
        hidden = int(bool(raw.get("is_hidden")))
        slot = int(raw.get("slot") or 0)
    else:
        return {}
    if not name:
        return {}
    return {
        "name": name,
        "name_zh": glossary_zh("abilities", name),
        "is_hidden": bool(hidden),
        "slot": slot,
    }


def move_out(name: str) -> dict:
    """把招式英文 slug 转成 {name, name_zh}。"""
    return {"name": name, "name_zh": glossary_zh("moves", name)}
