"""SQLAlchemy ORM 模型。

设计要点：
- pokemon 主键直接采用 PokeAPI 的 id，便于幂等 upsert
- 多值字段（属性/特性/种族值）双写：主表 JSON 列供展示与导出，子表供筛选与聚合
- order 是 SQL 保留字，改名 sort_order
- SQLite 无 bool，统一存 0/1
- P2 深度表（species/evolution_edge/move_detail/ability_detail）由 create_all 自动建表，
  不涉及老库 ALTER； EvolutionaryEdge 用复合主键 + 全列 NOT NULL 化（0/"" 表示「无」），
  规避 SQLite 唯一约束把 NULL 视为互异导致的行重复
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Pokemon(Base):
    __tablename__ = "pokemon"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # 简体中文官方译名（物种级，同一物种的所有形态共享一个译名）
    name_zh: Mapped[str | None] = mapped_column(String(64))
    species_name: Mapped[str | None] = mapped_column(String(64))
    is_default: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int | None] = mapped_column(Integer)

    base_experience: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)  # dm
    weight: Mapped[int | None] = mapped_column(Integer)  # hg

    type_primary: Mapped[str | None] = mapped_column(String(32))
    type_secondary: Mapped[str | None] = mapped_column(String(32))
    types_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    abilities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    stats_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    stat_hp: Mapped[int | None] = mapped_column(Integer)
    stat_attack: Mapped[int | None] = mapped_column(Integer)
    stat_defense: Mapped[int | None] = mapped_column(Integer)
    stat_special_attack: Mapped[int | None] = mapped_column(Integer)
    stat_special_defense: Mapped[int | None] = mapped_column(Integer)
    stat_speed: Mapped[int | None] = mapped_column(Integer)
    stat_total: Mapped[int | None] = mapped_column(Integer)

    moves_count: Mapped[int | None] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(Text)
    cry_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)

    content_hash: Mapped[str | None] = mapped_column(String(40))
    raw_json: Mapped[str | None] = mapped_column(Text)
    crawl_job_id: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        Index("ux_pokemon_name", "name", unique=True),
        Index("ix_pokemon_type_primary", "type_primary"),
        Index("ix_pokemon_type_secondary", "type_secondary"),
        Index("ix_pokemon_stat_total", "stat_total"),
        Index("ix_pokemon_base_exp", "base_experience"),
        Index("ix_pokemon_height", "height"),
        Index("ix_pokemon_weight", "weight"),
        Index("ix_pokemon_updated", "updated_at"),
    )


class PokemonType(Base):
    __tablename__ = "pokemon_type"

    pokemon_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    type_name: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (Index("ix_ptype_name", "type_name"),)


class PokemonAbility(Base):
    __tablename__ = "pokemon_ability"

    pokemon_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    ability_name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_hidden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (Index("ix_pability_name", "ability_name"),)


class PokemonStat(Base):
    __tablename__ = "pokemon_stat"

    pokemon_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stat_name: Mapped[str] = mapped_column(String(32), primary_key=True)
    base_stat: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (Index("ix_pstat_name", "stat_name"),)


class PokemonMove(Base):
    __tablename__ = "pokemon_move"

    pokemon_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    move_name: Mapped[str] = mapped_column(String(64), primary_key=True)

    __table_args__ = (Index("ix_pmove_name", "move_name"),)


class CrawlJob(Base):
    __tablename__ = "crawl_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_source: Mapped[str] = mapped_column(String(32), nullable=False, default="api")
    fetcher: Mapped[str] = mapped_column(String(32), nullable=False, default="httpx")
    adapter: Mapped[str] = mapped_column(String(32), nullable=False, default="pokeapi")

    params_json: Mapped[str | None] = mapped_column(Text)

    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cursor: Mapped[str | None] = mapped_column(String(64))
    concurrency: Mapped[int | None] = mapped_column(Integer)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    message: Mapped[str | None] = mapped_column(Text)
    error_detail: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[str | None] = mapped_column(String(32))
    finished_at: Mapped[str | None] = mapped_column(String(32))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (Index("ix_job_status_started", "status", "started_at"),)


class CrawlError(Base):
    __tablename__ = "crawl_error"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int | None] = mapped_column(Integer)
    target: Mapped[str | None] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (Index("ix_cerr_job", "job_id"),)


# ---------------------------------------------------------------- P2 深度表
class PokemonSpecies(Base):
    """物种档案：分类、捕获率、性别比、蛋组、栖息地、世代等。

    与 pokemon 主表的分工：pokemon 是「形态级」（含 300+ 地区/ Mega 形态），
    本表是「物种级」（1025 条），genus/蛋组/栖息地都只属于物种。
    genus_zh 直接取 PokeAPI 官方的 zh-hans 译名（抓取时写入），
    缺失时回落 zh_genera.json 手工补录，再缺则留空由前端回退英文。
    """

    __tablename__ = "pokemon_species"

    pokemon_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str | None] = mapped_column(String(64))  # 物种 slug，与 pokemon.species_name 对齐
    genus_en: Mapped[str | None] = mapped_column(String(64))
    genus_zh: Mapped[str | None] = mapped_column(String(64))

    capture_rate: Mapped[int | None] = mapped_column(Integer)
    gender_rate: Mapped[int | None] = mapped_column(Integer)  # -1 无性别；否则 0..8（八分之一为雌）
    hatch_counter: Mapped[int | None] = mapped_column(Integer)
    egg_groups_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    habitat: Mapped[str | None] = mapped_column(String(32))
    color: Mapped[str | None] = mapped_column(String(32))
    shape: Mapped[str | None] = mapped_column(String(32))
    growth_rate: Mapped[str | None] = mapped_column(String(32))

    is_legendary: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_mythical: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation: Mapped[str | None] = mapped_column(String(16))  # 如 generation-i
    chain_url: Mapped[str | None] = mapped_column(Text)

    content_hash: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        Index("ix_species_habitat", "habitat"),
        Index("ix_species_color", "color"),
        Index("ix_species_shape", "shape"),
        Index("ix_species_growth", "growth_rate"),
        Index("ix_species_generation", "generation"),
        Index("ix_species_legendary", "is_legendary"),
    )


class EvolutionEdge(Base):
    """进化边（扁平表，前端按 from/to 自行组装树）。

    六列复合主键全部 NOT NULL 化：min_level 0 / item "" / time_of_day ""
    表示「无该条件」，规避 SQLite 唯一约束中 NULL 互异导致的重复行。
    detail_json 保存该进化方法的全部触发条件变体（JSON 数组，排序稳定），
    供展示层做悬浮说明；PokeAPI 会把同一方法按地点等列多个变体，由 writer 归并。
    """

    __tablename__ = "evolution_edge"

    from_species: Mapped[str] = mapped_column(String(64), primary_key=True)
    to_species: Mapped[str] = mapped_column(String(64), primary_key=True)
    trigger: Mapped[str] = mapped_column(String(32), primary_key=True)
    min_level: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False, default=0)
    item: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False, default="")
    time_of_day: Mapped[str] = mapped_column(String(16), primary_key=True, nullable=False, default="")

    detail_json: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (Index("ix_edge_to", "to_species"),)


class MoveDetail(Base):
    """招式明细：威力/命中/PP/优先级/类别 + 英文效果与描述。

    效果长文按既定策略不机翻：effect_en/flavor_en 原样保存，界面如实标注英文。
    """

    __tablename__ = "move_detail"

    move_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    power: Mapped[int | None] = mapped_column(Integer)
    accuracy: Mapped[int | None] = mapped_column(Integer)  # None 表示必中
    pp: Mapped[int | None] = mapped_column(Integer)
    priority: Mapped[int | None] = mapped_column(Integer)
    damage_class: Mapped[str | None] = mapped_column(String(16))  # physical/special/status
    type_name: Mapped[str | None] = mapped_column(String(32))
    effect_chance: Mapped[int | None] = mapped_column(Integer)
    effect_en: Mapped[str | None] = mapped_column(Text)
    flavor_en: Mapped[str | None] = mapped_column(Text)
    generation: Mapped[str | None] = mapped_column(String(16))

    content_hash: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        Index("ix_move_type", "type_name"),
        Index("ix_move_class", "damage_class"),
        Index("ix_move_power", "power"),
    )


class AbilityDetail(Base):
    """特性明细：英文效果与描述 + 世代/主线系列标记。效果长文不机翻，存英文。"""

    __tablename__ = "ability_detail"

    ability_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    effect_en: Mapped[str | None] = mapped_column(Text)
    flavor_en: Mapped[str | None] = mapped_column(Text)
    generation: Mapped[str | None] = mapped_column(String(16))
    is_main_series: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    content_hash: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
