import re
import time
from typing import Optional
from urllib.parse import quote_plus

import httpx

# ✅ 모바일 UA (모바일 검색 HTML에 place 링크가 포함되는 경우가 많아, 모바일이 유리)
UA_MOBILE = (
    "Mozilla/5.0 (Linux; Android 10; Pixel 3) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

SEARCH_URLS = [
    # m.search(모바일 웹검색)
    "https://m.search.naver.com/search.naver?query={q}",
    # m.place(모바일 플레이스 검색 패널)
    "https://m.place.naver.com/search?q={q}",
]

# place 링크에서 pid를 뽑는 정규식 (restaurant, place 등 카테고리 다양성 대응)
PID_PATTERNS = [
    re.compile(
        r"https?://(?:m\.)?place\.naver\.com/(?:restaurant|place|accommodation|attraction|mango|hairshop)/(\d+)",
        re.I,
    ),
    re.compile(
        r"data-cid=['\"](\d+)['\"]", re.I
    ),  # 일부 결과에 data-cid로 노출되기도 함
]

DEFAULT_TIMEOUT = 10.0


def _extract_pid_from_html(html: str) -> Optional[str]:
    for pat in PID_PATTERNS:
        m = pat.search(html)
        if m:
            return m.group(1)
    return None


def _request_text(url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    headers = {
        "User-Agent": UA_MOBILE,
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    with httpx.Client(
        headers=headers, timeout=timeout, follow_redirects=True
    ) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def get_place_pid_by_query_http(
    query: str, timeout: float = DEFAULT_TIMEOUT
) -> Optional[str]:
    """
    1차: HTTP만으로 모바일 검색 HTML에서 place 링크나 data-cid로 pid 추출
    """
    q = quote_plus(query)
    for tpl in SEARCH_URLS:
        url = tpl.format(q=q)
        try:
            html = _request_text(url, timeout=timeout)
        except Exception:
            continue
        pid = _extract_pid_from_html(html)
        if pid:
            return pid
        # 혹시 동적 로딩 지연 대비, 아주 짧게 한 번 더 시도
        time.sleep(0.35)
        pid = _extract_pid_from_html(html)
        if pid:
            return pid
    return None


def get_place_pid_by_query_playwright(
    query: str, headless: bool = True, timeout_ms: int = 8000
) -> Optional[str]:
    """
    2차: Playwright로 m.search 또는 m.place를 열어 place 링크가 DOM에 뜨도록 한 뒤 pid 추출
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None

    q = quote_plus(query)
    urls = [
        f"https://m.search.naver.com/search.naver?query={q}",
        f"https://m.place.naver.com/search?q={q}",
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            user_agent=UA_MOBILE,
            viewport={"width": 420, "height": 900},
            locale="ko-KR",
            java_script_enabled=True,
        )
        page = ctx.new_page()
        page.set_default_timeout(timeout_ms)

        try:
            for url in urls:
                try:
                    page.goto(url, wait_until="domcontentloaded")
                except Exception:
                    continue

                # 첫 페인트 후 살짝 대기
                page.wait_for_timeout(350)

                # 스크롤 몇 번 내려서 동적 로드 유도
                for _ in range(4):
                    page.mouse.wheel(0, 1200)
                    page.wait_for_timeout(220)

                html = page.content()
                pid = _extract_pid_from_html(html)
                if pid:
                    return pid
        finally:
            browser.close()

    return None


async def get_place_pid_by_query_playwright_async(
    query: str, headless: bool = True, timeout_ms: int = 8000
) -> Optional[str]:
    """
    2차: Playwright 비동기 API로 m.search 또는 m.place를 열어 place 링크가 DOM에 뜨도록 한 뒤 pid 추출
    """
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return None

    q = quote_plus(query)
    urls = [
        f"https://m.search.naver.com/search.naver?query={q}",
        f"https://m.place.naver.com/search?q={q}",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = await browser.new_context(
            user_agent=UA_MOBILE,
            viewport={"width": 420, "height": 900},
            locale="ko-KR",
            java_script_enabled=True,
        )
        page = await ctx.new_page()
        page.set_default_timeout(timeout_ms)

        try:
            for url in urls:
                try:
                    await page.goto(url, wait_until="domcontentloaded")
                except Exception:
                    continue

                # 첫 페인트 후 살짝 대기
                await page.wait_for_timeout(350)

                # 스크롤 몇 번 내려서 동적 로드 유도
                for _ in range(4):
                    await page.mouse.wheel(0, 1200)
                    await page.wait_for_timeout(220)

                html = await page.content()
                pid = _extract_pid_from_html(html)
                if pid:
                    return pid
        finally:
            await browser.close()

    return None


def get_place_pid(query: str, headless: bool = True) -> Optional[str]:
    """
    고수준 API:
    1) HTTP 정적 파싱으로 시도
    2) 실패 시 Playwright 폴백
    """
    pid = get_place_pid_by_query_http(query)
    if pid:
        return pid
    return get_place_pid_by_query_playwright(query, headless=headless)


async def get_place_pid_async(query: str, headless: bool = True) -> Optional[str]:
    """
    비동기 고수준 API:
    1) HTTP 정적 파싱으로 시도
    2) 실패 시 Playwright 비동기 폴백
    """
    pid = get_place_pid_by_query_http(query)
    if pid:
        return pid
    return await get_place_pid_by_query_playwright_async(query, headless=headless)


if __name__ == "__main__":
    q = "경상북도 청도군 화양읍 파이노스"
    pid = get_place_pid(q)
    print(f"Query: {q}")
    print(f"PID: {pid}")
