"""
place_id → 네이버 플레이스 → '블로그 리뷰' 탭 → 상단 blog 링크 top_k개 반환 (추천순)
이게 모지?
"""

from typing import List
import re
import asyncio
from urllib.parse import urlparse, urlunparse
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from playwright.async_api import async_playwright, TimeoutError as PWTimeoutAsync

UA_MOBILE = (
    "Mozilla/5.0 (Linux; Android 10; Pixel 3) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)


def _mplace_review_url(place_id: str) -> str:
    return f"https://m.place.naver.com/restaurant/{place_id}/review/visitor?reviewSort=recommand"


def _block_assets(route, req):
    u = req.url.lower()
    if any(
        u.endswith(ext)
        for ext in (
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".mp4",
            ".webm",
            ".svg",
            ".woff",
            ".woff2",
            ".ttf",
            ".otf",
        )
    ):
        return route.abort()
    return route.continue_()


def _norm_blog_url(u: str) -> str:
    if "://m.blog.naver.com/" in u:
        return u.replace("://m.blog.naver.com/", "://blog.naver.com/")
    p = urlparse(u)
    if not p.scheme:
        p = p._replace(scheme="https")
    return urlunparse(p)


def fetch_top_blog_links(
    place_id: str, top_k: int = 5, headless: bool = True
) -> List[str]:
    url = _mplace_review_url(place_id)
    links: List[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-gpu",
                "--disable-webgl",
                "--disable-webgl2",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        ctx = browser.new_context(
            user_agent=UA_MOBILE,
            viewport={"width": 420, "height": 900},
            java_script_enabled=True,
            locale="ko-KR",
        )
        ctx.route("**/*", _block_assets)
        page = ctx.new_page()
        page.set_default_timeout(10000)

        try:
            page.goto(url, wait_until="domcontentloaded")
        except PWTimeout:
            pass
        page.wait_for_timeout(300)

        clicked = False
        try:
            page.get_by_role("tab", name=re.compile("블로그\s*리뷰")).click()
            clicked = True
        except Exception:
            pass
        if not clicked:
            try:
                page.locator("a,button").filter(
                    has_text=re.compile("블로그\s*리뷰")
                ).first.click()
                clicked = True
            except Exception:
                pass
        if not clicked:
            try:
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(200)
                page.locator("a,button").filter(
                    has_text=re.compile("블로그\s*리뷰")
                ).first.click()
                clicked = True
            except Exception:
                clicked = False

        page.wait_for_timeout(400)

        def _collect_now():
            hrefs = page.locator(
                "a[href*='blog.naver.com'], a[href*='m.blog.naver.com']"
            )
            out = []
            n = min(80, hrefs.count())
            for i in range(n):
                try:
                    u = hrefs.nth(i).get_attribute("href") or ""
                    if not u:
                        continue
                    if re.search(r"blog\.naver\.com/|m\.blog\.naver\.com/", u):
                        out.append(_norm_blog_url(u))
                except Exception:
                    continue
            return out

        seen = set()
        for _ in range(6):
            for u in _collect_now():
                if u not in seen:
                    seen.add(u)
                    links.append(u)
                    if len(links) >= top_k:
                        break
            if len(links) >= top_k:
                break
            try:
                page.mouse.wheel(0, 1200)
            except Exception:
                break
            page.wait_for_timeout(250)

        browser.close()
    return links[:top_k]


async def fetch_top_blog_links_async(
    place_id: str, top_k: int = 5, headless: bool = True
) -> List[str]:
    """비동기 버전의 fetch_top_blog_links 함수"""
    url = _mplace_review_url(place_id)
    links: List[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-gpu",
                "--disable-webgl",
                "--disable-webgl2",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        ctx = await browser.new_context(
            user_agent=UA_MOBILE,
            viewport={"width": 420, "height": 900},
            java_script_enabled=True,
            locale="ko-KR",
        )
        await ctx.route("**/*", _block_assets_async)
        page = await ctx.new_page()
        page.set_default_timeout(10000)

        try:
            await page.goto(url, wait_until="domcontentloaded")
        except PWTimeoutAsync:
            pass
        await page.wait_for_timeout(300)

        clicked = False
        try:
            await page.get_by_role("tab", name=re.compile("블로그\s*리뷰")).click()
            clicked = True
        except Exception:
            pass
        if not clicked:
            try:
                await page.locator("a,button").filter(
                    has_text=re.compile("블로그\s*리뷰")
                ).first.click()
                clicked = True
            except Exception:
                pass
        if not clicked:
            try:
                await page.mouse.wheel(0, 1200)
                await page.wait_for_timeout(200)
                await page.locator("a,button").filter(
                    has_text=re.compile("블로그\s*리뷰")
                ).first.click()
                clicked = True
            except Exception:
                clicked = False

        await page.wait_for_timeout(400)

        async def _collect_now():
            hrefs = page.locator(
                "a[href*='blog.naver.com'], a[href*='m.blog.naver.com']"
            )
            out = []
            n = min(80, await hrefs.count())
            for i in range(n):
                try:
                    u = await hrefs.nth(i).get_attribute("href") or ""
                    if not u:
                        continue
                    if re.search(r"blog\.naver\.com/|m\.blog\.naver\.com/", u):
                        out.append(_norm_blog_url(u))
                except Exception:
                    continue
            return out

        seen = set()
        for _ in range(6):
            for u in await _collect_now():
                if u not in seen:
                    seen.add(u)
                    links.append(u)
                    if len(links) >= top_k:
                        break
            if len(links) >= top_k:
                break
            try:
                await page.mouse.wheel(0, 1200)
            except Exception:
                break
            await page.wait_for_timeout(250)

        await browser.close()
    return links[:top_k]


async def _block_assets_async(route, req):
    u = req.url.lower()
    if any(
        u.endswith(ext)
        for ext in (
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".mp4",
            ".webm",
            ".svg",
            ".woff",
            ".woff2",
            ".ttf",
            ".otf",
        )
    ):
        await route.abort()
    else:
        await route.continue_()


if __name__ == "__main__":
    pid = input("네이버 플레이스 가게 고유번호(place_id): ").strip()
    out = fetch_top_blog_links(pid, top_k=5, headless=True)
    print(f"✅ 블로그 링크 {len(out)}개")
    for i, u in enumerate(out, 1):
        print(f"[{i}] {u}")
