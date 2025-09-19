import sys
import os
import math
import asyncio
from typing import List, Tuple, Dict, Any

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.utils.Context_Enhance.Naver_blog_text_gatter import (
    _pick_body_block_requests as extract_blog_body_requests,
)
from app.utils.Context_Enhance.blog_links import fetch_top_blog_links_async
from app.utils.Context_Enhance.Place_info import search_places
from app.utils.Context_Enhance.get_place_pid import get_place_pid_async
from app.utils.Context_Enhance.reviews_crawling import crawl_reviews_text_async
from app.utils.Context_Enhance.Place_Image import fetch_and_save_images
from app.utils.Context_Enhance.Blog_text_mining import refine_multiple_blogs_async
from app.utils.geo import geocode_address
from app.utils.cache_util import load_cache, save_cache

from dotenv import load_dotenv

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")


async def _gather_place_context(
    place_query: str,
    images_dir: str,
    place_num: int,
    blog_top_k: int,
    review_batches: int,
    image_limit: int,
    user_query: str = "",
    enable_blog_refinement: bool = True,
) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    cache_key = (
        f"place_ctx::{place_query}::k{blog_top_k}::b{review_batches}::i{image_limit}::refine{enable_blog_refinement}::q{user_query[:50] if user_query else 'none'}"
    )
    cached = load_cache(cache_key)
    if cached:
        # 캐시에 의존하기 전에 실제 이미지가 존재하는지 확인
        save_prefix = f"Place_{place_num}_"
        try:
            has_files = any(
                fn.startswith(save_prefix) and fn.endswith((".jpg", ".jpeg", ".png"))
                for fn in os.listdir(images_dir)
            )
        except Exception:
            has_files = False
        if has_files:
            return cached

    pid = await get_place_pid_async(place_query)
    if pid is None:
        return ("", [], {})

    results = search_places(place_query, display=1)
    if len(results) != 1:
        return ("", [], {})

    images, _ = await fetch_and_save_images(
        place_query,
        skip=2,
        limit=image_limit,
        save_name=f"Place_{place_num}",
        save_dir=images_dir,
    )

    lat, lng = geocode_address(results[0].roadAddress)
    place_info = {
        "title": results[0].title,
        "category": results[0].category,
        "telephone": results[0].telephone,
        "address": results[0].address,
        "roadAddress": results[0].roadAddress,
        "link": results[0].link,
        "lat": lat,
        "lng": lng,
    }

    ctx = []
    ctx.append(f"# Place {place_num}\n### 장소 이름: {results[0].title}\n")
    ctx.append(f"### 카테고리: {results[0].category}\n")
    ctx.append(f"### 전화: {results[0].telephone}\n")
    ctx.append(f"### 도로명주소: {results[0].roadAddress}\n")
    ctx.append(f"### 링크: {results[0].link}\n")
    ctx.append(f"### 이미지 개수: {len(images)}\n\n")

    reference_link: List[Dict[str, Any]] = []
    blog_links = await fetch_top_blog_links_async(pid, top_k=blog_top_k, headless=True)
    
    # 블로그 내용 수집
    blog_contents = []
    for blog_link in blog_links:
        try:
            body = extract_blog_body_requests(blog_link.strip())
            blog_title = body.get("title", "블로그") or "블로그"
            blog_contents.append({
                "text": body.get("text", ""),
                "url": blog_link,
                "title": blog_title
            })
        except Exception as e:
            print(f"블로그 추출 실패: {blog_link}, {e}")
            continue
    
    # 블로그 정제 (ChatGPT 사용)
    if enable_blog_refinement and blog_contents and user_query:
        try:
            refined_blogs = await refine_multiple_blogs_async(
                blog_contents, 
                place_name=results[0].title,
                query=user_query,
                max_length_per_blog=1024
            )
            blog_contents = refined_blogs
        except Exception as e:
            print(f"블로그 정제 실패, 원본 사용: {e}")
    
    # 정제된 블로그 내용을 컨텍스트에 추가
    for idx, blog in enumerate(blog_contents, 1):
        ctx.append(f"## Place {place_num}'s Blog {idx}\n###블로그 링크: {blog['url']}\n")
        ctx.append(f"### 블로그 제목: {blog['title']}\n")
        ctx.append(f"### 블로그 내용: {blog['text']}\n\n")
        reference_link.append(
            {"title": blog['title'], "url": blog['url'], "type": "blog", "score": 0.0}
        )

    reviews = await crawl_reviews_text_async(pid, headless=True, batches=review_batches)
    for i, review in enumerate(reviews, 1):
        ctx.append(f"## Place {place_num}'s Reviews {i}\n### 리뷰 내용: {review}\n\n\n")

    context_text = "".join(ctx)
    payload = (context_text, reference_link, place_info)
    # 이미지가 비었으면 캐시 저장 스킵 → 다음 요청에서 재수집 유도
    try:
        img_prefix = f"Place_{place_num}_"
        has_files = any(
            fn.startswith(img_prefix) and fn.endswith((".jpg", ".jpeg", ".png"))
            for fn in os.listdir(images_dir)
        )
    except Exception:
        has_files = False
    if has_files:
        save_cache(cache_key, payload)
    return payload


async def build_context(
    places: List[str],
    address: str,
    blog_top_k: int = 3,
    review_batches: int = 2,
    image_limit: int = 3,
    max_concurrency: int = 3,
    user_query: str = "",
    enable_blog_refinement: bool = True,
):
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
    all_ctx_parts: List[str] = []
    all_refs: List[Dict[str, Any]] = []
    places_info: List[Dict[str, Any]] = []

    sem = asyncio.Semaphore(max_concurrency)

    async def _task_wrapper(place_name: str, idx: int):
        async with sem:
            q = f"{address} {place_name}"
            ctx, refs, pinfo = await _gather_place_context(
                q, images_dir, idx, blog_top_k, review_batches, image_limit, user_query, enable_blog_refinement
            )
            return (ctx, refs, pinfo)

    tasks = [
        asyncio.create_task(_task_wrapper(place, i))
        for i, place in enumerate(places, start=1)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for res in results:
        if isinstance(res, Exception):
            continue
        ctx, refs, pinfo = res
        if not ctx:
            continue
        all_ctx_parts.append(ctx)
        all_refs.extend(refs)
        if pinfo:
            places_info.append(pinfo)

    return "".join(all_ctx_parts), all_refs, places_info
