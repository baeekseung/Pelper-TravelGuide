import httpx
from typing import Dict, Literal
from ..config import settings

BASE = "https://openapi.naver.com/v1/search"

class NaverClient:
    def __init__(self, timeout=10.0):
        # ✅ 키가 비어있으면 즉시 명확한 예외
        if not settings.naver_client_id or not settings.naver_client_secret:
            raise RuntimeError(
                "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 비어있습니다. "
                ".env 또는 환경변수를 확인하세요."
            )
        self.headers = {
            "X-Naver-Client-Id": settings.naver_client_id,
            "X-Naver-Client-Secret": settings.naver_client_secret,
            "User-Agent": "TravelGuide/0.1 (FastAPI)"
        }
        self.timeout = timeout

    async def _get(self, url: str, params: Dict):
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            r = await client.get(url, params=params)
            # ✅ 401 본문까지 포함해 디버깅 용이
            if r.status_code == 401:
                detail = r.text
                raise httpx.HTTPStatusError(
                    f"Naver API 401 Unauthorized: {detail}",
                    request=r.request, response=r
                )
            r.raise_for_status()
            return r.json()

    async def search_web(self, query: str, display: int = 10, start: int = 1):
        return await self._get(f"{BASE}/webkr.json",
                               {"query": query, "display": display, "start": start})

    async def search_blog(self, query: str, display: int = 10, start: int = 1):
        return await self._get(f"{BASE}/blog.json",
                               {"query": query, "display": display, "start": start})

    async def search_local(self, query: str, display: int = 10, start: int = 1):
        return await self._get(f"{BASE}/local.json",
                               {"query": query, "display": display, "start": start})

def pick_top(results: dict, kind: Literal["web", "blog", "place"], k: int = 5):
    items = results.get("items", [])[:k]
    out = []
    for it in items:
        # Naver 응답의 <b> 태그 제거
        title = (it.get("title") or "").replace("<b>", "").replace("</b>", "")
        link = it.get("link") or it.get("bloggerlink") or it.get("link")
        out.append({"title": title, "url": link, "type": kind})
    return out
