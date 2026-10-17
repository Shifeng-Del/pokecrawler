"""校验中文词典对数据库实际取值的覆盖率。

用法：
    python scripts/check_glossary.py              # 只报告
    python scripts/check_glossary.py --strict      # 有缺口时退出码 2

比对三件事：
- missing：库里有、词典没译 -> 这正是需要补译的输入，会完整打印
- extra  ：词典里有、库里没有 -> 仅告警（未来世代/形态预留，留着无害）
- invalid：词条本身不合规（空值 / 值等于 key / 译文过长 / slug 非法）

P2 起命名空间覆盖物种档案的封闭枚举：蛋组/栖息地/体色/体型/成长率/进化触发条件，
其中蛋组存在 JSON 列里，用 ("__json__", table, column) 声明。
对应表在未爬取的库上不存在时跳过该命名空间（不计缺口）。
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BACKEND_DIR / "data" / "poke.db"
GLOSSARY = BACKEND_DIR / "app" / "data" / "zh_glossary.json"

# 命名空间 -> 取值来源：("table", "column") 或 ("__json__", "table", "column")
NAMESPACES: dict[str, tuple[str, ...]] = {
    "abilities": ("pokemon_ability", "ability_name"),
    "moves": ("pokemon_move", "move_name"),
    "habitats": ("pokemon_species", "habitat"),
    "colors": ("pokemon_species", "color"),
    "shapes": ("pokemon_species", "shape"),
    "growth-rates": ("pokemon_species", "growth_rate"),
    "evolution-trigger": ("evolution_edge", "trigger"),
    "egg-groups": ("__json__", "pokemon_species", "egg_groups_json"),
}
SLUG_RE = re.compile(r"^[a-z0-9]+(-+[a-z0-9]+)*$")  # 允许 PokeAPI 的 --physical/--special 双连字符后缀
MAX_VALUE_LEN = 24


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def db_slugs(db: Path, source: tuple[str, ...]) -> set[str]:
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        if source[0] == "__json__":
            _, table, column = source
            sql = f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL AND {column} != ''"
            out: set[str] = set()
            for (raw,) in conn.execute(sql):
                try:
                    values = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                if isinstance(values, list):
                    out.update(v for v in values if isinstance(v, str) and v)
            return out
        table, column = source
        sql = f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL AND {column} != ''"
        return {r[0] for r in conn.execute(sql)}
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="校验中文词典覆盖率")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--glossary", type=Path, default=GLOSSARY)
    ap.add_argument("--strict", action="store_true", help="存在缺口时以退出码 2 结束")
    args = ap.parse_args()

    if not args.glossary.exists():
        print(f"[错误] 词典不存在：{args.glossary}", file=sys.stderr)
        return 3
    try:
        payload = json.loads(args.glossary.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(f"[错误] 词典解析失败：{exc}", file=sys.stderr)
        return 3

    exit_code = 0
    total_missing = 0

    for ns, source in NAMESPACES.items():
        entries: dict[str, str] = payload.get(ns) or {}
        table = source[1] if source[0] == "__json__" else source[0]
        conn = sqlite3.connect(f"file:{args.db.as_posix()}?mode=ro", uri=True)
        try:
            if not _table_exists(conn, table):
                print(f"=== {ns} ===")
                print(f"跳过：表 {table} 不存在（尚未爬取）\n")
                continue
        finally:
            conn.close()

        slugs = db_slugs(args.db, source)

        missing = sorted(slugs - set(entries))
        extra = sorted(set(entries) - slugs)
        invalid = [
            k
            for k, v in entries.items()
            if not SLUG_RE.match(k)
            or not isinstance(v, str)
            or not v.strip()
            or v == k
            or len(v) > MAX_VALUE_LEN
            or any(c in v for c in "\n\r\t")
        ]

        covered = len(slugs) - len(missing)
        rate = covered / len(slugs) * 100 if slugs else 100.0
        print(f"=== {ns} ===")
        print(f"库内 {len(slugs)} 条，词典 {len(entries)} 条，命中 {covered} 条（{rate:.2f}%）")

        if missing:
            total_missing += len(missing)
            print(f"未翻译 {len(missing)} 条（补译时把下面这些 key 加进分片再重跑 merge）：")
            for k in missing:
                print(f"  {k}")
        if extra:
            print(f"词典多出 {len(extra)} 条（库内暂无，仅提示）：{', '.join(extra[:20])}")
        if invalid:
            print(f"⚠ 不合规词条 {len(invalid)} 条：{', '.join(invalid[:20])}")
            exit_code = exit_code or 2
        print()

    if total_missing and args.strict:
        print(f"[严格模式] 共 {total_missing} 条未翻译", file=sys.stderr)
        return 2
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
