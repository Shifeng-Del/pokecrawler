"""路由依赖：查询参数解析。"""

from __future__ import annotations

from fastapi import Query

from app.core.repository import build_pokemon_query


def pokemon_filters(
    q: str | None = Query(None, description="名称模糊搜索"),
    type: list[str] | None = Query(None, description="属性筛选，可重复传，需同时满足"),
    type_any: list[str] | None = Query(None, description="属性筛选，满足任一即可"),
    ability: str | None = Query(None, description="特性名精确匹配"),
    min_total: int | None = Query(None, ge=0, description="种族值总和下限"),
    max_total: int | None = Query(None, ge=0, description="种族值总和上限"),
    min_height: int | None = Query(None, ge=0),
    max_height: int | None = Query(None, ge=0),
    min_weight: int | None = Query(None, ge=0),
    max_weight: int | None = Query(None, ge=0),
    min_exp: int | None = Query(None, ge=0),
    max_exp: int | None = Query(None, ge=0),
    is_default: bool | None = Query(None, description="是否为默认形态"),
    ids: str | None = Query(None, description="限定 id 集合，逗号分隔（如收藏筛选）"),
    # P2 物种档案筛选（值均为英文 slug；genus 为英文原文如 Seed Pokémon）
    genus: str | None = Query(None, description="物种分类，如 Seed Pokémon"),
    egg_group: str | None = Query(None, description="蛋组 slug，如 monster"),
    habitat: str | None = Query(None, description="栖息地 slug，如 grassland"),
    color: str | None = Query(None, description="体色 slug，如 green"),
    shape: str | None = Query(None, description="体型 slug，如 quadruped"),
    growth_rate: str | None = Query(None, description="成长率 slug，如 medium-slow"),
    sort: str = Query("id", description="排序字段"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
) -> dict:
    return {
        "q": q,
        "types": type,
        "type_any": type_any,
        "ability": ability,
        "min_total": min_total,
        "max_total": max_total,
        "min_height": min_height,
        "max_height": max_height,
        "min_weight": min_weight,
        "max_weight": max_weight,
        "min_exp": min_exp,
        "max_exp": max_exp,
        "is_default": is_default,
        "ids": ids,
        "genus": genus,
        "egg_group": egg_group,
        "habitat": habitat,
        "color": color,
        "shape": shape,
        "growth_rate": growth_rate,
        "sort": sort,
        "order": order,
    }


def stmt_from_filters(filters: dict):
    return build_pokemon_query(**filters)
