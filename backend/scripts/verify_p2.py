"""P2 爬虫数据深度验收：四张新表的数量、锚点抽查与中文覆盖率。

用法（四路爬取完成后运行）：
    python scripts/verify_p2.py
    python scripts/verify_p2.py --strict   # 有任何 FAIL 时退出码 1

验收项：
1. 数量：species == 1025 / move_detail == 937 / ability_detail == 374
   （期望值为 2026-10 PokeAPI 快照；端点扩容后只需同步 EXPECTED_COUNTS）
   evolution_edge 为「归并后的唯一进化方法数」：同一方法（六元组相同）的
   多变体/跨链重复已合并为一行，实测 514；同时校验最新 evolution 任务
   540/540 全量完成、0 失败，以及知名锚点边与物种引用完整性
2. 锚点：妙蛙种子 genus_zh/en、蛋组、栖息地；bulbasaur→ivysaur(level-up,16) 边；
   dreepy→drakloak(50)→dragapult(60) 三代链；tackle(40/100/35)、overgrow 效果文非空
3. 覆盖：genus_zh 覆盖率 >= 98% 且缺失项全部是 id>=1011 的 Gen 9 DLC 新物种
   （PokeAPI 上游未上架 zh-hans，补录机制见 check_genera.py）；
   六类封闭枚举在词典中的 100% 覆盖
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BACKEND_DIR / "data" / "poke.db"
GLOSSARY = BACKEND_DIR / "app" / "data" / "zh_glossary.json"

EXPECTED_COUNTS = {
    "pokemon_species": 1025,
    "move_detail": 937,
    "ability_detail": 374,
}
# 归并后的唯一进化方法数（540 条链，含大量单物种链），实测 514，留 10% 余量
EDGE_MIN = 460
EDGE_FROM_MIN = 420
# PokeAPI 未上架 zh-hans genus 的新物种 id 下界（Gen 9 DLC / 太晶 / 桃歹郎）
GENUS_GAP_FROM_ID = 1011
GENUS_MIN_RATE = 98.0

# 命名空间 -> (表, 列或 JSON 列)
ENUM_SOURCES = {
    "habitats": ("pokemon_species", "habitat"),
    "colors": ("pokemon_species", "color"),
    "shapes": ("pokemon_species", "shape"),
    "growth-rates": ("pokemon_species", "growth_rate"),
    "evolution-trigger": ("evolution_edge", "trigger"),
    "egg-groups": ("__json__", "pokemon_species", "egg_groups_json"),
}

# 知名锚点边：(起, 终, 触发, 等级) —— 覆盖三代链/分支链/道具进化/旋转进化
ANCHOR_EDGES = [
    ("bulbasaur", "ivysaur", "level-up", 16),
    ("ivysaur", "venusaur", "level-up", 32),
    ("dreepy", "drakloak", "level-up", 50),
    ("drakloak", "dragapult", "level-up", 60),
    ("eevee", "sylveon", "level-up", 0),
    ("wurmple", "silcoon", "level-up", 7),
    ("wurmple", "cascoon", "level-up", 7),
    ("pikachu", "raichu", "use-item", 0),
    ("milcery", "alcremie", "spin", 0),
    ("golbat", "crobat", "level-up", 0),
]

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description="P2 数据验收")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    if not args.db.exists():
        print(f"[错误] 数据库不存在：{args.db}，先跑四路爬取")
        return 1

    conn = sqlite3.connect(f"file:{args.db.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        # ---------- 1. 表存在性与数量 ----------
        print("== 表与数量 ==")
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for table in ("pokemon_species", "evolution_edge", "move_detail", "ability_detail"):
            check(f"表 {table} 已创建", table in tables)

        counts = {}
        for table in ("pokemon_species", "evolution_edge", "move_detail", "ability_detail"):
            counts[table] = (
                conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if table in tables
                else 0
            )
        for table, expected in EXPECTED_COUNTS.items():
            check(f"{table} 数量 == {expected}", counts[table] == expected, f"实际 {counts[table]}")
        check(
            f"evolution_edge（归并后方法数）> {EDGE_MIN}",
            counts["evolution_edge"] > EDGE_MIN,
            f"实际 {counts['evolution_edge']}",
        )
        distinct_from = conn.execute(
            "SELECT COUNT(DISTINCT from_species) FROM evolution_edge"
        ).fetchone()[0]
        check(
            f"可进化物种（distinct from）> {EDGE_FROM_MIN}",
            distinct_from > EDGE_FROM_MIN,
            f"实际 {distinct_from}",
        )

        # 进化任务必须全量完成：540/540、0 失败（列表 540 条 = 549 最大 id 减 9 个空洞）
        job = conn.execute(
            "SELECT total, processed, failed FROM crawl_job "
            "WHERE adapter = 'pokeapi-evolution' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if job is None:
            check("存在 evolution 抓取任务记录", False)
        else:
            check(
                "evolution 任务 540/540 全量完成且 0 失败",
                job["total"] == 540 and job["processed"] == 540 and job["failed"] == 0,
                f"total={job['total']} processed={job['processed']} failed={job['failed']}",
            )

        # 物种引用完整性：边的两端都必须能在物种表找到（无孤儿边）
        orphans = conn.execute(
            "SELECT COUNT(*) FROM evolution_edge e "
            "WHERE NOT EXISTS (SELECT 1 FROM pokemon_species s WHERE s.name = e.from_species) "
            "   OR NOT EXISTS (SELECT 1 FROM pokemon_species s WHERE s.name = e.to_species)"
        ).fetchone()[0]
        check("进化边两端物种均在 species 表中（无孤儿）", orphans == 0, f"孤儿 {orphans} 条")

        # ---------- 2. 锚点抽查 ----------
        print("== 锚点抽查 ==")
        row = conn.execute(
            "SELECT genus_en, genus_zh, habitat, egg_groups_json, capture_rate "
            "FROM pokemon_species WHERE pokemon_id = 1"
        ).fetchone()
        if row is None:
            check("妙蛙种子 species 记录存在", False)
        else:
            check("妙蛙种子 species 记录存在", True)
            check("genus_en == Seed Pokémon", row["genus_en"] == "Seed Pokémon", str(row["genus_en"]))
            check("genus_zh == 种子宝可梦", row["genus_zh"] == "种子宝可梦", str(row["genus_zh"]))
            check("habitat == grassland", row["habitat"] == "grassland", str(row["habitat"]))
            check(
                "蛋组含 monster/plant",
                set(json.loads(row["egg_groups_json"])) >= {"monster", "plant"},
                row["egg_groups_json"],
            )
            check("capture_rate == 45", row["capture_rate"] == 45, str(row["capture_rate"]))

        edge = conn.execute(
            "SELECT min_level FROM evolution_edge "
            "WHERE from_species = 'bulbasaur' AND to_species = 'ivysaur' AND trigger = 'level-up'"
        ).fetchone()
        check("边 bulbasaur→ivysaur(level-up,16)", edge is not None and edge["min_level"] == 16,
              f"min_level={edge['min_level'] if edge else '缺失'}")

        # 知名锚点边批量核对（三代链/分支链/道具/旋转）
        # 注意 hit >= 1：同一方法可能因 time_of_day 等字段不同而合法占多行
        # （如 milcery→alcremie 的 day/dusk/night 三个旋转变体）
        for frm, to, trigger, level in ANCHOR_EDGES:
            hit = conn.execute(
                "SELECT COUNT(*) FROM evolution_edge "
                "WHERE from_species = ? AND to_species = ? AND trigger = ? AND min_level = ?",
                (frm, to, trigger, level),
            ).fetchone()[0]
            check(f"锚点边 {frm}→{to}({trigger},{level})", hit >= 1, f"{hit} 行")

        move = conn.execute(
            "SELECT power, accuracy, pp, damage_class, type_name, effect_en "
            "FROM move_detail WHERE move_name = 'tackle'"
        ).fetchone()
        if move is None:
            check("招式 tackle 明细存在", False)
        else:
            check("招式 tackle 明细存在", True)
            check("tackle 威力40/命中100/PP35", (move["power"], move["accuracy"], move["pp"]) == (40, 100, 35))
            check("tackle 物理/一般", (move["damage_class"], move["type_name"]) == ("physical", "normal"))
            check("tackle 效果文非空（英文原样）", bool(move["effect_en"]))

        ability = conn.execute(
            "SELECT effect_en, flavor_en, is_main_series FROM ability_detail WHERE ability_name = 'overgrow'"
        ).fetchone()
        if ability is None:
            check("特性 overgrow 明细存在", False)
        else:
            check("特性 overgrow 明细存在", True)
            check("overgrow 效果文非空", bool(ability["effect_en"]))
            check("overgrow 主线系列", ability["is_main_series"] == 1)

        # ---------- 3. 覆盖率 ----------
        print("== 中文覆盖 ==")
        total_species = conn.execute("SELECT COUNT(*) FROM pokemon_species").fetchone()[0]
        covered = conn.execute(
            "SELECT COUNT(*) FROM pokemon_species WHERE genus_zh IS NOT NULL AND genus_zh != ''"
        ).fetchone()[0]
        rate = covered / total_species * 100 if total_species else 100.0
        # 缺失项必须全部是 id>=1011 的 Gen 9 DLC 新物种：PokeAPI 上游尚未上架 zh-hans
        # 译名（属真实数据缺口而非抓取遗漏），补录后重跑 species 即自动落库
        gap_ids = [
            r[0]
            for r in conn.execute(
                "SELECT pokemon_id FROM pokemon_species "
                "WHERE genus_zh IS NULL OR genus_zh = '' ORDER BY pokemon_id"
            )
        ]
        gaps_are_known_dlc = all(i >= GENUS_GAP_FROM_ID for i in gap_ids)
        check(
            f"genus_zh 覆盖率 >= {GENUS_MIN_RATE}% 且缺失均为 Gen 9 DLC 上游缺口",
            rate >= GENUS_MIN_RATE and gaps_are_known_dlc,
            f"{rate:.2f}%（{covered}/{total_species}），缺失 id: {gap_ids}",
        )

        if GLOSSARY.exists():
            glossary = json.loads(GLOSSARY.read_text(encoding="utf-8"))
            for ns, source in ENUM_SOURCES.items():
                entries = glossary.get(ns) or {}
                if source[0] == "__json__":
                    _, table, column = source
                    values: set[str] = set()
                    for (raw,) in conn.execute(f"SELECT {column} FROM {table}"):
                        try:
                            values.update(v for v in json.loads(raw) if isinstance(v, str) and v)
                        except (TypeError, ValueError):
                            continue
                else:
                    table, column = source
                    values = {
                        r[0]
                        for r in conn.execute(
                            f"SELECT DISTINCT {column} FROM {table} "
                            f"WHERE {column} IS NOT NULL AND {column} != ''"
                        )
                    }
                missing = sorted(values - set(entries))
                check(
                    f"枚举 {ns} 100% 覆盖（{len(values)} 值）",
                    not missing,
                    f"缺：{', '.join(missing[:10])}" if missing else "",
                )
        else:
            check("中文词典存在", False, str(GLOSSARY))
    finally:
        conn.close()

    print()
    print(f"通过 {len(PASSED)} 项，失败 {len(FAILED)} 项")
    if FAILED:
        for name in FAILED:
            print(f"  FAIL  {name}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
