"""中文展示效果截图：列表页 + 详情抽屉 + 特性筛选下拉 + P3 招式图鉴/进化链。

用法：
    python scripts/shot_zh.py                       # 默认 http://127.0.0.1:8000
    python scripts/shot_zh.py --out DIR             # 指定输出目录

产物用于人工肉眼验收「中文为主、英文保留」的展示效果，不属于自动化测试。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, ".")

from app.core.loop import setup_event_loop_policy  # noqa: E402

setup_event_loop_policy()

from playwright.async_api import async_playwright  # noqa: E402

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "shots"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True, args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"]
    )
    ctx = await browser.new_context(viewport={"width": 1440, "height": 1000})
    page = await ctx.new_page()
    # 截图不依赖外网图片：拦截 CDN 镜像与 raw 源（PokemonAvatar 有占位降级）
    await page.route("**cdn.jsdelivr.net/**", lambda r: r.abort())
    await page.route("**raw.githubusercontent.com/**", lambda r: r.abort())

    await page.goto(args.base + "/pokemon", wait_until="domcontentloaded", timeout=45000)
    rows = page.locator("tbody tr.ant-table-row")
    await rows.first.wait_for(state="visible", timeout=30000)
    await page.wait_for_timeout(1500)
    await page.screenshot(path=str(args.out / "list_zh.png"))

    # 详情抽屉：特性中文 + 招式中文标签云
    await rows.first.click()
    await page.wait_for_timeout(2500)
    await page.screenshot(path=str(args.out / "drawer_zh.png"))

    # P3：招式悬停明细（鼠标移到招式标签上，显示威力/命中/PP/优先级）
    try:
        await page.locator(".ant-drawer-body .move-tag").first.hover(timeout=10000)
        await page.wait_for_timeout(1200)
        await page.screenshot(path=str(args.out / "move_tip_zh.png"))
        tip = await page.evaluate(
            "() => { const t = document.querySelector('.ant-tooltip, [class*=\"tooltip\"]'); return t ? t.innerText : ''; }"
        )
        print("\n招式悬停卡文本：")
        print(tip)
    except Exception as exc:  # noqa: BLE001
        print(f"[警告] 招式悬停截图失败：{type(exc).__name__}")

    body = await page.evaluate(
        "() => { const d = document.querySelector('.ant-drawer-body'); return d ? d.innerText : ''; }"
    )
    print("抽屉文本片段：")
    print("\n".join(body.splitlines()[:24]))

    # 重新载入页面（避开抽屉遮罩干扰），打开特性筛选下拉
    try:
        await page.goto(
            args.base + "/pokemon", wait_until="domcontentloaded", timeout=45000
        )
        await page.locator("tbody tr.ant-table-row").first.wait_for(
            state="visible", timeout=30000
        )
        await page.wait_for_timeout(1500)
        # 第 1 个 select 是属性，第 2 个是特性
        await page.locator(".ant-select").nth(1).click(timeout=15000)
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(args.out / "filter_ability_zh.png"))
        opts = await page.evaluate(
            "() => Array.from(document.querySelectorAll('.ant-select-item-option-content')).slice(0,6).map(e => e.innerText)"
        )
        print("\n特性下拉前 6 项：", " | ".join(opts))
    except Exception as exc:  # noqa: BLE001
        print(f"[警告] 特性下拉截图失败：{type(exc).__name__}")

    # P3：进化链大图（抽屉内「查看大图」→ 水平链路弹层）
    try:
        await page.goto(args.base + "/pokemon", wait_until="domcontentloaded", timeout=45000)
        await page.locator("tbody tr.ant-table-row").first.wait_for(
            state="visible", timeout=30000
        )
        await page.wait_for_timeout(1200)
        await page.locator("tbody tr.ant-table-row").first.click()
        await page.wait_for_timeout(2500)
        await page.locator("button:has-text('查看大图')").first.click(timeout=15000)
        await page.wait_for_timeout(1200)
        await page.screenshot(path=str(args.out / "evolution_modal_zh.png"))
        modal_text = await page.evaluate(
            "() => { const m = document.querySelector('.ant-modal-body'); return m ? m.innerText : ''; }"
        )
        print("\n进化链弹层文本片段：")
        print("\n".join(modal_text.splitlines()[:16]))
        await page.keyboard.press("Escape")
    except Exception as exc:  # noqa: BLE001
        print(f"[警告] 进化链大图截图失败：{type(exc).__name__}")

    # P3：招式图鉴页
    try:
        await page.goto(args.base + "/moves", wait_until="domcontentloaded", timeout=45000)
        await page.locator("tbody tr.ant-table-row").first.wait_for(
            state="visible", timeout=30000
        )
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(args.out / "movedex_zh.png"))
        # 点第一行看招式详情弹层
        await page.locator("tbody tr.ant-table-row").first.click()
        await page.wait_for_timeout(1800)
        await page.screenshot(path=str(args.out / "move_detail_zh.png"))
        detail_text = await page.evaluate(
            "() => { const m = document.querySelector('.ant-modal-body'); return m ? m.innerText : ''; }"
        )
        print("\n招式详情弹层文本片段：")
        print("\n".join(detail_text.splitlines()[:18]))
    except Exception as exc:  # noqa: BLE001
        print(f"[警告] 招式图鉴截图失败：{type(exc).__name__}")

    print(f"\n截图已保存到 {args.out}")
    await ctx.close()
    await pw.stop()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
