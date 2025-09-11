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
from app.services.naver_client import NaverClient, pick_top
from app.utils.Context_Enhance.Place_info import search_places
from app.utils.Context_Enhance.Place_Image import fetch_and_save_images

from dotenv import load_dotenv

load_dotenv()


NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

BASE = "https://openapi.naver.com/v1/search/blog.json"

Query = ""


def build_context(places: List[str], address: str):
    Place_Num = 1
    Context_Result = ""
    for place in places:
        results = search_places(f"{address} {place}", display=1)

        if len(results) == 1:
            print("results", results)
            Context_Result += f"Place {Place_Num}\n장소 이름: {results[0].title}\n"
            Context_Result += f"카테고리: {results[0].category}\n"
            Context_Result += f"전화: {results[0].telephone}\n"
            Context_Result += f"도로명주소: {results[0].roadAddress}\n"
            Context_Result += f"링크: {results[0].link}\n"
            Context_Result += "\n"

            blog_links = naver_blog_search(f"{address} {place}", k=5, sort="sim")
            driver = build_driver(headless=True)
            print(f"{address} {place}")
            print("blog_links", blog_links)
            Blog_Num = 1
            for blog_link in blog_links:
                blog_content = extract_blog_content(blog_link.strip(), driver)
                Context_Result += f"Blog {Blog_Num}\n블로그 링크: {blog_link}\n"
                Context_Result += f"블로그 내용: {blog_content['text']}\n"
                Context_Result += "\n"
                Blog_Num += 1

            Place_Num += 1

    # print("Context_Result\n\n", Context_Result)

# # 블로그 가져오기
# try:
#     blog_links = naver_blog_search(q, k=5, sort="sim")
#     print(f"블로그 링크 {len(blog_links)}개 발견")

#     for i, blog_link in enumerate(blog_links, 1):
#         print(f"URL: {blog_link}")

#         driver = build_driver(headless=True)
#         try:
#             blog_content = extract_blog_content(blog_link.strip(), driver)
#             if blog_content["text"]:
#                 print(f"[본문 미리보기] {blog_content['text']}")
#             else:
#                 print("[본문] 추출된 텍스트가 없습니다.")
#         except Exception as e:
#             print(f"블로그 콘텐츠 추출 실패: {e}")
#         finally:
#             driver.quit()

# except Exception as e:
#     print(f"블로그 검색 실패: {e}")


# # 이미지 저장
# res = asyncio.run(
#     fetch_and_save_images("경상북도 청도군 화양읍 파이노스", skip=2, limit=3)
# )

# print("저장된 파일들:", res)
