import re
from typing import List
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from playwright.async_api import async_playwright, TimeoutError as PWTimeoutAsync

UA_MOBILE = (
    "Mozilla/5.0 (Linux; Android 10; Pixel 3) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)


# === Speed tunables ===
WAIT_SHORT_MS = 120
WAIT_MED_MS = 180
SCROLL_SMALL = 800
SCROLL_MED = 1200


def _normalize_to_mplace(pid: str) -> str:
    return (
        f"https://m.place.naver.com/restaurant/{pid}/review/visitor?reviewSort=recent"
    )


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


def _inner_text(page, loc) -> str:
    h = loc.element_handle()
    if not h:
        return ""
    return (
        page.evaluate("(el)=> (el.innerText||el.textContent||'').trim()", h) or ""
    ).strip()


async def _inner_text_async(page, loc) -> str:
    h = await loc.element_handle()
    if not h:
        return ""
    return (
        await page.evaluate("(el)=> (el.innerText||el.textContent||'').trim()", h) or ""
    ).strip()


def _click_safe(page, loc, wait_ms: int = WAIT_MED_MS) -> bool:
    try:
        loc.scroll_into_view_if_needed()
        loc.click()
        page.wait_for_timeout(wait_ms)
        return True
    except Exception:
        h = loc.element_handle()
        if not h:
            return False
        try:
            page.evaluate("(el)=>el.click()", h)
            page.wait_for_timeout(wait_ms)
            return True
        except Exception:
            return False


async def _click_safe_async(page, loc, wait_ms: int = WAIT_MED_MS) -> bool:
    try:
        await loc.scroll_into_view_if_needed()
        await loc.click()
        await page.wait_for_timeout(wait_ms)
        return True
    except Exception:
        h = await loc.element_handle()
        if not h:
            return False
        try:
            await page.evaluate("(el)=>el.click()", h)
            await page.wait_for_timeout(wait_ms)
            return True
        except Exception:
            return False


def _click_next_batch(page) -> bool:
    def _try(sel: str) -> bool:
        btn = page.locator(sel)
        if btn.count() == 0:
            return False
        ok = _click_safe(page, btn.first, WAIT_MED_MS)
        if ok:
            print(f"[debug] next-batch clicked by: {sel}")
        return ok

    for sel in [
        "a.fvwqf:has(span.TeItc)",
        "a:has(span.TeItc)",
        "a:has-text('펼쳐서 더보기')",
    ]:
        if _try(sel):
            return True

    span = page.locator("span.TeItc")
    if span.count() > 0:
        try:
            h = span.first.element_handle()
            ok = page.evaluate(
                "(el)=>{ const a=el.closest('a'); if(!a) return false; a.click(); return true; }",
                h,
            )
            page.wait_for_timeout(WAIT_MED_MS)
            if ok:
                print("[debug] next-batch clicked by closest('a')")
                return True
        except Exception:
            pass

    target = None
    for sel in [
        "a.fvwqf:has(span.TeItc)",
        "a:has(span.TeItc)",
        "a:has-text('펼쳐서 더보기')",
    ]:
        loc = page.locator(sel)
        if loc.count() > 0:
            target = loc.first
            break
    if not target and span.count() > 0:
        target = span.first

    if target:
        try:
            box = target.bounding_box()
            if box:
                page.mouse.click(
                    box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                )
                page.wait_for_timeout(WAIT_MED_MS)
                print("[debug] next-batch clicked by mouse coords")
                return True
        except Exception:
            pass
    print("[debug] next-batch button NOT found")
    return False


async def _click_next_batch_async(page) -> bool:
    async def _try(sel: str) -> bool:
        btn = page.locator(sel)
        if await btn.count() == 0:
            return False
        ok = await _click_safe_async(page, btn.first, WAIT_MED_MS)
        if ok:
            # print(f"[debug] next-batch clicked by: {sel}")
            pass
        return ok

    for sel in [
        "a.fvwqf:has(span.TeItc)",
        "a:has(span.TeItc)",
        "a:has-text('펼쳐서 더보기')",
    ]:
        if await _try(sel):
            return True

    span = page.locator("span.TeItc")
    if await span.count() > 0:
        try:
            h = await span.first.element_handle()
            ok = await page.evaluate(
                "(el)=>{ const a=el.closest('a'); if(!a) return false; a.click(); return true; }",
                h,
            )
            await page.wait_for_timeout(WAIT_MED_MS)
            if ok:
                print("[debug] next-batch clicked by closest('a')")
                return True
        except Exception:
            pass

    target = None
    for sel in [
        "a.fvwqf:has(span.TeItc)",
        "a:has(span.TeItc)",
        "a:has-text('펼쳐서 더보기')",
    ]:
        loc = page.locator(sel)
        if await loc.count() > 0:
            target = loc.first
            break
    if not target and await span.count() > 0:
        target = span.first

    if target:
        try:
            box = await target.bounding_box()
            if box:
                await page.mouse.click(
                    box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                )
                await page.wait_for_timeout(WAIT_MED_MS)
                print("[debug] next-batch clicked by mouse coords")
                return True
        except Exception:
            pass
    print("[debug] next-batch button NOT found")
    return False


def crawl_reviews_text(url: str, headless: bool = True, batches: int = 3) -> List[str]:
    target = _normalize_to_mplace(url)
    out: List[str] = []

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
        page.set_default_timeout(8000)
        page.set_default_navigation_timeout(8000)

        try:
            page.goto(target, wait_until="domcontentloaded")
        except PWTimeout:
            pass
        page.wait_for_timeout(WAIT_MED_MS)

        processed_offset = 0

        for b in range(batches):
            cons = page.locator("div.pui__vn15t2")
            total = cons.count()
            if total == 0:
                page.mouse.wheel(0, SCROLL_SMALL)
                page.wait_for_timeout(WAIT_SHORT_MS)
                cons = page.locator("div.pui__vn15t2")
                total = cons.count()
                if total == 0:
                    break

            # 이번 배치에서 정확히 10개 텍스트를 확보할 때까지 킵고잉
            need = 10
            collected_this_batch = 0

            while collected_this_batch < need:
                cons = page.locator("div.pui__vn15t2")
                total = cons.count()

                # 부족하면 버튼 눌러 다음 10개 노출
                if processed_offset >= total:
                    before = total
                    if not _click_next_batch(page):
                        break
                    try:
                        page.wait_for_function(
                            "(before)=> document.querySelectorAll('div.pui__vn15t2').length > before",
                            arg=before,
                            timeout=1800,
                        )
                    except Exception:
                        page.mouse.wheel(0, SCROLL_MED)
                        page.wait_for_timeout(WAIT_MED_MS)
                    cons = page.locator("div.pui__vn15t2")
                    total = cons.count()
                    if processed_offset >= total:
                        break

                end = min(processed_offset + (need - collected_this_batch), total)
                for i in range(processed_offset, end):
                    con = cons.nth(i)
                    sm = con.locator("[data-pui-click-code='rvshowmore']")
                    if sm.count() > 0:
                        _click_safe(page, sm.last, WAIT_SHORT_MS)

                    txt = _inner_text(page, con)
                    txt = re.sub(r"\s*(더보기|접기)\s*$", "", txt).strip()
                    if txt:
                        out.append(txt)
                        collected_this_batch += 1
                    else:
                        # 빈 텍스트 패~~~~~~~~~~스
                        pass

                    processed_offset += 1

                    if collected_this_batch >= need:
                        break

                if collected_this_batch < need and processed_offset >= total:
                    before = total
                    if not _click_next_batch(page):
                        break
                    try:
                        page.wait_for_function(
                            "(before)=> document.querySelectorAll('div.pui__vn15t2').length > before",
                            arg=before,
                            timeout=1800,
                        )
                    except Exception:
                        page.mouse.wheel(0, SCROLL_MED)
                        page.wait_for_timeout(WAIT_MED_MS)

            if b == batches - 1:
                break

        browser.close()
    return out[: batches * 10]


async def crawl_reviews_text_async(
    url: str, headless: bool = True, batches: int = 3
) -> List[str]:
    target = _normalize_to_mplace(url)
    out: List[str] = []

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
        await ctx.route("**/*", _block_assets)
        page = await ctx.new_page()
        page.set_default_timeout(8000)
        page.set_default_navigation_timeout(8000)

        try:
            await page.goto(target, wait_until="domcontentloaded")
        except PWTimeoutAsync:
            pass
        await page.wait_for_timeout(WAIT_MED_MS)

        processed_offset = 0

        for b in range(batches):
            cons = page.locator("div.pui__vn15t2")
            total = await cons.count()
            if total == 0:
                await page.mouse.wheel(0, SCROLL_SMALL)
                await page.wait_for_timeout(WAIT_SHORT_MS)
                cons = page.locator("div.pui__vn15t2")
                total = await cons.count()
                if total == 0:
                    break

            # 이번 배치에서 정확히 10개 텍스트를 확보할 때까지 킵고잉
            need = 10
            collected_this_batch = 0

            while collected_this_batch < need:
                cons = page.locator("div.pui__vn15t2")
                total = await cons.count()

                # 부족하면 버튼 눌러 다음 10개 노출
                if processed_offset >= total:
                    before = total
                    if not await _click_next_batch_async(page):
                        break
                    try:
                        await page.wait_for_function(
                            "(before)=> document.querySelectorAll('div.pui__vn15t2').length > before",
                            arg=before,
                            timeout=1800,
                        )
                    except Exception:
                        await page.mouse.wheel(0, SCROLL_MED)
                        await page.wait_for_timeout(WAIT_MED_MS)
                    cons = page.locator("div.pui__vn15t2")
                    total = await cons.count()
                    if processed_offset >= total:
                        break

                end = min(processed_offset + (need - collected_this_batch), total)
                for i in range(processed_offset, end):
                    con = cons.nth(i)
                    sm = con.locator("[data-pui-click-code='rvshowmore']")
                    if await sm.count() > 0:
                        await _click_safe_async(page, sm.last, WAIT_SHORT_MS)

                    txt = await _inner_text_async(page, con)
                    txt = re.sub(r"\s*(더보기|접기)\s*$", "", txt).strip()
                    if txt:
                        out.append(txt)
                        collected_this_batch += 1
                    else:
                        # 빈 텍스트 패~~~~~~~~~~스
                        pass

                    processed_offset += 1

                    if collected_this_batch >= need:
                        break

                if collected_this_batch < need and processed_offset >= total:
                    before = total
                    if not await _click_next_batch_async(page):
                        break
                    try:
                        await page.wait_for_function(
                            "(before)=> document.querySelectorAll('div.pui__vn15t2').length > before",
                            arg=before,
                            timeout=1800,
                        )
                    except Exception:
                        await page.mouse.wheel(0, SCROLL_MED)
                        await page.wait_for_timeout(WAIT_MED_MS)

            if b == batches - 1:
                break

        await browser.close()
    return out[: batches * 10]