"""
- 10개씩 3배치 수집함요
- 각 컨테이너(div.pui__vn15t2) 안 rvshowmore 클릭 -> 컨테이너 innerText 수집
"""

import re
from typing import List
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

UA_MOBILE = ("Mozilla/5.0 (Linux; Android 10; Pixel 3) "
             "AppleWebKit/537.36 (KHTML, like Gecko) "
             "Chrome/124.0.0.0 Mobile Safari/537.36")

def _normalize_to_mplace(url: str) -> str:
    for pat in (r"/restaurant/(\d+)", r"/entry/place/(\d+)", r"/place/(\d+)"):
        m = re.search(pat, url)
        if m:
            pid = m.group(1)
            return f"https://m.place.naver.com/restaurant/{pid}/review/visitor?reviewSort=recent"
    return url

def _block_assets(route, req):
    u = req.url.lower()
    if any(u.endswith(ext) for ext in (".png",".jpg",".jpeg",".gif",".webp",
                                       ".mp4",".webm",".svg",".woff",".woff2",
                                       ".ttf",".otf")):
        return route.abort()
    return route.continue_()

def _inner_text(page, loc) -> str:
    h = loc.element_handle()
    if not h: return ""
    return (page.evaluate("(el)=> (el.innerText||el.textContent||'').trim()", h) or "").strip()

def _click_safe(page, loc, wait_ms: int = 180) -> bool:
    try:
        loc.scroll_into_view_if_needed()
        loc.click()
        page.wait_for_timeout(wait_ms)
        return True
    except Exception:
        h = loc.element_handle()
        if not h: return False
        try:
            page.evaluate("(el)=>el.click()", h)
            page.wait_for_timeout(wait_ms)
            return True
        except Exception:
            return False

def _click_next_batch(page) -> bool:
    def _try(sel: str) -> bool:
        btn = page.locator(sel)
        if btn.count() == 0: return False
        ok = _click_safe(page, btn.first, 250)
        if ok: print(f"[debug] next-batch clicked by: {sel}")
        return ok

    for sel in ["a.fvwqf:has(span.TeItc)",
                "a:has(span.TeItc)",
                "a:has-text('펼쳐서 더보기')"]:
        if _try(sel): return True

    span = page.locator("span.TeItc")
    if span.count() > 0:
        try:
            h = span.first.element_handle()
            ok = page.evaluate("(el)=>{ const a=el.closest('a'); if(!a) return false; a.click(); return true; }", h)
            page.wait_for_timeout(250)
            if ok:
                print("[debug] next-batch clicked by closest('a')")
                return True
        except Exception:
            pass

    target = None
    for sel in ["a.fvwqf:has(span.TeItc)", "a:has(span.TeItc)", "a:has-text('펼쳐서 더보기')"]:
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
                page.mouse.click(box["x"]+box["width"]/2, box["y"]+box["height"]/2)
                page.wait_for_timeout(250)
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
            args=["--disable-gpu","--disable-webgl","--disable-webgl2",
                  "--no-sandbox","--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            user_agent=UA_MOBILE,
            viewport={"width": 420, "height": 900},
            java_script_enabled=True,
            locale="ko-KR",
        )
        ctx.route("**/*", _block_assets)
        page = ctx.new_page(); page.set_default_timeout(10000)

        try:
            page.goto(target, wait_until="domcontentloaded")
        except PWTimeout:
            pass
        page.wait_for_timeout(400)

        processed_offset = 0

        for b in range(batches):
            cons = page.locator("div.pui__vn15t2")
            total = cons.count()
            if total == 0:
                page.mouse.wheel(0, 800); page.wait_for_timeout(250)
                cons = page.locator("div.pui__vn15t2"); total = cons.count()
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
                            arg=before, timeout=2500
                        )
                    except Exception:
                        page.mouse.wheel(0, 1200); page.wait_for_timeout(300)
                    cons = page.locator("div.pui__vn15t2"); total = cons.count()
                    if processed_offset >= total:
                        break

                end = min(processed_offset + (need - collected_this_batch), total)
                for i in range(processed_offset, end):
                    con = cons.nth(i)
                    sm = con.locator("[data-pui-click-code='rvshowmore']")
                    if sm.count() > 0:
                        _click_safe(page, sm.last, 140)

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
                            arg=before, timeout=2500
                        )
                    except Exception:
                        page.mouse.wheel(0, 1200); page.wait_for_timeout(300)

            if b == batches - 1:
                break

        browser.close()
    return out[:batches*10]

if __name__ == "__main__":
    link = input("네이버 플레이스 리뷰 링크: ").strip()
    texts = crawl_reviews_text(link, headless=True, batches=3)
    print(f"✅ 수집 {len(texts)}건")
    for i, t in enumerate(texts, 1):
        print(f"[{i}] {t}\n")
