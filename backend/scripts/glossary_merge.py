"""合并中文词典分片 -> app/data/zh_glossary.json。

用法：
    python scripts/glossary_merge.py
    python scripts/glossary_merge.py --src app/data/glossary_parts --out app/data/zh_glossary.json

设计要点：
- 分片与产物同构（顶层只有一个命名空间键），便于后续增补时只改分片再重跑
- **冲突即中止**：同一命名空间同一 key 出现不同值时，打印来源并退出 3，绝不产出半成品
- 条目级校验：key 必须是不含空格/撇号的 slug；value 非空、不等于 key、不过长、无控制字符
- 幂等：重复运行输出字节一致（除 _generated_at 外），可放心重跑
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC = BACKEND_DIR / "app" / "data" / "glossary_parts"
OUT = BACKEND_DIR / "app" / "data" / "zh_glossary.json"

NAMESPACES: tuple[str, ...] = (
    "abilities",
    "moves",
    "egg-groups",
    "habitats",
    "colors",
    "shapes",
    "growth-rates",
    "evolution-trigger",
    "evolution-items",
    "locations",
    "natures",
)
SLUG_RE = re.compile(r"^[a-z0-9]+(-+[a-z0-9]+)*$")  # 允许 PokeAPI 的 --physical/--special 双连字符后缀
MAX_VALUE_LEN = 24


class MergeError(Exception):
    pass


def _validate_entry(ns: str, key: str, value: str, part: str) -> None:
    if not SLUG_RE.match(key):
        raise MergeError(f"[{part}] {ns} 的 key 不是合法 slug：{key!r}")
    if not isinstance(value, str) or not value.strip():
        raise MergeError(f"[{part}] {ns}.{key} 的译文为空")
    if value == key:
        raise MergeError(f"[{part}] {ns}.{key} 的译文与原文相同，属于无效条目")
    if len(value) > MAX_VALUE_LEN:
        raise MergeError(f"[{part}] {ns}.{key} 的译文过长（{len(value)} > {MAX_VALUE_LEN}）：{value!r}")
    if any(c in value for c in "\n\r\t"):
        raise MergeError(f"[{part}] {ns}.{key} 的译文含换行/制表符")


def merge(src: Path) -> dict[str, dict[str, str]]:
    if not src.is_dir():
        raise MergeError(f"分片目录不存在：{src}")

    merged: dict[str, dict[str, str]] = {ns: {} for ns in NAMESPACES}
    origin: dict[str, dict[str, str]] = {ns: {} for ns in NAMESPACES}
    files = sorted(src.glob("*.json"))
    if not files:
        raise MergeError(f"分片目录为空：{src}")

    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise MergeError(f"分片解析失败 {path.name}：{exc}") from exc
        for ns in NAMESPACES:
            entries = payload.get(ns)
            if not entries:
                continue
            for key, value in entries.items():
                _validate_entry(ns, key, value, path.name)
                # 交叉预警：key 出现在错误的命名空间
                for other in NAMESPACES:
                    if other != ns and key in merged[other]:
                        print(f"⚠ 交叉预警：{key} 同时出现在 {other}（{origin[other][key]}）与 {ns}（{path.name}）")
                if key in merged[ns] and merged[ns][key] != value:
                    raise MergeError(
                        f"冲突：{ns}.{key} 已由 {origin[ns][key]} 写入 {merged[ns][key]!r}，"
                        f"{path.name} 又写入 {value!r}"
                    )
                merged[ns][key] = value
                origin[ns][key] = path.name

    return merged


def main() -> int:
    ap = argparse.ArgumentParser(description="合并中文词典分片")
    ap.add_argument("--src", type=Path, default=SRC)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--generated-at", default=None, help="固定时间戳，便于产出可复现的 diff")
    args = ap.parse_args()

    try:
        merged = merge(args.src)
    except MergeError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 3

    payload = {
        "_source": "AI 生成，采用官方简体译名口径；英文 slug 保持为权威 key",
        "_version": 1,
        "_generated_at": args.generated_at or datetime.now(timezone.utc).isoformat(),
    }
    total = 0
    for ns in NAMESPACES:
        payload[ns] = dict(sorted(merged[ns].items()))
        total += len(payload[ns])

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )

    for ns in NAMESPACES:
        print(f"{ns}: {len(payload[ns])}")
    print(f"总计 {total} 条 -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
