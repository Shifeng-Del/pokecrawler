"""P1 新功能验收：全局搜索 / 对比模式 / 收藏 / URL 同步 / 暗色模式。

DOM 级断言 + 截图，不依赖肉眼。用法：
    python scripts/verify_p1.py
"""

from __future__ import annotations

import argparse
import asyncio

from playwright.async_api import async_playwright

BASE = "http://127.0.0.1:8000"
PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASSED if ok else FAILED).append(name)
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/shots")
    args = parser.parse_args()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        console_errors: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)))

        # ---------- 1. 全局搜索 ----------
        print("== 全局搜索 ==")
        await page.goto(f"{BASE}/", wait_until="domcontentloaded")
        await page.wait_for_timeout(1800)
        await page.keyboard.press("Control+k")
        await page.wait_for_timeout(600)
        modal = await page.locator(".search-modal").count()
        check("Ctrl+K 唤起搜索面板", modal > 0)

        await page.get_by_placeholder("搜索宝可梦：喷火龙 / charizard / 6…").fill("喷")
        await page.wait_for_timeout(900)
        items = page.locator(".ant-select-item")
        n = await items.count()
        check("输入「喷」出现候选", n > 0, f"{n} 条")
        if n:
            first_text = await items.first.inner_text()
            check("候选含喷火龙", "喷火龙" in first_text, first_text.replace("\n", " ")[:40])
            await page.screenshot(path=f"{args.out}/p1_search.png")
            await items.first.click()
            await page.wait_for_timeout(2500)
            check("点击候选跳转列表页并打开抽屉",
                  page.url.endswith("/pokemon") and await page.locator(".ant-drawer-open").count() > 0)

        # ---------- 2. 对比模式（独立入口，不依赖上面的搜索跳转） ----------
        print("== 对比模式 ==")
        await page.goto(f"{BASE}/pokemon", wait_until="domcontentloaded")
        await page.wait_for_timeout(2600)
        await page.locator(".ant-table-tbody .ant-table-row").first.click()
        await page.wait_for_timeout(2200)
        drawer_btn = page.get_by_role("button", name="加入对比")
        has_btn = await drawer_btn.count() > 0
        check("抽屉出现「加入对比」按钮", has_btn)
        if has_btn:
            await drawer_btn.first.click()
            await page.wait_for_timeout(600)
            check("对比悬浮栏出现", await page.locator(".compare-bar").count() > 0)
            await page.screenshot(path=f"{args.out}/p1_compare_bar.png")
            await page.get_by_role("button", name="开始对比").click()
            await page.wait_for_timeout(2500)
            check("进入对比页", page.url.endswith("/compare"))
            check("对比页渲染雷达图", await page.locator("canvas").count() > 0)
            check("对比页渲染明细表", await page.locator(".ant-table-tbody tr").count() > 0)
            await page.screenshot(path=f"{args.out}/p1_compare_page.png")

        # ---------- 3. 收藏 + 只看收藏 ----------
        print("== 收藏 ==")
        await page.goto(f"{BASE}/pokemon", wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)
        await page.locator(".ant-table-tbody .ant-table-row").first.click()
        await page.wait_for_timeout(2200)
        fav_btn = page.get_by_role("button", name="收藏").first
        if await fav_btn.count():
            await fav_btn.click()
            await page.wait_for_timeout(500)
            check("收藏按钮状态切换", await page.get_by_role("button", name="已收藏").count() > 0)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(800)
        switch = page.locator(".filter-card .ant-switch").first
        await switch.click()
        await page.wait_for_timeout(2500)
        rows = await page.locator(".ant-table-tbody .ant-table-row").count()
        check("「只看收藏」后列表仅剩收藏项", rows == 1, f"{rows} 行")
        await page.screenshot(path=f"{args.out}/p1_favorite.png")
        # 还原
        await page.locator(".filter-card .ant-switch").first.click()
        await page.wait_for_timeout(1200)

        # ---------- 4. URL 同步 ----------
        print("== URL 同步 ==")
        await page.goto(f"{BASE}/pokemon?q=char&sort=stat_total&order=desc", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        kw = page.get_by_placeholder("搜索中文名或英文名，如 喷火龙 / char").first
        kw_val = await kw.input_value()
        check("URL 恢复搜索词", kw_val == "char", kw_val)
        sort_sel = page.locator(".filter-card .ant-select").nth(2)
        sort_text = await sort_sel.inner_text()
        check("URL 恢复排序字段", "种族值" in sort_text, sort_text)
        order_sel = page.locator(".filter-card .ant-select").nth(3)
        order_text = await order_sel.inner_text()
        check("URL 恢复排序方向", "降序" in order_text, order_text)
        # 反向：改筛选 → URL 更新
        await kw.fill("pika")
        await page.wait_for_timeout(1500)
        check("改筛选写回 URL", "q=pika" in page.url, page.url)

        # ---------- 5. 暗色模式 ----------
        print("== 暗色模式 ==")
        await page.goto(f"{BASE}/", wait_until="domcontentloaded")
        await page.wait_for_timeout(1800)
        await page.get_by_role("button", name="切换主题").click()
        await page.wait_for_timeout(1200)
        theme = await page.evaluate("document.documentElement.dataset.theme")
        check("切换暗色主题", theme == "dark", f"data-theme={theme}")
        card_style = await page.evaluate(
            """() => {
                const c = document.querySelector('.ant-card');
                const cs = getComputedStyle(c);
                return cs.backgroundColor + ' | ' + cs.backgroundImage.slice(0, 80);
            }"""
        )
        # 统计卡暗色为渐变（background-image），普通卡为纯色 #1a2138（rgb 26,33,56）
        check("卡片暗色背景生效", "26, 33, 56" in card_style or "gradient" in card_style, card_style[:70])
        await page.screenshot(path=f"{args.out}/p1_dark.png")
        # 还原亮色
        await page.get_by_role("button", name="切换主题").click()
        await page.wait_for_timeout(800)

        # ---------- 运行时错误 ----------
        real = [e for e in console_errors if "Failed to load resource" not in e and "favicon" not in e.lower()]
        check("零运行时错误", len(real) == 0, "; ".join(real[:2]))
        await browser.close()

    print(f"\n===== P1 验收：{len(PASSED)} 通过 / {len(FAILED)} 失败 =====")
    if FAILED:
        print("失败项：", FAILED)
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
