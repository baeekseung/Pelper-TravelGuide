import re
import urllib.parse
import httpx
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
)
HDRS = {
    "User-Agent": UA,
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

def _txt(x) -> str:
    from bs4 import NavigableString
    if x is None:
        return ""
    if hasattr(x, "get_text"):
        s = x.get_text(" ", strip=True)
    elif isinstance(x, NavigableString):
        s = str(x).strip()
    else:
        s = str(x).strip()
    return re.sub(r"\s+", " ", s)

def _panel_root(soup: BeautifulSoup):
    """place_blind가 가장 많이 포함된 조상 div를 패널 루트로 사용."""
    cands = soup.select("span.place_blind")
    if not cands:
        return soup
    best, best_cnt = None, 0
    for b in cands:
        p, hop = b, 0
        while p and hop < 6:
            p = p.parent; hop += 1
            if getattr(p, "name", "") == "div":
                cnt = len(p.select("span.place_blind"))
                if cnt > best_cnt:
                    best, best_cnt = p, cnt
    return best or soup

def _get_by_label(panel, label: str) -> Optional[str]:
    for st in panel.select("strong"):
        blind = st.select_one("span.place_blind")
        if not blind or _txt(blind) != label:
            continue
        parent = st.parent
        vals: List[str] = []
        for sib in parent.find_all(recursive=False):
            if sib is st: continue
            t = _txt(sib)
            if t: vals.append(t)
        if vals:
            return " ".join(vals).strip() or None
        nxt = parent.find_next_sibling()
        if nxt:
            t = _txt(nxt)
            if t: return t
    return None

# 실사진 후보
_PHOTO = re.compile(
    r"https://[^\s\"'()]+pstatic\.net/[^\s\"'()]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'()]+)?",
    re.I,
)
# 비사진 제거
_BAD = re.compile(
    r"(sprite|sp_map|marker|icon|favicon|badge|logo|watermark|staticmap|svg|"
    r"default_|placeholder|btn_|ico_|symbol|stamp|blank|dummy|thumb_default|"
    r"brand|verification|cert|check|profile|avatar|emblem|square_|naver_logo|"
    r"brandstore|rasterview|vector)",
    re.I,
)

def _photos(html: str, k: int = 3) -> List[str]:
    if not html:
        return []
    cand = [u for u in _PHOTO.findall(html) if not _BAD.search(u)]
    out, seen = [], set()
    for u in cand:
        if u in seen: continue
        seen.add(u); out.append(u)
        if len(out) >= k: break
    return out

async def fetch_search_panel_info(
    region: str, place_name: str, timeout: int = 12000
) -> Dict[str, Any]:
    q = f"{region} {place_name}".strip()
    url = (
        "https://search.naver.com/search.naver"
        f"?where=nexearch&sm=top_hty&query={urllib.parse.quote(q)}"
    )
    async with httpx.AsyncClient(headers=HDRS, timeout=timeout, follow_redirects=True) as s:
        r = await s.get(url)
        if r.status_code != 200:
            return {
                "query": q,
                "address": None,
                "business_hours": None,
                "phone": None,
                "amenities": None,
                "way": None,
                "photos": [],
                "source": url,
            }

    soup = BeautifulSoup(r.text, "html.parser")
    panel = _panel_root(soup)
    
    return {
        "query": q,
        "address":        _get_by_label(panel, "주소"),
        "business_hours": _get_by_label(panel, "영업시간"),
        "phone":          _get_by_label(panel, "전화번호"),
        "amenities":      _get_by_label(panel, "편의"),
        "way":            _get_by_label(panel, "찾아가는길"),
        "photos":         _photos(r.text, 3),
        "source":         url,
    }