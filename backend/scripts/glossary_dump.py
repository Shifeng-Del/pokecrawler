"""导出待翻译的英文 slug 清单（纯只读，不触碰库结构）。

用法：
    python scripts/glossary_dump.py                  # 打印到 stdout
    python scripts/glossary_dump.py --out DIR        # 落 abilities.txt / moves.txt

说明：
- 用 sqlite3 以 mode=ro 打开，**不调用 init_db()**，避免对生产库做任何结构变更
- 输出顺序稳定（按 slug 升序），便于按序分批翻译与人工核对
- 产物是 AI 翻译词典的输入，也是 check_glossary.py 的覆盖率基准
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BACKEND_DIR / "data" / "poke.db"

# 命名空间 -> (表名, 列名)
NAMESPACES: dict[str, tuple[str, str]] = {
    "abilities": ("pokemon_ability", "ability_name"),
    "moves": ("pokemon_move", "move_name"),
}

# 用于交叉校验的期望条数（首次运行若不一致会告警，不会阻断）
EXPECTED = {"abilities": 313, "moves": 833}


def fetch_distinct(conn: sqlite3.Connection, table: str, column: str) -> list[str]:
    sql = f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}"
    return [r[0] for r in conn.execute(sql)]


def main() -> int:
    ap = argparse.ArgumentParser(description="导出待翻译的英文 slug 清单")
    ap.add_argument("--out", type=Path, default=None, help="输出目录；不传则打印到 stdout")
    ap.add_argument("--db", type=Path, default=DB_PATH, help="数据库路径")
    args = ap.parse_args()

    if not args.db.exists():
        print(f"[错误] 数据库不存在：{args.db}", file=sys.stderr)
        return 1

    # mode=ro 保证只读，防止误写
    conn = sqlite3.connect(f"file:{args.db.as_posix()}?mode=ro", uri=True)
    try:
        result: dict[str, list[str]] = {}
        for ns, (table, column) in NAMESPACES.items():
            try:
                result[ns] = fetch_distinct(conn, table, column)
            except sqlite3.Error as exc:
                print(f"[错误] 查询 {table}.{column} 失败：{exc}", file=sys.stderr)
                return 1
    finally:
        conn.close()

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        for ns, items in result.items():
            path = args.out / f"{ns}.txt"
            path.write_text("\n".join(items) + "\n", encoding="utf-8")
            print(f"已写入 {path} （{len(items)} 条）")
    else:
        for ns, items in result.items():
            print(f"=== {ns} ({len(items)}) ===")
            print("\n".join(items))
            print()

    print("--- 汇总 ---")
    for ns, items in result.items():
        exp = EXPECTED.get(ns)
        flag = "" if exp is None or len(items) == exp else f"  ⚠ 期望 {exp}"
        print(f"{ns}: {len(items)}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
