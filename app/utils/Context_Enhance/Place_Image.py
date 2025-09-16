import re
import asyncio
import os
import urllib.parse
import httpx
from bs4 import BeautifulSoup
from PIL import Image
import io

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


def _resize_image(
    image_data: bytes, max_width: int = 800, max_height: int = 600, quality: int = 85
) -> bytes:
    """이미지를 리사이즈하고 최적화합니다."""
    try:
        # 이미지 열기
        image = Image.open(io.BytesIO(image_data))

        # 원본 크기
        original_width, original_height = image.size

        # 비율을 유지하면서 리사이즈 계산
        ratio = min(max_width / original_width, max_height / original_height)

        # 이미지가 이미 작으면 리사이즈하지 않음
        if ratio >= 1:
            new_width, new_height = original_width, original_height
        else:
            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)

        # 리사이즈
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # RGB로 변환 (JPEG 저장을 위해)
        if resized_image.mode in ("RGBA", "LA", "P"):
            resized_image = resized_image.convert("RGB")

        # 바이트로 저장
        output = io.BytesIO()
        resized_image.save(output, format="JPEG", quality=quality, optimize=True)
        return output.getvalue()

    except Exception as e:
        print(f"이미지 리사이즈 실패: {e}")
        return image_data  # 실패시 원본 반환


_IMG_SEM = asyncio.Semaphore(int(os.getenv("IMAGE_FETCH_CONCURRENCY", "3")))


async def _get_with_retry(
    session: httpx.AsyncClient, url: str, tries: int = 3, timeout: float = 15.0
):
    last_exc = None
    for i in range(tries):
        try:
            r = await session.get(url, timeout=timeout)
            if r.status_code == 200:
                return r
            last_exc = RuntimeError(f"status {r.status_code}")
        except Exception as e:
            last_exc = e
        await asyncio.sleep(0.25 * (2**i))
    if last_exc:
        raise last_exc
    raise RuntimeError("unknown error")


async def fetch_and_save_images(
    query: str,
    save_dir: str = "./images",
    skip: int = 2,
    limit: int = 3,
    save_name: str = "",
    max_width: int = 200,
    max_height: int = 200,
    quality: int = 85,
):
    async with _IMG_SEM:
        save_result = False
        os.makedirs(save_dir, exist_ok=True)
        url = (
            "https://search.naver.com/search.naver?"
            f"where=nexearch&sm=top_hty&query={urllib.parse.quote(query)}"
        )
        async with httpx.AsyncClient(
            headers=HDRS, follow_redirects=True, timeout=15.0
        ) as s:
            try:
                r = await _get_with_retry(s, url, tries=3, timeout=15.0)
            except Exception as e:
                print("검색 실패", e)
                r = None
            html = r.text if r else ""

            # 이미지 URL 후보 추출
            cand = [u for u in _RE_IMG.findall(html) if not _RE_BAD.search(u)]
            img_urls = _dedup(cand, k=limit, skip=skip)

            saved_files = []
            for i, img_url in enumerate(img_urls, 1):
                try:
                    resp = await _get_with_retry(s, img_url, tries=3, timeout=12.0)
                    resized_data = _resize_image(
                        resp.content,
                        max_width=max_width,
                        max_height=max_height,
                        quality=quality,
                    )
                    ext = ".jpg"
                    fname = os.path.join(save_dir, f"{save_name}_{i}{ext}")
                    with open(fname, "wb") as f:
                        f.write(resized_data)
                    saved_files.append(fname)
                    save_result = True
                except Exception as e:
                    pass

            # 폴백: 검색 파싱으로 못 찾은 경우, 네이버 플레이스 사진탭에서 시도
            if not saved_files:
                try:
                    from app.services.naver_place import (
                        fetch_place_details as _fetch_place_details,
                    )

                    # place_query는 검색 질의 그대로 사용
                    details = await _fetch_place_details(
                        f"https://map.naver.com/v5/search/{urllib.parse.quote(query)}",
                        limit=limit,
                        timeout_ms=20000,
                        mode="classic",
                    )
                    photos = details.get("photos_top", [])
                    for i, img_url in enumerate(photos, 1):
                        try:
                            resp = await _get_with_retry(
                                s, img_url, tries=3, timeout=12.0
                            )
                            resized_data = _resize_image(
                                resp.content,
                                max_width=max_width,
                                max_height=max_height,
                                quality=quality,
                            )
                            ext = ".jpg"
                            fname = os.path.join(save_dir, f"{save_name}_{i}{ext}")
                            with open(fname, "wb") as f:
                                f.write(resized_data)
                            saved_files.append(fname)
                            save_result = True
                        except Exception as e:
                            pass
                except Exception as fe:
                    pass

            return saved_files, save_result
