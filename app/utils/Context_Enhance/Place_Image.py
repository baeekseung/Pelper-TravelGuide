import re
import os
import urllib.parse
import httpx
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36"
)
HDRS = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8"}

# 이미지 필터
_RE_IMG = re.compile(
    r"https://[^\s\"'()]+pstatic\.net/[^\s\"'()]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'()]+)?",
    re.I,
)
_RE_BAD = re.compile(
    r"(sprite|icon|favicon|badge|logo|watermark|staticmap|svg|"
    r"default_|placeholder|btn_|ico_|symbol|stamp|blank|dummy|"
    r"thumb_default|brandstore|vector)",
    re.I,
)


def _dedup(urls, k=5, skip=0):
    out, seen = [], set()
    for u in urls:
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out[skip : skip + k]


async def fetch_and_save_images(
    query: str, save_dir: str = "./images", skip: int = 2, limit: int = 3
):
    os.makedirs(save_dir, exist_ok=True)
    url = (
        "https://search.naver.com/search.naver?"
        f"where=nexearch&sm=top_hty&query={urllib.parse.quote(query)}"
    )
    async with httpx.AsyncClient(
        headers=HDRS, follow_redirects=True, timeout=15.0
    ) as s:
        r = await s.get(url)
        if r.status_code != 200:
            print("검색 실패", r.status_code)
            return []
        html = r.text

        # 이미지 URL 후보 추출
        cand = [u for u in _RE_IMG.findall(html) if not _RE_BAD.search(u)]
        img_urls = _dedup(cand, k=limit, skip=skip)  # 처음 2개 건너뛰고 3개 선택

        saved_files = []
        for i, img_url in enumerate(img_urls, 1):
            try:
                resp = await s.get(img_url)
                if resp.status_code == 200:
                    ext = ".jpg"
                    fname = os.path.join(save_dir, f"{query}_{i}{ext}")
                    with open(fname, "wb") as f:
                        f.write(resp.content)
                    saved_files.append(fname)
                    print("저장 완료:", fname)
            except Exception as e:
                print("다운로드 실패:", img_url, e)

        return saved_files

# 사용 예시
if __name__ == "__main__":
    import asyncio

    res = asyncio.run(
        fetch_and_save_images("경상북도 청도군 화양읍 파이노스", skip=2, limit=3)
    )
    print("저장된 파일들:", res)
