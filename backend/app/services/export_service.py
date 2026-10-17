"""导出服务：CSV（utf-8-sig 防 Excel 乱码）/ JSON，流式生成。"""

from __future__ import annotations

import csv
import io
import json
import logging
from collections.abc import AsyncIterator

from app.core.database import get_session_factory
from app.utils.time import stamp
from app.utils.zh_glossary import ability_out, glossary_zh

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    "id",
    "name",
    "name_zh",
    "type_primary",
    "type_secondary",
    "types",
    "abilities",
    "abilities_zh",
    "stat_hp",
    "stat_attack",
    "stat_defense",
    "stat_special_attack",
    "stat_special_defense",
    "stat_speed",
    "stat_total",
    "height",
    "weight",
    "base_experience",
    "image_url",
    "updated_at",
]

BATCH = 200


async def iter_csv(stmt) -> AsyncIterator[bytes]:
    """流式生成 CSV，首块带 BOM。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    yield buf.getvalue().encode("utf-8-sig")
    buf.seek(0)
    buf.truncate(0)

    offset = 0
    async with get_session_factory()() as session:
        while True:
            rows = (
                (await session.execute(stmt.offset(offset).limit(BATCH)))
                .scalars()
                .unique()
                .all()
            )
            if not rows:
                break
            for p in rows:
                try:
                    types = json.loads(p.types_json or "[]")
                except ValueError:
                    types = []
                try:
                    abilities = json.loads(p.abilities_json or "[]")
                except ValueError:
                    abilities = []
                ability_names = [
                    a.get("name") if isinstance(a, dict) else a for a in abilities
                ]
                # 先按列名构造整行，再按 CSV_COLUMNS 顺序取值，杜绝表头与值错位
                row = {
                    "id": p.id,
                    "name": p.name,
                    "name_zh": p.name_zh,
                    "type_primary": p.type_primary,
                    "type_secondary": p.type_secondary,
                    "types": "/".join(types),
                    "abilities": "/".join(str(a) for a in ability_names),
                    "abilities_zh": "/".join(
                        glossary_zh("abilities", a) or "" for a in ability_names
                    ),
                    "stat_hp": p.stat_hp,
                    "stat_attack": p.stat_attack,
                    "stat_defense": p.stat_defense,
                    "stat_special_attack": p.stat_special_attack,
                    "stat_special_defense": p.stat_special_defense,
                    "stat_speed": p.stat_speed,
                    "stat_total": p.stat_total,
                    "height": p.height,
                    "weight": p.weight,
                    "base_experience": p.base_experience,
                    "image_url": p.image_url,
                    "updated_at": p.updated_at,
                }
                writer.writerow([row.get(c) for c in CSV_COLUMNS])
            offset += len(rows)
            yield buf.getvalue().encode("utf-8")
            buf.seek(0)
            buf.truncate(0)
            if len(rows) < BATCH:
                break


async def iter_json(stmt) -> AsyncIterator[bytes]:
    yield b"["
    offset = 0
    first = True
    async with get_session_factory()() as session:
        while True:
            rows = (
                (await session.execute(stmt.offset(offset).limit(BATCH)))
                .scalars()
                .unique()
                .all()
            )
            if not rows:
                break
            chunks: list[str] = []
            for p in rows:
                try:
                    types = json.loads(p.types_json or "[]")
                except ValueError:
                    types = []
                try:
                    abilities = json.loads(p.abilities_json or "[]")
                except ValueError:
                    abilities = []
                try:
                    stats = json.loads(p.stats_json or "{}")
                except ValueError:
                    stats = {}
                prefix = "" if first else ","
                chunks.append(
                    prefix
                    + json.dumps(
                        {
                            "id": p.id,
                            "name": p.name,
                            "name_zh": p.name_zh,
                            "types": types,
                            "abilities": [
                                a for a in (ability_out(x) for x in abilities) if a
                            ],
                            "stats": stats,
                            "stat_total": p.stat_total,
                            "height": p.height,
                            "weight": p.weight,
                            "base_experience": p.base_experience,
                            "image_url": p.image_url,
                            "updated_at": p.updated_at,
                        },
                        ensure_ascii=False,
                    )
                )
                first = False
            offset += len(rows)
            yield "".join(chunks).encode("utf-8")
            if len(rows) < BATCH:
                break
    yield b"]"


def filename(fmt: str) -> str:
    return f"pokemon_{stamp()}.{fmt}"
