import pathlib
import os
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Template
from app.schemas import GuideQuery, GuideResponse, LatLng
from app.services.naver_client import NaverClient, pick_top
from app.services.rag_chain import run_chain
from app.utils.geo import resolve_location
from app.utils.Loaction_getter import get_location
from app.utils.Refine_query import refine_query
from app.utils.Build_context import build_context

app = FastAPI(title="PELPER-Travel-Guide", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙 설정 (이미지 폴더)
app.mount("/images", StaticFiles(directory="images"), name="images")

current_location = {"lat": 37.5665, "lng": 126.9780}  # 기본값: 서울 시청


# 사용자의 현재 위치를 current_location에 저장
async def get_startup_location():
    global current_location
    try:
        loop = asyncio.get_event_loop()
        lat, lng = await loop.run_in_executor(None, get_location)
        current_location = {"lat": lat, "lng": lng}
        print(f"사용자 GPS 위치 설정됨: {lat}, {lng}")
    except Exception as e:
        print(f"사용자 GPS 위치 가져오기 실패: {e}")
        print("기본 위치(서울 시청)를 사용합니다.")


@app.on_event("startup")
async def startup_event():
    await get_startup_location()


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


# Frontend에서 사용자의 위도 경도를 반환
@app.get("/v1/location/current")
async def get_current_location():
    return {
        "lat": current_location["lat"],
        "lng": current_location["lng"],
        "status": "success",
    }


@app.post("/v1/guide/query", response_model=GuideResponse)
async def guide_query(body: GuideQuery):
    # 텍스트 주소, 위도, 경도 정보가 없을때
    if not body.location_text and (body.lat is None or body.lng is None):
        raise HTTPException(
            status_code=400,
            detail="위치 정보(location_text 또는 lat/lng)가 필요합니다.",
        )

    lat, lng, address_data = await resolve_location(
        body.location_text, body.lat, body.lng
    )

    if isinstance(address_data, dict):
        resolved_address = address_data.get("main_address", None)
    else:
        resolved_address = address_data

    client = NaverClient()

    q = await refine_query(resolved_address, body.query)

    local = await client.search_local(q, display=min(10, body.max_results))
    local_top = pick_top(local, kind="place", k=5)

    place_list = []
    for item in local_top:
        place_list.append(item["title"])
    print("places", place_list)

    collected, reference_link, places_info = await build_context(
        place_list, resolved_address
    )

    answer = await run_chain(body.query, collected, model_name=body.llm_model)

    # 사용자 위치를 center로 사용 (geocoding된 주소 좌표)
    center = LatLng(lat=lat, lng=lng) if lat is not None and lng is not None else None

    print(f"응답에 포함될 장소 정보: {places_info}")

    return GuideResponse(
        answer=answer,
        sources=reference_link,
        center=center,
        resolved_address=resolved_address,
        places=places_info,
        meta={},
    )


WEB_INDEX = pathlib.Path(__file__).parent / "web" / "index.html"
if WEB_INDEX.exists():
    INDEX_HTML = WEB_INDEX.read_text(encoding="utf-8")
else:
    INDEX_HTML = """<!doctype html><html><body>
    <h3>index.html이 없습니다.</h3>
    <p>경로: app/web/index.html 파일을 생성해 주세요.</p>
    </body></html>"""


@app.get("/", response_class=HTMLResponse)
async def index(_: Request):
    map_client_id = os.getenv("NAVER_MAP_CLIENT_ID", "")
    html = Template(INDEX_HTML).render(NAVER_MAP_CLIENT_ID=map_client_id)
    return HTMLResponse(content=html)
