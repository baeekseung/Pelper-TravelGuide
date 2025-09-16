import sys
import os
import math
from typing import List

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.utils.Context_Enhance.Naver_blog_text_gatter import (
    extract_blog_content,
    build_driver,
)
from app.utils.Context_Enhance.blog_links import fetch_top_blog_links_async
from app.utils.Context_Enhance.Place_info import search_places
from app.utils.Context_Enhance.Place_Image import fetch_and_save_images
from app.utils.Context_Enhance.get_place_pid import get_place_pid_async
from app.utils.Context_Enhance.reviews_crawling import crawl_reviews_text_async
from app.utils.Context_Enhance.Place_Image import fetch_and_save_images

from dotenv import load_dotenv

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")


def tm128_to_wgs84(x, y):
    """TM128 좌표를 WGS84 좌표로 변환"""
    try:
        # TM128 좌표계의 기준점과 변환 파라미터
        XO = 43
        YO = 136
        OLON = 126.0
        OLAT = 38.0

        # TM128 좌표를 1/1000 단위로 변환 (네이버 API는 1/1000 단위로 반환)
        x = x / 1000.0
        y = y / 1000.0

        # TM128 좌표계에서 WGS84로 변환하는 근사 공식
        # 이는 한국 지역에 특화된 근사 변환입니다
        lat = (OLAT + (y - YO) * 0.0001) / 2
        lng = (OLON + (x - XO) * 0.0001) / 2

        # 좌표 범위 조정 (한국 지역 범위)
        if 33.0 <= lat <= 38.5 and 124.0 <= lng <= 132.0:
            return lat, lng
        else:
            print(f"변환된 좌표가 한국 범위를 벗어남: lat={lat}, lng={lng}")
            return None, None

    except Exception as e:
        print(f"좌표 변환 오류: {e}")
        return None, None


async def build_context(places: List[str], address: str):
    # 기존 이미지 파일들 정리 (새 요청 시마다)
    # 절대 경로 사용
    current_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    images_dir = os.path.join(current_dir, "images")

    if os.path.exists(images_dir):
        files_to_delete = []
        for filename in os.listdir(images_dir):
            if filename.endswith((".jpg", ".jpeg", ".png")):
                files_to_delete.append(filename)

        for filename in files_to_delete:
            try:
                file_path = os.path.join(images_dir, filename)
                os.remove(file_path)
            except Exception as e:
                print(f"이미지 파일 삭제 실패: {filename}, {e}")
    else:
        print("images 디렉토리가 존재하지 않습니다.")

    Place_Num = 1
    Context_Result = ""
    reference_link = []
    collected = []  # collected 데이터를 저장할 리스트
    places_info = []  # 장소 정보를 저장할 리스트
    for place in places:
        Reviews_Num = 1
        Blog_Num = 1

        # pid 번호 가져오기
        pid = await get_place_pid_async(f"{address} {place}")
        if pid == None:
            print("pid is None")
            continue

        results = search_places(f"{address} {place}", display=1)
        if len(results) == 1:

            images, save_result = await fetch_and_save_images(
                f"{address} {place}",
                skip=2,
                limit=3,
                save_name=f"Place_{Place_Num}",
                save_dir=images_dir,
            )

            # 장소 정보 수집 (좌표 변환 적용)
            if results[0].mapx and results[0].mapy:
                # TM128 좌표를 WGS84 좌표로 변환
                lat, lng = tm128_to_wgs84(results[0].mapx, results[0].mapy)
                print(
                    f"좌표 변환: TM128({results[0].mapx}, {results[0].mapy}) -> WGS84({lat}, {lng})"
                )

                # 좌표 변환이 성공한 경우에만 장소 정보 추가
                if lat is not None and lng is not None:
                    place_info = {
                        "title": results[0].title,
                        "category": results[0].category,
                        "telephone": results[0].telephone,
                        "roadAddress": results[0].roadAddress,
                        "link": results[0].link,
                        "lat": lat,
                        "lng": lng,
                    }
                    print(f"장소 정보 수집: {place_info}")
                    places_info.append(place_info)
                else:
                    print(f"좌표 변환 실패로 장소 제외: {results[0].title}")
            else:
                print(f"좌표 정보 없음: {results[0].title}")

            Context_Result += (
                f"# Place {Place_Num}\n### 장소 이름: {results[0].title}\n"
            )
            Context_Result += f"### 카테고리: {results[0].category}\n"
            Context_Result += f"### 전화: {results[0].telephone}\n"
            Context_Result += f"### 도로명주소: {results[0].roadAddress}\n"
            Context_Result += f"### 링크: {results[0].link}\n"
            Context_Result += f"### 이미지 개수: {len(images)}\n"
            Context_Result += "\n"

            blog_links = await fetch_top_blog_links_async(pid, top_k=5, headless=True)
            driver = build_driver(headless=True)
            for blog_link in blog_links:
                blog_content = extract_blog_content(blog_link.strip(), driver)
                blog_title = blog_content.get("title", "블로그") or "블로그"
                Context_Result += f"## Place {Place_Num}'s Blog {Blog_Num}\n###블로그 링크: {blog_link}\n"
                Context_Result += f"### 블로그 내용: {blog_content['text']}\n"
                reference_link.append(
                    {
                        "title": blog_title,
                        "url": blog_link,
                        "type": "blog",
                        "score": 0.0,
                    }
                )
                Context_Result += "\n"
                Blog_Num += 1

            reviews = await crawl_reviews_text_async(pid, headless=True, batches=3)
            for review in reviews:
                Context_Result += f"## Place {Place_Num}'s Reviews {Reviews_Num}\n### 리뷰 내용: {review}\n"
                Context_Result += "\n\n"
                Reviews_Num += 1

            Place_Num += 1

    return Context_Result, reference_link, places_info
