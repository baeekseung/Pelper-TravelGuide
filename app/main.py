from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .schemas import GuideQuery, GuideResponse, SourceItem, LatLng
from .services.naver_client import NaverClient, pick_top
from .services.rag_chain import run_chain
from .utils.geo import resolve_location

app = FastAPI(title="Location-based Travel Guide API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.post("/v1/guide/query", response_model=GuideResponse)
async def guide_query(body: GuideQuery):
    if not body.location_text and (body.lat is None or body.lng is None):
        raise HTTPException(status_code=400, detail="위치 정보(location_text 또는 lat/lng)가 필요합니다.")

    lat, lng, unresolved = await resolve_location(body.location_text, body.lat, body.lng)

    client = NaverClient()

    # 1) 쿼리 보정(간단): 위치 키워드를 포함
    q = body.query
    if body.location_text:
        q = f"{body.location_text} {body.query}"

    # 2) 네이버 검색 호출
    web   = await client.search_web(q, display=min(10, body.max_results))
    blog  = await client.search_blog(q, display=min(10, body.max_results))
    local = await client.search_local(q, display=min(10, body.max_results))

    # 3) 상위 결과 정리
    collected = pick_top(web, "web", k=5) + pick_top(blog, "blog", k=4) + pick_top(local, "place", k=4)

    # 4) LLM 요약/가이드 생성
    answer = await run_chain(body.query, collected, model_name=body.llm_model)

    sources = [SourceItem(**c, score=1.0) for c in collected]  # 점수/거리 리랭킹은 추후 개선
    center = LatLng(lat=lat, lng=lng) if lat is not None and lng is not None else None

    return GuideResponse(
        answer=answer,
        sources=sources,
        center=center,
        resolved_address=None if unresolved is None else unresolved,
        meta={}
    )
