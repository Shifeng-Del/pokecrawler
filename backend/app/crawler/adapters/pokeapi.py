"""PokeAPI 适配器。

列表接口负责发现 id，详情接口负责拿全字段；
从 url 解析 id 可以省掉一次请求。

P2 起同一数据源按 target 拆成五个适配器（pokemon / species / evolution /
move-detail / ability-detail），共用 `_iter_list_pages` 分页逻辑，
彼此独立、互不影响；写入侧由 pipeline 按 target 分派。
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.crawler.adapters.base import BaseAdapter
from app.crawler.base import BaseFetcher
from app.utils.hash import content_hash
from app.utils.zh_genera import genus_zh_fallback
from app.utils.zh_names import zh_name_or_none
from config.settings import Settings

logger = logging.getLogger(__name__)

STAT_KEYS = (
    "hp",
    "attack",
    "defense",
    "special-attack",
    "special-defense",
    "speed",
)


def parse_id_from_url(url: str) -> int | None:
    try:
        return int(url.rstrip("/").split("/")[-1])
    except (ValueError, IndexError):
        return None


async def _iter_list_pages(
    fetcher: BaseFetcher,
    list_url: str,
    *,
    page_size: int = 100,
    start: int = 0,
    stop: int | None = None,
    max_items: int | None = None,
) -> AsyncIterator[dict]:
    """分页遍历 PokeAPI 列表端点，产出 {id, name, url} 引用。

    start/stop 是列表偏移量（不是 id）；max_items 限制产出条数。
    注意：PokeAPI 的 id 不连续（1..1025 之后是 10001+ 形态），
    因此不能用 id 做上界判断，否则会漏掉后 300 多条形态数据。
    """
    offset = start
    yielded = 0
    while True:
        payload = await fetcher.fetch_json(
            list_url, params={"limit": page_size, "offset": offset}
        )
        results = payload.get("results") or []
        if not results:
            break
        for item in results:
            pid = parse_id_from_url(item.get("url", ""))
            if pid is None:
                continue
            yield {"id": pid, "name": item.get("name"), "url": item.get("url")}
            yielded += 1
            if max_items is not None and yielded >= max_items:
                return
        offset += page_size
        if not payload.get("next"):
            break
        if stop is not None and offset >= stop:
            break


class PokeAPIAdapter(BaseAdapter):
    name = "pokeapi"

    def __init__(self, fetcher: BaseFetcher, settings: Settings) -> None:
        super().__init__(fetcher, settings)
        self.base = settings.pokeapi_base.rstrip("/")
        self.list_url = f"{self.base}/api/v2/pokemon"
        self.detail_url = f"{self.base}/api/v2/pokemon/{{id}}/"

    async def discover_total(self) -> int:
        payload = await self.fetcher.fetch_json(
            self.list_url, params={"limit": 1, "offset": 0}
        )
        return int(payload.get("count", 0))

    async def iter_list(
        self,
        page_size: int = 100,
        start: int = 0,
        stop: int | None = None,
        max_items: int | None = None,
    ) -> AsyncIterator[dict]:
        async for ref in _iter_list_pages(
            self.fetcher,
            self.list_url,
            page_size=page_size,
            start=start,
            stop=stop,
            max_items=max_items,
        ):
            yield ref

    async def fetch_detail(self, ref: dict) -> dict:
        pid = int(ref["id"])
        url = self.detail_url.format(id=pid)
        payload = await self.fetcher.fetch_json(url)
        record = self.map_payload(payload)
        record["source_url"] = url
        return record

    def map_payload(self, p: dict) -> dict:
        types = [t["type"]["name"] for t in sorted(p.get("types", []), key=lambda x: x.get("slot", 0))]
        abilities = [
            {
                "name": a["ability"]["name"],
                "is_hidden": int(bool(a.get("is_hidden"))),
                "slot": a.get("slot", 0),
            }
            for a in sorted(p.get("abilities", []), key=lambda x: x.get("slot", 0))
        ]
        stats: dict[str, int] = {}
        for s in p.get("stats", []):
            name = (s.get("stat") or {}).get("name")
            if name:
                stats[name] = int(s.get("base_stat", 0))

        sprites = p.get("sprites") or {}
        artwork = ((sprites.get("other") or {}).get("official-artwork") or {}).get(
            "front_default"
        )
        moves = [m.get("move", {}).get("name") for m in p.get("moves", [])]
        moves = [m for m in moves if m]

        species = (p.get("species") or {}).get("name")
        return {
            "id": int(p["id"]),
            "name": p.get("name"),
            "species_name": species,
            # 中文译名是物种级的：deoxys-normal / deoxys-attack 都归到 deoxys
            "name_zh": zh_name_or_none(species or p.get("name")),
            "is_default": int(bool(p.get("is_default", True))),
            "sort_order": p.get("order"),
            "base_experience": p.get("base_experience"),
            "height": p.get("height"),
            "weight": p.get("weight"),
            "type_primary": types[0] if types else None,
            "type_secondary": types[1] if len(types) > 1 else None,
            "types_json": json.dumps(types, ensure_ascii=False),
            "abilities_json": json.dumps(abilities, ensure_ascii=False),
            "stats_json": json.dumps(stats, ensure_ascii=False),
            "stat_hp": stats.get("hp"),
            "stat_attack": stats.get("attack"),
            "stat_defense": stats.get("defense"),
            "stat_special_attack": stats.get("special-attack"),
            "stat_special_defense": stats.get("special-defense"),
            "stat_speed": stats.get("speed"),
            "stat_total": sum(stats.get(k, 0) for k in STAT_KEYS),
            "moves_count": len(moves),
            "image_url": artwork or f"{self.settings.sprite_base}/{p['id']}.png",
            "cry_url": (p.get("cries") or {}).get("latest"),
            "content_hash": content_hash(p),
            "_types": types,
            "_abilities": abilities,
            "_stats": stats,
            "_moves": moves,
            "_raw": p,
        }


# ---------------------------------------------------------------- P2 深度适配器
def _pick_en(entries: Any, field: str) -> str | None:
    """从多语言条目数组里取最后一个英文值（列表按版本组升序，取最新）。"""
    values = [
        e.get(field)
        for e in (entries or [])
        if isinstance(e, dict)
        and (e.get("language") or {}).get("name") == "en"
        and e.get(field)
    ]
    return values[-1] if values else None


class SpeciesAdapter(BaseAdapter):
    """物种档案：分类/捕获率/性别比/蛋组/栖息地/体型/成长率/世代。"""

    name = "pokeapi-species"

    def __init__(self, fetcher: BaseFetcher, settings: Settings) -> None:
        super().__init__(fetcher, settings)
        self.base = settings.pokeapi_base.rstrip("/")
        self.list_url = f"{self.base}/api/v2/pokemon-species"
        self.detail_url = f"{self.base}/api/v2/pokemon-species/{{id}}/"

    async def discover_total(self) -> int:
        payload = await self.fetcher.fetch_json(
            self.list_url, params={"limit": 1, "offset": 0}
        )
        return int(payload.get("count", 0))

    async def iter_list(
        self,
        page_size: int = 100,
        start: int = 0,
        stop: int | None = None,
        max_items: int | None = None,
    ) -> AsyncIterator[dict]:
        async for ref in _iter_list_pages(
            self.fetcher,
            self.list_url,
            page_size=page_size,
            start=start,
            stop=stop,
            max_items=max_items,
        ):
            yield ref

    async def fetch_detail(self, ref: dict) -> dict:
        url = self.detail_url.format(id=int(ref["id"]))
        payload = await self.fetcher.fetch_json(url)
        record = self.map_payload(payload)
        record["source_url"] = url
        return record

    def map_payload(self, p: dict) -> dict:
        # genera 是多语言数组；en 存原文，zh-hans 是官方简中译名（抓取时直接入库），
        # 官方缺失时再查手工补录文件，仍查不到留 None（前端回落英文，不写英文占位）
        genera = {
            (g.get("language") or {}).get("name"): g.get("genus")
            for g in (p.get("genera") or [])
            if isinstance(g, dict)
        }
        genus_en = genera.get("en")
        genus_zh = genera.get("zh-hans") or genus_zh_fallback(genus_en)

        egg_groups = [
            e.get("name") for e in (p.get("egg_groups") or []) if isinstance(e, dict) and e.get("name")
        ]
        return {
            # 物种表主键列名是 pokemon_id（与 pokemon.id 对齐但不同表），
            # 记录键必须与列名一致，否则 upsert 的键匹配全部落到 None
            "pokemon_id": int(p["id"]),
            "name": p.get("name"),
            "genus_en": genus_en,
            "genus_zh": genus_zh,
            "capture_rate": p.get("capture_rate"),
            "gender_rate": p.get("gender_rate"),
            "hatch_counter": p.get("hatch_counter"),
            "egg_groups_json": json.dumps(egg_groups, ensure_ascii=False),
            "habitat": (p.get("habitat") or {}).get("name"),
            "color": (p.get("color") or {}).get("name"),
            "shape": (p.get("shape") or {}).get("name"),
            "growth_rate": (p.get("growth_rate") or {}).get("name"),
            "is_legendary": int(bool(p.get("is_legendary"))),
            "is_mythical": int(bool(p.get("is_mythical"))),
            "generation": (p.get("generation") or {}).get("name"),
            "chain_url": (p.get("evolution_chain") or {}).get("url"),
            "content_hash": content_hash(p),
            "_raw": p,
        }


def _norm_edge(from_species: str, to_species: str, detail: dict) -> dict:
    """把一条 evolution_details 规范化为进化边行。

    主键六列全部 NOT NULL 化：min_level 0 / item "" / time_of_day "" 表示「无该条件」，
    规避 SQLite 唯一约束把 NULL 视为互异导致重复行。
    detail_json 保存该变体的完整触发条件（性别/携带/亲密度/地点等）；
    同一方法的多变体由 repository 的 evolution writer 归并成数组，这里只产单变体。
    """
    trigger = ((detail.get("trigger") or {}).get("name")) or ""
    item = ((detail.get("item") or {}).get("name")) or ""
    time_of_day = detail.get("time_of_day") or ""
    min_level = int(detail.get("min_level") or 0)

    # version_group 是版本环境噪音，不入详情快照
    conditions = {k: v for k, v in detail.items() if k != "version_group"}
    detail_json = json.dumps(conditions, ensure_ascii=False, sort_keys=True)

    return {
        "from_species": from_species,
        "to_species": to_species,
        "trigger": trigger,
        "min_level": min_level,
        "item": item,
        "time_of_day": time_of_day,
        "detail_json": detail_json,
        "content_hash": content_hash(
            {
                "from": from_species,
                "to": to_species,
                "trigger": trigger,
                "min_level": min_level,
                "item": item,
                "time_of_day": time_of_day,
                "detail": conditions,
            }
        ),
    }


def flatten_chain(chain: dict) -> list[dict]:
    """把嵌套进化链树拍平为边列表（纯函数，便于单测）。"""
    edges: list[dict] = []

    def walk(node: dict) -> None:
        from_species = (node.get("species") or {}).get("name")
        if not from_species:
            return
        for child in node.get("evolves_to") or []:
            to_species = (child.get("species") or {}).get("name")
            if not to_species:
                continue
            details = child.get("evolution_details") or [{}]
            for detail in details:
                edges.append(_norm_edge(from_species, to_species, detail))
            walk(child)

    walk(chain or {})
    return edges


class EvolutionAdapter(BaseAdapter):
    """进化链：列表发现 chain id，详情拿嵌套树，map 时拍平成边表行。

    一次抓取产出多条边（fetch_detail 返回带 `_edges` 的链级记录），
    由 repository 的 evolution writer 展开写入。
    """

    name = "pokeapi-evolution"

    def __init__(self, fetcher: BaseFetcher, settings: Settings) -> None:
        super().__init__(fetcher, settings)
        self.base = settings.pokeapi_base.rstrip("/")
        self.list_url = f"{self.base}/api/v2/evolution-chain"
        self.detail_url = f"{self.base}/api/v2/evolution-chain/{{id}}/"

    async def discover_total(self) -> int:
        payload = await self.fetcher.fetch_json(
            self.list_url, params={"limit": 1, "offset": 0}
        )
        return int(payload.get("count", 0))

    async def iter_list(
        self,
        page_size: int = 100,
        start: int = 0,
        stop: int | None = None,
        max_items: int | None = None,
    ) -> AsyncIterator[dict]:
        async for ref in _iter_list_pages(
            self.fetcher,
            self.list_url,
            page_size=page_size,
            start=start,
            stop=stop,
            max_items=max_items,
        ):
            yield ref

    async def fetch_detail(self, ref: dict) -> dict:
        url = self.detail_url.format(id=int(ref["id"]))
        payload = await self.fetcher.fetch_json(url)
        record = self.map_payload(payload)
        record["source_url"] = url
        return record

    def map_payload(self, p: dict) -> dict:
        edges = flatten_chain(p.get("chain") or {})
        return {
            "id": int(p["id"]),
            "name": f"chain-{p.get('id')}",
            "edge_count": len(edges),
            "content_hash": content_hash(p),
            "_edges": edges,
            "_raw": p,
        }


class MoveDetailAdapter(BaseAdapter):
    """招式明细：威力/命中/PP/优先级/伤害类别 + 英文效果与描述（不机翻）。"""

    name = "pokeapi-move-detail"

    def __init__(self, fetcher: BaseFetcher, settings: Settings) -> None:
        super().__init__(fetcher, settings)
        self.base = settings.pokeapi_base.rstrip("/")
        self.list_url = f"{self.base}/api/v2/move"
        self.detail_url = f"{self.base}/api/v2/move/{{id}}/"

    async def discover_total(self) -> int:
        payload = await self.fetcher.fetch_json(
            self.list_url, params={"limit": 1, "offset": 0}
        )
        return int(payload.get("count", 0))

    async def iter_list(
        self,
        page_size: int = 100,
        start: int = 0,
        stop: int | None = None,
        max_items: int | None = None,
    ) -> AsyncIterator[dict]:
        async for ref in _iter_list_pages(
            self.fetcher,
            self.list_url,
            page_size=page_size,
            start=start,
            stop=stop,
            max_items=max_items,
        ):
            yield ref

    async def fetch_detail(self, ref: dict) -> dict:
        url = self.detail_url.format(id=int(ref["id"]))
        payload = await self.fetcher.fetch_json(url)
        record = self.map_payload(payload)
        record["source_url"] = url
        return record

    def map_payload(self, p: dict) -> dict:
        effect_en = _pick_en(p.get("effect_entries"), "effect") or _pick_en(
            p.get("effect_entries"), "short_effect"
        )
        return {
            "move_name": p.get("name"),
            "power": p.get("power"),
            "accuracy": p.get("accuracy"),
            "pp": p.get("pp"),
            "priority": p.get("priority"),
            "damage_class": (p.get("damage_class") or {}).get("name"),
            "type_name": (p.get("type") or {}).get("name"),
            "effect_chance": p.get("effect_chance"),
            "effect_en": effect_en,
            "flavor_en": _pick_en(p.get("flavor_text_entries"), "flavor_text"),
            "generation": (p.get("generation") or {}).get("name"),
            "content_hash": content_hash(p),
            "_raw": p,
        }


class AbilityDetailAdapter(BaseAdapter):
    """特性明细：英文效果与描述 + 世代/主线系列标记（效果长文不机翻）。"""

    name = "pokeapi-ability-detail"

    def __init__(self, fetcher: BaseFetcher, settings: Settings) -> None:
        super().__init__(fetcher, settings)
        self.base = settings.pokeapi_base.rstrip("/")
        self.list_url = f"{self.base}/api/v2/ability"
        self.detail_url = f"{self.base}/api/v2/ability/{{id}}/"

    async def discover_total(self) -> int:
        payload = await self.fetcher.fetch_json(
            self.list_url, params={"limit": 1, "offset": 0}
        )
        return int(payload.get("count", 0))

    async def iter_list(
        self,
        page_size: int = 100,
        start: int = 0,
        stop: int | None = None,
        max_items: int | None = None,
    ) -> AsyncIterator[dict]:
        async for ref in _iter_list_pages(
            self.fetcher,
            self.list_url,
            page_size=page_size,
            start=start,
            stop=stop,
            max_items=max_items,
        ):
            yield ref

    async def fetch_detail(self, ref: dict) -> dict:
        url = self.detail_url.format(id=int(ref["id"]))
        payload = await self.fetcher.fetch_json(url)
        record = self.map_payload(payload)
        record["source_url"] = url
        return record

    def map_payload(self, p: dict) -> dict:
        effect_en = _pick_en(p.get("effect_entries"), "effect") or _pick_en(
            p.get("effect_entries"), "short_effect"
        )
        return {
            "ability_name": p.get("name"),
            "effect_en": effect_en,
            "flavor_en": _pick_en(p.get("flavor_text_entries"), "flavor_text"),
            "generation": (p.get("generation") or {}).get("name"),
            "is_main_series": int(bool(p.get("is_main_series", True))),
            "content_hash": content_hash(p),
            "_raw": p,
        }
