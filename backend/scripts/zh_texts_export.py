"""导出招式/特性英文长文案为分批待译文件（zh_texts 管线第一步）。

用法：
    python scripts/zh_texts_export.py            # 全量导出（已存在的分批文件默认跳过）
    python scripts/zh_texts_export.py --force    # 覆盖重导
    python scripts/zh_texts_export.py --batch-size 80

产物：app/data/zh_texts/parts/{move,ability}_{NN}.json
    {"_kind": "move", "_batch": 1, "_count": 80,
     "items": {"absorb": {"effect": "...", "flavor": "..."}, ...}}

翻译完成的分批文件写入 app/data/zh_texts/zh/（同名同格式），
再由 scripts/zh_texts_merge.py 合并为运行时的 move_texts.json / ability_texts.json。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BACKEND_DIR / "data" / "poke.db"
PARTS_DIR = BACKEND_DIR / "app" / "data" / "zh_texts" / "parts"

KINDS = {
    "move": ("move_detail", "move_name"),
    "ability": ("ability_detail", "ability_name"),
}


def export(kind: str, batch_size: int, force: bool) -> tuple[int, int]:
    table, key_col = KINDS[kind]
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            f"SELECT {key_col} AS k, effect_en, flavor_en FROM {table} ORDER BY {key_col}"
        ).fetchall()
    finally:
        con.close()

    items = {r["k"]: {"effect": r["effect_en"] or "", "flavor": r["flavor_en"] or ""} for r in rows}
    keys = sorted(items)
    total = len(keys)
    written = skipped = 0
    for i in range(0, total, batch_size):
        batch = keys[i : i + batch_size]
        no = i // batch_size + 1
        path = PARTS_DIR / f"{kind}_{no:02d}.json"
        if path.exists() and not force:
            skipped += 1
            continue
        payload = {
            "_kind": kind,
            "_batch": no,
            "_count": len(batch),
            "items": {k: items[k] for k in batch},
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        written += 1
    return written, total


def main() -> int:
    ap = argparse.ArgumentParser(description="导出待机翻的英文长文案分批文件")
    ap.add_argument("--batch-size", type=int, default=80)
    ap.add_argument("--force", action="store_true", help="覆盖已存在的分批文件")
    args = ap.parse_args()

    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    for kind in KINDS:
        written, total = export(kind, args.batch_size, args.force)
        batches = (total + args.batch_size - 1) // args.batch_size
        print(f"{kind}: {total} 条 -> {batches} 批（新写 {written}，跳过 {batches - written}）")
    print(f"分批目录：{PARTS_DIR}")
    print("下一步：把 parts/ 的英文逐批翻译后写入 app/data/zh_texts/zh/ 同名文件，再跑 zh_texts_merge.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
