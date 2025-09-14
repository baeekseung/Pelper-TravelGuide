import sys
import os
import asyncio
from typing import List

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.utils.Context_Enhance.Naver_blog_text_gatter import (
    naver_blog_search,
    extract_blog_content,
    build_driver,
)
from app.utils.Context_Enhance.blog_links import fetch_top_blog_links_async
from app.services.naver_client import NaverClient, pick_top
from app.utils.Context_Enhance.Place_info import search_places
from app.utils.Context_Enhance.Place_Image import fetch_and_save_images
from app.utils.Context_Enhance.get_place_pid import get_place_pid_async
from app.utils.Context_Enhance.reviews_crawling import crawl_reviews_text_async
from app.utils.Context_Enhance.Place_Image import fetch_and_save_images

from dotenv import load_dotenv

load_dotenv()


NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

BASE = "https://openapi.naver.com/v1/search/blog.json"

Query = ""


async def build_context(places: List[str], address: str):
    Place_Num = 1
    Context_Result = ""
    collected = []  # collected 데이터를 저장할 리스트
    for place in places:
        Reviews_Num = 1
        Blog_Num = 1
        
        # pid 번호 가져오기
        pid = await get_place_pid_async(f"{address} {place}")
        if pid==None:
            print("pid is None")
            continue

        results = search_places(f"{address} {place}", display=1)
        if len(results) == 1:
            Context_Result += f"# Place {Place_Num} - {place}\n## 장소 이름: {results[0].title}\n"
            Context_Result += f"## 카테고리: {results[0].category}\n"
            Context_Result += f"## 전화: {results[0].telephone}\n"
            Context_Result += f"## 도로명주소: {results[0].roadAddress}\n"
            Context_Result += f"## 링크: {results[0].link}\n"
            Context_Result += "\n"

            blog_links = await fetch_top_blog_links_async(pid, top_k=5, headless=True)
            driver = build_driver(headless=True)
            for blog_link in blog_links:
                blog_content = extract_blog_content(blog_link.strip(), driver)
                Context_Result += f"## Blog {Blog_Num}\n블로그 링크: {blog_link}\n"
                Context_Result += f"### 블로그 내용: {blog_content['text']}\n"
                Context_Result += "\n"
                Blog_Num += 1

            reviews = await crawl_reviews_text_async(pid, headless=True, batches=3)
            for review in reviews:
                Context_Result += f"## Reviews {Reviews_Num}\n### 리뷰 내용: {review}\n"
                Context_Result += "\n"
                Reviews_Num += 1
                
            images = await fetch_and_save_images(f"{address} {place}", skip=2, limit=3)

            Place_Num += 1

    return Context_Result