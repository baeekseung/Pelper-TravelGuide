import time
import re
import requests
from typing import Dict, Optional, List
import httpx
import os

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    UnexpectedAlertPresentException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from dotenv import load_dotenv


load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

try:
    from webdriver_manager.chrome import ChromeDriverManager

    _HAS_WDM = True
except Exception:
    _HAS_WDM = False


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)

LOAD_WAIT_SEC = 10
SETTLE_SLEEP = 0.8


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


def build_driver(
    headless: bool = True, driver_path: Optional[str] = None
) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,2200")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=ko-KR")
    options.add_argument(f"--user-agent={UA}")

    if driver_path:
        service = Service(driver_path)
        return webdriver.Chrome(service=service, options=options)

    if not _HAS_WDM:
        raise RuntimeError(
            "webdriver-manager 미설치. pip install webdriver-manager 또는 driver_path 지정 필요."
        )
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def _into_mainframe_if_exists(driver: webdriver.Chrome) -> None:
    try:
        WebDriverWait(driver, LOAD_WAIT_SEC).until(
            EC.frame_to_be_available_and_switch_to_it((By.NAME, "mainFrame"))
        )
        return
    except TimeoutException:
        pass

    try:
        frame = driver.find_element(
            By.CSS_SELECTOR, "iframe#mainFrame, frame#mainFrame"
        )
        driver.switch_to.frame(frame)
    except NoSuchElementException:
        return


def _pick_body_block_selenium(driver: webdriver.Chrome) -> Dict[str, str]:
    selectors = [
        "div.se-main-container",  # 신형 - 권주연
        "#postViewArea",  # 구형 - 백승주
        "div#content-area",  # ㄹㅈㄷ 구형 - 할아버지 백승주
        ".se-main-container",  # 클래스 선택자
        ".post_ct",  # 구형 포스트 컨테이너
        "div.post_ct",  # 구형 포스트 컨테이너
        ".se-text-paragraph",  # 신형 텍스트 단락
        "div.se-text",  # 신형 텍스트
        "div[data-module='SE2M_MAIN_CONTAINER']",  # 신형 메인 컨테이너
        "div.se-component-content",  # 신형 컴포넌트 콘텐츠
        "div.se-text-paragraph",  # 신형 텍스트 단락
        "div#postViewArea div",  # 구형 포스트 뷰 내부 div
        "div.se-main-container div",  # 신형 컨테이너 내부 div
        "body",  # 최후의 수단
    ]
    last_exc = None
    for sel in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            text = el.text.strip()
            html = el.get_attribute("innerHTML") or ""
            if text or html:
                return {"selector": sel, "text": text, "html": html}
        except NoSuchElementException as e:
            last_exc = e
            continue
    if last_exc:
        raise last_exc
    raise NoSuchElementException("본문 탐색 실패")


# ---------------- requests 폴백 ----------------
def _normalize_to_mobile(url: str) -> str:
    if "://blog.naver.com/" in url:
        return url.replace("://blog.naver.com/", "://m.blog.naver.com/")
    return url


def _pick_body_block_requests(url: str) -> Dict[str, str]:
    murl = _normalize_to_mobile(url)
    # SSL 인증서 검증 비활성화 및 경고 억제
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    r = requests.get(murl, headers={"User-Agent": UA}, timeout=12, verify=False)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    # 페이지 <title> 추출 시도
    page_title = (soup.title.string or "").strip() if soup.title else ""

    for sel in [
        "div.se-main-container",
        "#postViewArea",
        "div.post_ct, .post_ct",
        "div#content-area",
    ]:
        cont = soup.select_one(sel)
        if cont:
            for bad in cont.select(
                ".se-component.se-share, .spi_layer, script, style, noscript"
            ):
                bad.decompose()
            text = cont.get_text("\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text)
            return {
                "selector": sel,
                "text": text,
                "html": str(cont),
                "title": page_title,
            }

    raise RuntimeError("requests 폴백에서도 본문 컨테이너를 찾지 못했습니다.")


# ---------------- 공개 함수 ----------------
def extract_blog_content(url: str, driver: webdriver.Chrome) -> Dict[str, str]:
    """
    링크에서 본문 블록 추출
    1. Selenium -> mainFrame 진입 -> 본문 찾기
    2. 실패하면 requests + BS4 폴백
    """
    try:
        driver.get(url)
        try:
            WebDriverWait(driver, LOAD_WAIT_SEC).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            pass
        time.sleep(SETTLE_SLEEP)
        _into_mainframe_if_exists(driver)
        time.sleep(SETTLE_SLEEP)

        block = _pick_body_block_selenium(driver)
        # Selenium에서 문서 제목 사용
        page_title = (driver.title or "").strip()
        return {
            "url": url,
            "selector": block["selector"],
            "text": block["text"],
            "html": block["html"],
            "title": page_title,
        }

    except (
        NoSuchElementException,
        TimeoutException,
        UnexpectedAlertPresentException,
    ) as e:
        print(f"Selenium 실패, requests 폴백 시도: {e}")
        try:
            fb = _pick_body_block_requests(url)
            return {
                "url": url,
                "selector": fb.get("selector", ""),
                "text": fb.get("text", ""),
                "html": fb.get("html", ""),
                "title": fb.get("title", ""),
            }
        except Exception as fallback_error:
            print(f"requests 폴백도 실패: {fallback_error}")
            return {
                "url": url,
                "selector": "error",
                "text": f"콘텐츠 추출 실패: {str(fallback_error)}",
                "html": "",
                "title": "",
            }


def naver_blog_search(query: str, k: int = 3, sort: str = "date") -> List[str]:
    BASE = "https://openapi.naver.com/v1/search/blog.json"
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


if __name__ == "__main__":
    target = input("블로그 링크: ").strip()
    drv = build_driver(headless=True)
    try:
        data = extract_blog_content(target, drv)
        print("[SELECTOR]", data["selector"])
        print("\n[본문 전체]\n")
        print(data["text"])
    finally:
        drv.quit()
