"""前端冒烟检查：真实加载页面，断言有内容渲染且无运行时错误。

用法：
    python scripts/smoke_frontend.py                       # 默认 http://127.0.0.1:8000
    python scripts/smoke_frontend.py --base http://127.0.0.1:5173

用于捕捉「HTTP 200 但页面空白」这类 curl 测不出的问题。
"""
from __future__ import annotations

import argparse
import asyncio
import sys

sys.path.insert(0, ".")

from app.core.loop import setup_event_loop_policy  # noqa: E402

setup_event_loop_policy()

from playwright.async_api import async_playwright  # noqa: E402

ROUTES = ["/", "/pokemon", "/moves", "/charts", "/crawl"]

# 图片来自 raw.githubusercontent.com，国内网络常不可达，属预期噪音
IGNORED = ("ERR_CONNECTION_RESET", "ERR_NAME_NOT_RESOLVED", "raw.githubusercontent")


async def check(browser, base: str, route: str) -> tuple[bool, str]:
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await ctx.new_page()
    # 外链图鉴图片在国内网络不可达，直接 abort，避免等待拖垮检查
    await page.route("**raw.githubusercontent.com/**", lambda r: r.abort())

    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    await page.goto(base + route, wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(3000)

    root_len = await page.evaluate(
        "() => { const el = document.getElementById('root'); return el ? el.innerHTML.length : 0; }"
    )
    text = await page.evaluate("() => document.body.innerText")

    real_errors = [e for e in errors if not any(i in e for i in IGNORED)]
    ok = root_len > 2000 and len(text.strip()) > 50 and not real_errors
    detail = f"root={root_len}B text={len(text)}B errors={len(real_errors)}"
    if real_errors:
        detail += " | " + " ; ".join(e[:120] for e in real_errors[:3])
    await ctx.close()
    return ok, detail


async def check_drawer(browser, base: str) -> tuple[bool, str]:
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await ctx.new_page()
    await page.route("**raw.githubusercontent.com/**", lambda r: r.abort())

    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    await page.goto(base + "/pokemon", wait_until="domcontentloaded", timeout=45000)
    rows = page.locator("tbody tr.ant-table-row")
    await rows.first.wait_for(state="visible", timeout=25000)
    await rows.first.click()
    await page.wait_for_timeout(2500)
    body = await page.evaluate(
        "() => { const d = document.querySelector('.ant-drawer-body'); return d ? d.innerText : ''; }"
    )
    real_errors = [e for e in errors if not any(i in e for i in IGNORED)]
    ok = len(body) > 100 and not real_errors
    detail = f"drawer={len(body)}B errors={len(real_errors)}" + (
        " | " + " ; ".join(e[:120] for e in real_errors[:3]) if real_errors else ""
    )
    await ctx.close()
    return ok, detail


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    args = ap.parse_args()

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True, args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
    )
    print(f"前端冒烟检查 @ {args.base}")
    print("-" * 62)
    failed = 0
    for route in ROUTES:
        ok, detail = await check(browser, args.base, route)
        print(f"  {'PASS' if ok else 'FAIL'}  {route:<10} {detail}")
        failed += 0 if ok else 1

    ok, detail = await check_drawer(browser, args.base)
    print(f"  {'PASS' if ok else 'FAIL'}  {'抽屉交互':<10} {detail}")
    failed += 0 if ok else 1

    print("-" * 62)
    print("全部通过" if failed == 0 else f"{failed} 项失败")

    await pw.stop()
    return 0 if failed == 0 else 1


sys.exit(asyncio.run(main()))
