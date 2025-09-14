from typing import List, Dict, Optional
import re, os, logging
from urllib.parse import urlparse
from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36")

# 전체: 이미지, 플레이스 식별
_RX_IMG_EXT     = re.compile(r"(?:\.jpg|\.jpeg|\.png|\.webp)(?:\?|$)", re.I)
_RX_PLACE_HREF  = re.compile(r"/place/\d+")

# 전체: 아이콘, 스프라이트 등 비사진 URL ㅂㅂ
_RX_BAD_IMG = re.compile(
    r"(?:sprite|sp_map|marker|icon|favicon|badge|logo|watermark|staticmap|"
    r"default_|placeholder|btn_|ico_|symbol|stamp|blank|dummy|thumb_default|"
    r"naver_logo|brandstore|rasterview|vector|svg)",
    re.I
)

# 빡센 필터링 .... 인데 뭐 일단 냅둠
_HOST_OK = re.compile(r"(?:^|\.)(?:phinf|postfiles|blogfiles|mblogthumb|shop-phinf|storep-phinf)\.naver\.net$", re.I)
_HOST_BAD = re.compile(r"(?:^|\.)(?:s|ssl)\.pstatic\.net$", re.I)
_RX_GOOD_HINT = re.compile(r"(?:ugc|post|user|review|blog|photo|img|place|panorama|mblog|myplace|menu|storefarm)", re.I)

def _dedup_top(urls: List[str], k: int) -> List[str]:
    seen, out = set(), []
    for u in urls:
        if not u: continue
        u = u.strip().strip('"').strip("'")
        if u.startswith("//"): u = "https:" + u
        if u in seen: continue
        seen.add(u); out.append(u)
        if len(out) >= k: break
    return out

def _to_photo_url(url: str) -> str:
    if not url: return url
    if "placePath=/photo" in url: return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}placePath=/photo"

async def _enter_iframe(page, css: str, timeout_ms: int):
    try:
        await page.wait_for_selector(css, timeout=timeout_ms)
    except PWTimeoutError:
        return None
    el = await page.query_selector(css)
    return await el.content_frame()

async def _entry_frame(page, timeout_ms: int):
    fr = await _enter_iframe(page, "iframe#entryIframe", timeout_ms)
    return fr or page

async def _wait_main_root(frame, timeout_ms: int):
    await frame.wait_for_selector("#place-main-section-root", timeout=timeout_ms)

async def _scroll_lazy(frame, steps: int = 18, dy: int = 1500, delay_ms: int = 240):
    for _ in range(steps):
        try:
            await frame.mouse.wheel(0, dy)
        except Exception:
            pass
        await frame.wait_for_timeout(delay_ms)

async def _click_photo_tab_if_possible(frame, timeout_ms: int):
    try:
        tab = await frame.query_selector("a[href*='placePath=/photo']")
        if tab:
            await tab.click()
            await frame.wait_for_selector("#place-main-section-root", timeout=timeout_ms)
            await frame.wait_for_timeout(600)
    except Exception:
        pass

async def _collect_images_from_frame(frame, limit: int, mode: str = "classic") -> List[str]:
    """
    mode:
      - 'classic': 가벼운 필터링
      - 'strict' : 품질↑, 누락 위험↑
    """
    js = r"""
    () => {
      const items = [];
      const normUrl = (u) => {
        if (!u) return "";
        u = (u + "").trim();
        const m = u.match(/url\(["']?(.*?)["']?\)/i);
        if (m && m[1]) u = m[1];
        if (u.startsWith("//")) u = "https:" + u;
        return u;
      };

      const takeImg = (img) => {
        const u = normUrl(img.currentSrc || img.src || img.getAttribute("data-src") || img.getAttribute("data-lazy") || img.getAttribute("data-lazy-src"));
        const w = img.naturalWidth  || img.width  || 0;
        const h = img.naturalHeight || img.height || 0;
        const area = (w*h) || 0;
        items.push({u, w, h, area});
      };

      // 우선 place 루트 내 img
      document.querySelectorAll("#place-main-section-root img").forEach(takeImg);
      // 부족하면 전체 img
      document.querySelectorAll("img").forEach(takeImg);

      // background-image
      const all = document.querySelectorAll("*");
      for (const el of all) {
        try {
          const st = window.getComputedStyle(el);
          const bg = st && st.backgroundImage || "";
          if (bg && bg.includes("url(")) {
            const u = normUrl(bg);
            const r = el.getBoundingClientRect();
            items.push({u, w: Math.round(r.width)||0, h: Math.round(r.height)||0, area: Math.round(r.width*r.height)||0});
          }
        } catch(e) {}
      }

      // og:image
      try {
        const og = document.querySelector('meta[property="og:image"]');
        if (og && og.content) items.push({u: normUrl(og.content), w: 1200, h: 630, area: 1200*630});
      } catch(e) {}

      return items;
    }
    """
    pool = await frame.evaluate(js)
    if not pool: return []

    def _host(u: str) -> str:
        try: return (urlparse(u).hostname or "").lower()
        except Exception: return ""

    # 1) 확장자 & 기본 블랙리스트
    cands = [x for x in pool if x.get("u") and _RX_IMG_EXT.search(x["u"])]
    cands = [x for x in cands if not _RX_BAD_IMG.search(x["u"])]

    out: List[str] = []

    if mode == "strict":
        MIN_W, MIN_H = 200, 200
        tmp = []
        for x in cands:
            u, w, h = x["u"], int(x.get("w") or 0), int(x.get("h") or 0)
            hst = _host(u)
            if _HOST_BAD.search(hst):
                continue
            if not _HOST_OK.search(hst):  # 실사진 계열만
                continue
            if w < MIN_W or h < MIN_H:
                continue
            area = int(x.get("area") or (w*h))
            score = float(area) + (0.5 * 1e6 if _RX_GOOD_HINT.search(u) else 0.0)
            tmp.append((score, u))
        tmp.sort(key=lambda t: t[0], reverse=True)
        out = _dedup_top([u for _, u in tmp], limit)

    else:
        MIN_W, MIN_H = 120, 120
        tmp = []
        for x in cands:
            u, w, h = x["u"], int(x.get("w") or 0), int(x.get("h") or 0)
            if w < MIN_W or h < MIN_H:
                continue
            hst = _host(u)
            # 아이콘만 제외
            if hst.endswith("s.pstatic.net") or hst.endswith("ssl.pstatic.net"):
                continue
            area = int(x.get("area") or (w*h))
            tmp.append((area, u))
        tmp.sort(key=lambda t: t[0], reverse=True)
        out = _dedup_top([u for _, u in tmp], limit)

    return out

