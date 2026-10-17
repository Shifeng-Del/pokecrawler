"""从 Wikidata 抓取宝可梦简体中文官方译名，生成离线映射文件。

为什么不用 PokeAPI：它不提供 zh-Hans（只有 ja / fr / de 等 12 种语言）。
Wikidata 属性 P1685（Pokémon index）标注了图鉴编号，同时带多语言标签，
据此可以拿到覆盖率完整的简体中文译名。

产物：app/data/zh_names.json（离线静态资源，随仓库提交，运行期不再依赖外网）
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.logging_config import setup_logging  # noqa: E402

setup_logging("INFO")

import logging  # noqa: E402

logger = logging.getLogger("fetch_zh_names")

SPARQL = "https://query.wikidata.org/sparql"
UA = {"User-Agent": "PokeCrawler/1.0 (local project)", "Accept": "application/sparql-results+json"}

OUT = Path(__file__).resolve().parents[1] / "app" / "data" / "zh_names.json"


def normalize(name: str) -> str:
    """把 Wikidata 的英文显示名归一化为 PokeAPI 的 slug 形式。

    Nidoran♀ → nidoran-f    Farfetch'd → farfetchd
    Mr. Mime → mr-mime      Flabébé    → flabebe
    Type: Null → type-null  Ho-Oh      → ho-oh
    """
    s = unicodedata.normalize("NFD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().strip()
    s = s.replace("♀", "-f").replace("♂", "-m")
    s = s.replace("'", "").replace("’", "").replace(".", "").replace(":", "")
    s = re.sub(r"[\s/]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def run_sparql(query: str, timeout: float = 180.0):
    last = None
    for attempt in range(4):
        try:
            resp = httpx.get(SPARQL, params={"query": query, "format": "json"},
                             headers=UA, timeout=timeout)
            resp.raise_for_status()
            return resp.json()["results"]["bindings"]
        except Exception as exc:  # noqa: BLE001
            last = exc
            logger.warning("SPARQL 第 %d 次失败：%s", attempt + 1, exc)
    raise RuntimeError(f"SPARQL 请求失败：{last}")


QUERY = """
SELECT ?dex ?en ?zhCn ?zhHans ?zhTw ?zh WHERE {
  ?item wdt:P1685 ?dex .
  OPTIONAL { ?item rdfs:label ?en . FILTER(LANG(?en) = "en") }
  OPTIONAL { ?item rdfs:label ?zhCn . FILTER(LANG(?zhCn) = "zh-cn") }
  OPTIONAL { ?item rdfs:label ?zhHans . FILTER(LANG(?zhHans) = "zh-hans") }
  OPTIONAL { ?item rdfs:label ?zhTw . FILTER(LANG(?zhTw) = "zh-tw") }
  OPTIONAL { ?item rdfs:label ?zh . FILTER(LANG(?zh) = "zh") }
}
"""


def build_map() -> dict[str, str]:
    rows = run_sparql(QUERY)
    logger.info("Wikidata 返回 %d 行", len(rows))

    result: dict[str, str] = {}
    for row in rows:
        en = row.get("en", {}).get("value")
        if not en:
            continue
        # 优先级：简体（大陆） > 简体 > 繁体 > 通用中文
        zh = (
            row.get("zhCn", {}).get("value")
            or row.get("zhHans", {}).get("value")
            or row.get("zhTw", {}).get("value")
            or row.get("zh", {}).get("value")
        )
        if not zh:
            continue
        key = normalize(en)
        if key:
            result[key] = zh
    return result


def main() -> int:
    mapping = build_map()
    logger.info("归一化后可得 %d 条英文→中文映射", len(mapping))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "Wikidata (P1685 + multilingual labels)",
        "license": "CC0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(mapping),
        "pokemon": dict(sorted(mapping.items())),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("已写入 %s（%d 条）", OUT, len(mapping))

    sample = ["bulbasaur", "pikachu", "charizard", "mewtwo", "gyarados", "gengar"]
    for key in sample:
        print(f"  {key:<12} -> {mapping.get(key)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
