"""把 zh_genera.json 补录的 genus 中文回填到 pokemon_species（P4 机翻补录专用）。

背景：PokeAPI 上游 15 个 Gen 9 DLC 物种（id≥1011）无官方 zh-hans，
glossary/zh_genera.py 的补录表只影响「读取路径」，本脚本负责把译文落库，
与 species writer 的 compare_extra 口径一致（仅补 genus_zh，不动其他列）。

用法：
    python scripts/backfill_genus_zh.py            # 回填并报告
    python scripts/backfill_genus_zh.py --dry-run  # 只看会改哪些行
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.utils.zh_genera import load_genera, _norm  # noqa: E402

DB_PATH = BACKEND_DIR / "data" / "poke.db"


def main() -> int:
    ap = argparse.ArgumentParser(description="回填 genus_zh 机翻补录")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    genera = load_genera()
    if not genera:
        print("[错误] zh_genera.json 为空或不存在", file=sys.stderr)
        return 3

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT pokemon_id, name, genus_en, genus_zh FROM pokemon_species "
        "WHERE genus_zh IS NULL OR genus_zh = ''"
    ).fetchall()

    patched = 0
    for r in rows:
        zh = genera.get(_norm(r["genus_en"] or ""))
        if not zh:
            print(f"⚠ 无补录：{r['name']}（{r['genus_en']}）")
            continue
        print(f"{'将回填' if args.dry_run else '已回填'}：{r['name']} "
              f"{r['genus_en']} -> {zh}")
        if not args.dry_run:
            con.execute(
                "UPDATE pokemon_species SET genus_zh = ? WHERE pokemon_id = ?",
                (zh, r["pokemon_id"]),
            )
        patched += 1

    if not args.dry_run:
        con.commit()
    left = con.execute(
        "SELECT COUNT(*) FROM pokemon_species WHERE genus_zh IS NULL OR genus_zh = ''"
    ).fetchone()[0]
    con.close()

    print(f"\n{'预估' if args.dry_run else '实际'}回填 {patched} 条，剩余缺口 {left} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
