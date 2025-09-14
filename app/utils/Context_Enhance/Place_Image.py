import re
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
                    print(f"저장 완료 (리사이즈됨): {fname}")
            except Exception as e:
                print("다운로드 실패:", img_url, e)

        return saved_files
