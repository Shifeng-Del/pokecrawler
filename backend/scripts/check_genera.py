"""校验物种分类（genus）中文覆盖情况。

用法：
    python scripts/check_genera.py              # 只报告
    python scripts/check_genera.py --strict      # 有缺口时退出码 2

两件事：
1. zh_genera.json 条目合规性（slug 化的英文 key / 非空译文 / 不过长）——文件不存在则跳过
2. 库内 pokemon_species 的 genus_zh 覆盖率：官方 zh-hans 已覆盖绝大部分，
   缺口会完整打印，需要时把 key 补进 app/data/zh_genera.json 再重跑
   `python scripts/crawl_once.py --target species --mode full --limit 100000` 落库
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
GENERA_FILE = BACKEND_DIR / "app" / "data" / "zh_genera.json"

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_VALUE_LEN = 24


def main() -> int:
    ap = argparse.ArgumentParser(description="校验 genus 中文覆盖")
    ap.add_argument("--db", type=Path, default=DB_PATH)
    ap.add_argument("--strict", action="store_true", help="存在缺口时以退出码 2 结束")
    args = ap.parse_args()

    exit_code = 0

    # ---------- 1. 手工补录文件合规性 ----------
    if GENERA_FILE.exists():
        payload = json.loads(GENERA_FILE.read_text(encoding="utf-8"))
        genera = payload.get("genera") or {}
        invalid = [
            k
            for k, v in genera.items()
            if not isinstance(k, str)
            or not k.strip()
            or not isinstance(v, str)
            or not v.strip()
            or v == k
            or len(v) > MAX_VALUE_LEN
            or any(c in v for c in "\n\r\t")
        ]
        print(f"=== zh_genera.json ===")
        print(f"手工补录 {len(genera)} 条")
        if invalid:
            print(f"⚠ 不合规词条 {len(invalid)} 条：{', '.join(map(str, invalid[:20]))}")
            exit_code = exit_code or 2
        else:
            print("全部合规")
        print()
    else:
        print("=== zh_genera.json ===\n不存在（无手工补录，仅依赖官方 zh-hans）\n")

    # ---------- 2. 库内覆盖率 ----------
    if not args.db.exists():
        print(f"[提示] 数据库不存在：{args.db}，跳过覆盖率检查")
        return exit_code

    conn = sqlite3.connect(f"file:{args.db.as_posix()}?mode=ro", uri=True)
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pokemon_species'"
        ).fetchone()
        if not exists:
            print("[提示] pokemon_species 表不存在（尚未爬取），跳过覆盖率检查")
            return exit_code

        total = conn.execute("SELECT COUNT(*) FROM pokemon_species").fetchone()[0]
        covered = conn.execute(
            "SELECT COUNT(*) FROM pokemon_species WHERE genus_zh IS NOT NULL AND genus_zh != ''"
        ).fetchone()[0]
        missing = [
            (pid, en)
            for pid, en in conn.execute(
                "SELECT pokemon_id, genus_en FROM pokemon_species "
                "WHERE genus_zh IS NULL OR genus_zh = '' ORDER BY pokemon_id"
            )
        ]
    finally:
        conn.close()

    rate = covered / total * 100 if total else 100.0
    print("=== pokemon_species.genus_zh ===")
    print(f"共 {total} 条，已覆盖 {covered} 条（{rate:.2f}%）")
    if missing:
        print(f"未覆盖 {len(missing)} 条（需要时把英文原文补进 zh_genera.json）：")
        for pid, en in missing:
            print(f"  #{pid}  {en}")
        if args.strict:
            exit_code = exit_code or 2
    else:
        print("全覆盖")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
