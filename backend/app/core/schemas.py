"""Pydantic 请求/响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.utils.media_url import to_cdn_url


class AbilityOut(BaseModel):
    """特性条目。name 恒为英文 slug（筛选依赖它），name_zh 为展示用中文。"""

    name: str
    name_zh: str | None = None
    is_hidden: bool = False
    slot: int = 0


class MoveOut(BaseModel):
    """招式条目。moves 只在详情接口返回，列表接口恒为空以控制 payload。"""

    name: str
    name_zh: str | None = None


class PokemonOut(BaseModel):
    id: int
    name: str
    name_zh: str | None = None
    species_name: str | None = None  # 物种 slug，进化链/物种档案查询的关联键
    type_primary: str | None = None
    type_secondary: str | None = None
    types: list[str] = Field(default_factory=list)
    abilities: list[AbilityOut] = Field(default_factory=list)
    moves: list[MoveOut] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)
    stat_total: int | None = None
    height: int | None = None
    weight: int | None = None
    base_experience: int | None = None
    moves_count: int | None = None
    image_url: str | None = None
    cry_url: str | None = None
    is_default: bool = True
    updated_at: str | None = None

    @field_validator("image_url", "cry_url", mode="before")
    @classmethod
    def _cdn_media(cls, v: str | None) -> str | None:
        """读出口径统一改写：DB 存 raw 原值，API 输出 CDN 镜像（见 media_url）。"""
        return to_cdn_url(v)


class PagedPokemon(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PokemonOut]


# ---------------------------------------------------------------- P3 前端数据消费
class FilterOptionItem(BaseModel):
    """筛选项。value 为英文 slug（genus 为英文原文），label 为中文优先的展示名。"""

    value: str
    label: str
    label_en: str | None = None
    count: int = 0


class FilterOptionsOut(BaseModel):
    """图鉴分类筛选项（物种档案维度，计数为形态级 pokemon 行数）。"""

    genus: list[FilterOptionItem] = Field(default_factory=list)
    egg_groups: list[FilterOptionItem] = Field(default_factory=list)
    habitats: list[FilterOptionItem] = Field(default_factory=list)
    colors: list[FilterOptionItem] = Field(default_factory=list)
    shapes: list[FilterOptionItem] = Field(default_factory=list)
    growth_rates: list[FilterOptionItem] = Field(default_factory=list)


class EvolutionConditionOut(BaseModel):
    """一条进化边的触发条件（含 PokeAPI 多变体归并后的完整条件）。"""

    trigger: str
    trigger_zh: str | None = None
    min_level: int = 0
    item: str = ""
    time_of_day: str = ""
    variants: list[dict] = Field(default_factory=list)


class EvolutionNodeOut(BaseModel):
    """进化树节点。conditions 是从父节点进化到本节点的全部方式。"""

    species: str
    name_zh: str | None = None
    pokemon_id: int | None = None  # 代表形态（默认形态优先），供前端跳详情
    image_url: str | None = None
    conditions: list[EvolutionConditionOut] = Field(default_factory=list)
    children: list["EvolutionNodeOut"] = Field(default_factory=list)

    @field_validator("image_url", mode="before")
    @classmethod
    def _cdn_media(cls, v: str | None) -> str | None:
        return to_cdn_url(v)


class EvolutionOut(BaseModel):
    species: str
    name_zh: str | None = None
    roots: list[EvolutionNodeOut] = Field(default_factory=list)
    total_nodes: int = 0


class MoveListItemOut(BaseModel):
    """招式图鉴行。name 恒为英文 slug（筛选/跳转依赖它）。"""

    name: str
    name_zh: str | None = None
    type_name: str | None = None
    damage_class: str | None = None
    power: int | None = None
    accuracy: int | None = None
    pp: int | None = None
    priority: int | None = None


class PagedMoves(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[MoveListItemOut]


class MoveDetailOut(MoveListItemOut):
    effect_chance: int | None = None
    generation: str | None = None
    effect_en: str | None = None
    flavor_en: str | None = None
    # P4 机翻译文（zh_texts 管线，AI 翻译；缺失时界面回退英文原文）
    effect_zh: str | None = None
    flavor_zh: str | None = None
    learner_count: int = 0  # 多少只宝可梦可以学会（pokemon_move 计数）


class AbilityDetailOut(BaseModel):
    name: str
    name_zh: str | None = None
    generation: str | None = None
    is_main_series: bool = True
    effect_en: str | None = None
    flavor_en: str | None = None
    # P4 机翻译文（同上）
    effect_zh: str | None = None
    flavor_zh: str | None = None
    holder_count: int = 0  # 多少只宝可梦拥有该特性


class AbilityListItemOut(BaseModel):
    """特性图鉴行（效果长文已机翻，effect_zh 优先展示，effect_en 供原文切换）。"""

    name: str
    name_zh: str | None = None
    generation: str | None = None
    effect_en: str | None = None
    effect_zh: str | None = None
    holder_count: int = 0


class PagedAbilities(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AbilityListItemOut]


EvolutionNodeOut.model_rebuild()


class CrawlTriggerRequest(BaseModel):
    mode: str = "full"  # full | incremental | range | ids | retry_failed
    target: str = "pokemon"  # pokemon | species | evolution | move-detail | ability-detail
    fetcher: str | None = None  # httpx | playwright
    adapter: str | None = None  # pokeapi | generic_html（深度目标由 target 决定，忽略此字段）
    limit: int | None = None
    offset: int = 0
    ids: list[int] | None = None
    concurrency: int | None = None
    page_size: int | None = None
    dry_run: bool = False


class JobOut(BaseModel):
    id: int
    job_type: str
    status: str
    trigger_source: str
    fetcher: str
    adapter: str
    total: int = 0
    processed: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    progress: float = 0.0
    cursor: str | None = None
    request_count: int = 0
    message: str | None = None
    error_detail: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    created_at: str | None = None
    eta_seconds: int | None = None


class StatsEnvelope(BaseModel):
    updated_at: str
    total: int = 0
    items: list[Any] = Field(default_factory=list)


class HealthOut(BaseModel):
    status: str
    db: bool
    version: str
    active_job: int | None = None
    scheduler_running: bool = False
    frontend: bool = False
