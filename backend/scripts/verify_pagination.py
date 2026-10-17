"""翻页修复验证：访问列表页，点击第 2 页，确认数据与 URL 的 page 参数真实变化。"""
import asyncio
import sys

sys.path.insert(0, "scripts")
from playwright.async_api import async_playwright  # noqa: E402

BASE = "http://127.0.0.1:8000"


async def main() -> int:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(f"{BASE}/pokemon", wait_until="domcontentloaded")
        await page.wait_for_selector(".ant-table-row", timeout=15000)

        # 第 1 页首行 id
        first_row_p1 = await page.locator(".ant-table-row").first.locator(".id-pill").inner_text()

        # 点击分页第 2 页
        await page.locator(".ant-pagination-next").first.click()
        await page.wait_for_timeout(1200)
        first_row_p2 = await page.locator(".ant-table-row").first.locator(".id-pill").inner_text()
        current = await page.locator(".ant-pagination-item-active").inner_text()
        url_page = await page.evaluate(
            "() => new URLSearchParams(location.search).get('page')"
        )

        # 翻回第 1 页
        await page.locator(".ant-pagination-prev").first.click()
        await page.wait_for_timeout(1200)
        first_row_back = await page.locator(".ant-table-row").first.locator(".id-pill").inner_text()

        print(f"第1页首行: {first_row_p1}  第2页首行: {first_row_p2}  高亮页码: {current}  URL page: {url_page}")
        print(f"翻回后首行: {first_row_back}")

        ok = True
        if first_row_p1 == first_row_p2:
            print("FAIL: 第 2 页数据与第 1 页相同，翻页未生效"); ok = False
        if current.strip() != "2":
            print(f"FAIL: 高亮页码不是 2（实际 {current}）"); ok = False
        if url_page != "2":
            print(f"FAIL: URL page 参数不是 2（实际 {url_page}）"); ok = False
        if first_row_back != first_row_p1:
            print("FAIL: 翻回第 1 页后数据不一致"); ok = False
        if errors:
            print("FAIL: 页面报错:", errors[:3]); ok = False
        if ok:
            print("翻页验证通过")
        await browser.close()
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
