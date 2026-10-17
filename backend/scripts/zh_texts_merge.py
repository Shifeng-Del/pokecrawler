"""合并译文中分批文件 -> app/data/zh_texts/{move,ability}_texts.json（管线第二步）。

用法：
    python scripts/zh_texts_merge.py             # 全量合并（覆盖率不足则退出 3）
    python scripts/zh_texts_merge.py --partial   # 允许部分覆盖（调试用）

设计要点（与 glossary_merge.py 同构）：
- 分批译文放 app/data/zh_texts/zh/，格式 {"slug": {"effect": "...", "flavor": "..."}}
- 以 parts/ 英文源为基准做覆盖率校验：缺一条都不产出成品，防止半成品上线
- 软校验：ASCII 字母占比过高的条目判定「疑似漏译」并警告（HP/PP/× 等合法残留除外）
- 幂等：产物按 slug 排序，重复运行字节一致（除 _generated_at 外）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
BASE = BACKEND_DIR / "app" / "data" / "zh_texts"
PARTS_DIR = BASE / "parts"
ZH_DIR = BASE / "zh"

OUT = {"move": BASE / "move_texts.json", "ability": BASE / "ability_texts.json"}
MAX_ASCII_RATIO = 0.30


class MergeError(Exception):
    pass


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise MergeError(f"解析失败 {path.name}：{exc}") from exc


def _english_source(kind: str) -> dict[str, dict[str, str]]:
    """parts/ 里该类型的全部英文源（key -> {effect, flavor}）。"""
    src: dict[str, dict[str, str]] = {}
    files = sorted(PARTS_DIR.glob(f"{kind}_*.json"))
    if not files:
        raise MergeError(f"parts/ 下没有 {kind}_*.json，请先跑 zh_texts_export.py")
    for path in files:
        payload = _load_json(path)
        for k, v in (payload.get("items") or {}).items():
            if k in src and src[k] != v:
                raise MergeError(f"英文源冲突：{kind}.{k} 在 {path.name} 与之前批次不一致")
            src[k] = v
    return src


def _translations(kind: str) -> dict[str, dict[str, str]]:
    """zh/ 下该类型的全部译文，分批文件间冲突即中止。"""
    out: dict[str, dict[str, str]] = {}
    origin: dict[str, str] = {}
    for path in sorted(ZH_DIR.glob(f"{kind}_*.json")):
        payload = _load_json(path)
        for k, v in payload.items():
            if k.startswith("_"):
                continue
            if k in out and out[k] != v:
                raise MergeError(
                    f"译文冲突：{kind}.{k} 已由 {origin[k]} 写入 {out[k]!r}，"
                    f"{path.name} 又写入 {v!r}"
                )
            out[k] = v
            origin[k] = path.name
    return out


def _check_entry(kind: str, key: str, en: dict, zh: dict, part: str) -> None:
    for field in ("effect", "flavor"):
        src = en.get(field) or ""
        v = zh.get(field)
        if v is None:
            if src:
                raise MergeError(f"[{part}] {kind}.{key}.{field} 缺译文（英文源非空）")
            continue  # 上游英文本身为空（如 Gen9 新招式），允许留空
        if not isinstance(v, str) or not v.strip():
            if src:
                raise MergeError(f"[{part}] {kind}.{key}.{field} 译文为空字符串")
            continue
        if v == src:
            raise MergeError(f"[{part}] {kind}.{key}.{field} 译文与英文原文完全相同，疑似漏翻")
        if v:
            ascii_ratio = sum(c.isascii() and c.isalpha() for c in v) / max(len(v), 1)
            if ascii_ratio > MAX_ASCII_RATIO:
                print(
                    f"⚠ 疑似漏译：{kind}.{key}.{field} ASCII 字母占比 "
                    f"{ascii_ratio:.0%} -> {v[:60]!r}"
                )


def merge_kind(kind: str, partial: bool) -> tuple[int, int]:
    en = _english_source(kind)
    zh = _translations(kind)

    missing = [k for k in en if k not in zh]
    extra = [k for k in zh if k not in en]
    if missing and not partial:
        raise MergeError(
            f"{kind} 覆盖率不足：{len(en) - len(missing)}/{len(en)}，"
            f"缺 {len(missing)} 条（如 {', '.join(sorted(missing)[:8])}…）。"
            f"补齐 zh/ 分批后重跑，或临时加 --partial"
        )
    if extra:
        print(f"⚠ {kind} 译文中有 {len(extra)} 个英文源不存在的 key：{', '.join(sorted(extra)[:8])}")

    for k in sorted(zh):
        _check_entry(kind, k, en.get(k, {}), zh[k], "zh")

    payload = {
        "_source": "AI 机翻（术语表见 TERMS.md）；英文 slug 保持权威 key，译文缺失时界面回落英文",
        "_version": 1,
        "_generated_at": datetime.now(timezone.utc).isoformat(),
        "_coverage": f"{len(zh)}/{len(en)}",
        "items": {k: zh[k] for k in sorted(zh)},
    }
    OUT[kind].write_text(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return len(zh), len(en)


def main() -> int:
    ap = argparse.ArgumentParser(description="合并译文中分批文件")
    ap.add_argument("--partial", action="store_true", help="允许部分覆盖（调试用）")
    args = ap.parse_args()

    try:
        for kind in OUT:
            done, total = merge_kind(kind, args.partial)
            print(f"{kind}: {done}/{total} -> {OUT[kind].name}")
    except MergeError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
