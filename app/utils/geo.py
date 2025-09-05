from typing import Optional, Tuple

async def resolve_location(location_text: Optional[str], lat: Optional[float], lng: Optional[float]):
    if lat is not None and lng is not None:
        return (lat, lng, None)
    if location_text:
        # TODO: 네이버 지도 Geocode 연동
        # 임시: 좌표 미해결 시 None 반환
        return (None, None, location_text)
    return (None, None, None)
