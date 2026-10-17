"""双引擎一致性验证。

断言 httpx（静态）与 playwright（动态）两个抓取器对同一批 id 抓到的
规范化记录完全一致 —— 这是"按配置切换抓取器"能成立的前提。

用法：
    python scripts/verify_fetchers.py                # 默认校验 id 1,25,150
    python scripts/verify_fetchers.py --ids 1,6,10001
    python scripts/verify_fetchers.py --skip-playwright   # 没装内核时只跑 httpx
"""

from __future__ import annotations

import argparse
import asyncio

from _bootstrap import BACKEND_DIR  # noqa: E402,F401  副作用：sys.path + 事件循环策略 + 退出噪音屏蔽

from app.crawler.factory import AdapterFactory, FetcherFactory  # noqa: E402
from app.crawler.robots import RobotsPolicy  # noqa: E402
from config.logging_config import setup_logging  # noqa: E402
from config.settings import get_settings  # noqa: E402

# 入库前会被剔除的辅助键（原始 payload 与子表数据），不参与一致性比较
IGNORE = {"_types", "_abilities", "_stats", "_moves", "_raw"}


def normalize(record: dict) -> dict:
    return {k: v for k, v in record.items() if k not in IGNORE}


async def fetch_with(fetcher_name: str, ids: list[int]) -> dict[int, dict]:
    import time

    settings = get_settings()
    robots = RobotsPolicy(settings)
    fetcher = FetcherFactory.create(fetcher_name, settings, concurrency=2, robots=robots)
    adapter = AdapterFactory.create("pokeapi", fetcher, settings)
    out: dict[int, dict] = {}
    async with fetcher:
        print(f"  [{fetcher_name}] 抓取器就绪", flush=True)
        for pid in ids:
            t = time.perf_counter()
            out[pid] = normalize(await adapter.fetch_detail({"id": pid}))
            print(
                f"  [{fetcher_name}] id={pid} 用时 {time.perf_counter() - t:.2f}s",
                flush=True,
            )
    return out


async def main(ids: list[int], skip_playwright: bool) -> int:
    setup_logging("WARNING")
    print(f"校验 id：{ids}")

    httpx_data = await fetch_with("httpx", ids)
    print(f"  httpx     : 抓到 {len(httpx_data)} 条")

    if skip_playwright:
        print("  已跳过 playwright 校验")
        return 0

    try:
        pw_data = await fetch_with("playwright", ids)
    except Exception as exc:  # noqa: BLE001
        print(f"  playwright 不可用：{type(exc).__name__}: {exc}")
        print("  提示：先安装内核 python -m playwright install chromium")
        return 2

    print(f"  playwright: 抓到 {len(pw_data)} 条")

    ok = True
    for pid in ids:
        a, b = httpx_data.get(pid), pw_data.get(pid)
        if a is None or b is None:
            print(f"  [缺失] id={pid}")
            ok = False
            continue
        if a == b:
            print(f"  [一致] id={pid:<6} {a['name']:<18} hash={a['content_hash'][:12]}")
        else:
            ok = False
            diff = [k for k in a if a.get(k) != b.get(k)]
            print(f"  [差异] id={pid} 字段不一致：{diff}")
            for k in diff[:5]:
                print(f"        {k}: httpx={a.get(k)!r} != pw={b.get(k)!r}")

    print("\n结论：", "两种抓取器输出完全一致 ✅" if ok else "存在不一致 ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="1,25,150")
    ap.add_argument("--skip-playwright", action="store_true")
    args = ap.parse_args()
    ids = [int(x) for x in args.ids.split(",") if x.strip()]
    raise SystemExit(asyncio.run(main(ids, args.skip_playwright)))