async def _find_first_place_link(page) -> Optional[str]:
    for fr in page.frames:
        try:
            hrefs: List[str] = await fr.evaluate("""
              () => Array.from(document.querySelectorAll('a[href]')).map(a => a.getAttribute('href'))
            """)
            if not hrefs: continue
            for h in hrefs:
                if not h: continue
                if _RX_PLACE_HREF.search(h):
                    if h.startswith("/"): h = "https://map.naver.com" + h
                    return h
        except Exception:
            continue
    return None

async def _go_photo_then_collect(page, place_url: str, limit: int, timeout_ms: int, mode: str) -> List[str]:
    await page.goto(_to_photo_url(place_url), timeout=timeout_ms, wait_until="domcontentloaded")
    frame = await _entry_frame(page, timeout_ms)
    await _wait_main_root(frame, timeout_ms)

    await _click_photo_tab_if_possible(frame, timeout_ms)

    await _scroll_lazy(frame, steps=18, dy=1500, delay_ms=240)
    photos = await _collect_images_from_frame(frame, limit, mode=mode)
    if len(photos) >= limit:
        return photos

    try:
        home = await frame.query_selector("a[href*='placePath=/home']")
        if home:
            await home.click()
            await frame.wait_for_selector("#place-main-section-root", timeout=timeout_ms)
            await _scroll_lazy(frame, steps=12, dy=1400, delay_ms=240)
            add = await _collect_images_from_frame(frame, limit - len(photos), mode=mode)
            photos = _dedup_top(photos + add, limit)
        else:
            home_url = place_url if "placePath=" in place_url else (
                place_url + ("&" if "?" in place_url else "?") + "placePath=/home"
            )
            await page.goto(home_url, timeout=timeout_ms, wait_until="domcontentloaded")
            frame2 = await _entry_frame(page, timeout_ms)
            await _wait_main_root(frame2, timeout_ms)
            await _scroll_lazy(frame2, steps=12, dy=1400, delay_ms=240)
            add = await _collect_images_from_frame(frame2, limit - len(photos), mode=mode)
            photos = _dedup_top(photos + add, limit)
    except Exception as e:
        logging.warning(f"[home-fallback] {e}")

    return photos[:limit]

async def fetch_place_details(
    url_or_search: str,
    limit: int = 3,
    timeout_ms: int = 45000,
    mode: str = "classic"
) -> Dict:
    if not url_or_search:
        return {"photos_top": [], "source": None, "picked_place_url": None}

    headless = os.getenv("HEADLESS", "1") != "0"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent=UA,
            locale="ko-KR",
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True,
            viewport={"width": 1366, "height": 900},
        )

        await context.add_init_script("""
          Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
          window.chrome = { runtime: {} };
          const originalQuery = window.navigator.permissions.query;
          window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
              ? Promise.resolve({ state: Notification.permission })
              : originalQuery(parameters);
          Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
          Object.defineProperty(navigator, 'languages', {get: () => ['ko-KR','ko']});
        """)

        page = await context.new_page()
        picked_place_url: Optional[str] = None
        photos: List[str] = []

        try:
            await page.goto(url_or_search, timeout=timeout_ms, wait_until="domcontentloaded")

            target = url_or_search
            if not _RX_PLACE_HREF.search(url_or_search):
                # 검색 → 첫 번째 플레이스 상세 찾기
                cand = await _find_first_place_link(page)
                if not cand:
                    for _ in range(14):
                        await page.mouse.wheel(0, 1400)
                        await page.wait_for_timeout(220)
                    cand = await _find_first_place_link(page)
                if cand:
                    target = cand

            picked_place_url = target
            if picked_place_url:
                photos = await _go_photo_then_collect(page, picked_place_url, limit, timeout_ms, mode=mode)

        finally:
            await context.close()
            await browser.close()

    return {
        "photos_top": photos[:limit],
        "source": picked_place_url or url_or_search,
        "picked_place_url": picked_place_url,
    }

# 아 이거 좀 맞춰봐 내가 아무렇게나 해서 헷갈려 죽겠음 그냥
fetch_photos_for_local_link = fetch_place_details
