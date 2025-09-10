import os
import re
import urllib.parse
from typing import List, Optional
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

BASE = "https://openapi.naver.com/v1/search/local.json"

@dataclass
class Place:
    title: str
    category: Optional[str]
    telephone: Optional[str]
    address: Optional[str]
    roadAddress: Optional[str]
    mapx: Optional[float]  # TM128 좌표계 X
    mapy: Optional[float]  # TM128 좌표계 Y
    link: Optional[str]  # 사업장 웹사이트 등


def _strip_tags(text: str) -> str:
    if not text:
        return text
    return re.sub(r"<\/?b>", "", text)


def search_places(
    query: str, display: int = 7, start: int = 1, sort: str = "random"
) -> List[Place]:
    """
    sort: 'random' | 'comment' (공식 문서 기준)
    """
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise RuntimeError(
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 비어 있습니다."
        )

    params = {
        "query": query,
        "display": display,
        "start": start,
        "sort": sort,
    }
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        "User-Agent": "TravelGuide/0.1 (FastAPI)",
    }

    with httpx.Client(timeout=10.0, headers=headers) as client:
        r = client.get(BASE, params=params)
        r.raise_for_status()
        data = r.json()

    items = data.get("items", [])
    places: List[Place] = []
    for it in items:
        places.append(
            Place(
                title=_strip_tags(it.get("title")),
                category=it.get("category"),
                telephone=it.get("telephone"),
                address=it.get("address"),
                roadAddress=it.get("roadAddress"),
                mapx=float(it["mapx"]) if it.get("mapx") else None,
                mapy=float(it["mapy"]) if it.get("mapy") else None,
                link=it.get("link"),
            )
        )
    return places


if __name__ == "__main__":
    q = "경상북도 청도군 화양읍 파이노스"
    results = search_places(q, display=5)
    for i, p in enumerate(results, 1):
        print(f"[{i}] {p.title}")
        print(f"  카테고리: {p.category}")
        print(f"  전화: {p.telephone}")
        print(f"  지번주소: {p.address}")
        print(f"  도로명주소: {p.roadAddress}")
        print(f"  좌표(TM128): ({p.mapx}, {p.mapy})")
        print(f"  링크: {p.link}")
