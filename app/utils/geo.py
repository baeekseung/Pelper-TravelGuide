from typing import Optional, Tuple
import requests
from ..config import settings
from .Reverse_Geocoding import extract_clean_address, naver_reverse_address


def naver_reverse_address(lat: float, lng: float):
    url = "https://maps.apigw.ntruss.com/map-reversegeocode/v2/gc?coords=127.585%2C34.9765&output=json&orders=legalcode%2Cadmcode%2Caddr%2Croadaddr"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": settings.naver_map_client_id,
        "X-NCP-APIGW-API-KEY": settings.naver_map_reversegeocode_client_secret,
    }
    params = {
        "request": "coordsToaddr",
        "coords": f"{lng},{lat}",  # 경도,위도 순서 유의!
        "sourcecrs": "epsg:4326",
        "output": "json",
        "orders": "roadaddr,addr,admcode",  # 도로명/지번/행정구역
    }
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json()


async def resolve_location(
    location_text: Optional[str], lat: Optional[float], lng: Optional[float]
):
    if lat is not None and lng is not None:
        adress_json = naver_reverse_address(lat, lng)
        address = extract_clean_address(adress_json)
        return (lat, lng, address)
    if location_text:
        # TODO: 네이버 지도 Geocode 연동
        # 임시: 좌표 미해결 시 None 반환
        return (None, None, location_text)
    return (None, None, None)
