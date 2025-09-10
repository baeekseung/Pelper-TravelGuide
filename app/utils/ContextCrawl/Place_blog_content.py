import os
import urllib.parse
import httpx
from typing import List, Dict, Any
from langchain_community.document_loaders import WebBaseLoader
from dotenv import load_dotenv
import bs4

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

BASE = "https://openapi.naver.com/v1/search/blog.json"


def naver_blog_search(query: str, k: int = 3, sort: str = "date") -> List[str]:
    """
    네이버 검색 API(블로그)로 상위 k개의 블로그 링크를 반환.
    sort: 'sim'(정확도), 'date'(최신)
    """
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise RuntimeError(
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 필요합니다."
        )

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query": query,
        "display": max(10, k),  # 넉넉히 받아서 필터/중복 제거
        "start": 1,
        "sort": sort,
    }

    with httpx.Client(headers=headers, timeout=10.0, follow_redirects=True) as s:
        r = s.get(BASE, params=params)
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    # 'link' 필드에 원문 URL이 들어있음 (네이버블로그, 티스토리 등 혼재)
    urls: List[str] = []
    seen = set()
    for it in items:
        u = (it.get("link") or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        urls.append(u)
        if len(urls) >= k:
            break
    return urls


def load_blog_texts(urls: List[str]) -> List[Dict[str, Any]]:
    print(urls)
    if not urls:
        return []
    loader = WebBaseLoader(
        web_paths = (urls),
        bs_kwargs=dict(
            parse_only=bs4.SoupStrainer(
                "div",
                attrs={"class": ["pcol1"]},
            )
        ),
    header_template={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36",
    },
    )

    docs = loader.load()
    print(docs)

    out = []
    for d in docs:
        meta = d.metadata or {}
        out.append(
            {
                "url": meta.get("source") or meta.get("url"),
                "title": meta.get("title"),
                "content": d.page_content,  # 필요 시 길이 제한/전처리 추가
            }
        )
    return out


def fetch_place_blogs_with_naver_api(query: str, k: int = 3, sort: str = "date"):
    """
    장소 쿼리 → 네이버 API로 블로그 링크 k개 → LangChain으로 본문 수집
    """
    urls = naver_blog_search(query, k=k, sort=sort)
    return load_blog_texts(urls)


# ------------ 사용 예 ------------
if __name__ == "__main__":
    q = "경상북도 청도군 화양읍 카페마나나"
    results = fetch_place_blogs_with_naver_api(q, k=5, sort="sim")
    for i, r in enumerate(results, 1):
        print(f"\n[{i}] {r['title']}\n{r['url']}\n")
        print(r["content"], "...\n")
