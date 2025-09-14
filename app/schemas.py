from pydantic import BaseModel, Field
from typing import List, Optional

class GuideQuery(BaseModel):
    query: str = Field(..., description="사용자의 요청")
    location_text: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_m: int = 1500
    language: str = "ko"
    max_results: int = 12
    llm_model: str = "gpt-4.1-2025-04-14"
    safe_mode: bool = True

class SourceItem(BaseModel):
    title: str
    url: str
    type: str
    score: float

class LatLng(BaseModel):
    lat: float
    lng: float

class GuideResponse(BaseModel):
    answer: str
    sources: List[SourceItem]
    center: Optional[LatLng] = None
    resolved_address: Optional[str] = None
    meta: dict = {}
