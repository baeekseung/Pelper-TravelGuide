import requests
from ..config import settings

def naver_reverse_address(lat: float, lng: float):
    url = "https://maps.apigw.ntruss.com/map-reversegeocode/v2/gc?coords=127.585%2C34.9765&output=json&orders=legalcode%2Cadmcode%2Caddr%2Croadaddr"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": settings.naver_map_client_id,
        "X-NCP-APIGW-API-KEY": settings.naver_map_reversegeocode_client_secret,
    }
    params = {
        "request": "coordsToaddr",
        "coords": f"{lng},{lat}",
        "sourcecrs": "epsg:4326",
        "output": "json",
        "orders": "roadaddr,addr,admcode",  # 도로명/지번/행정구역
    }
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    return r.json()


def extract_clean_address(geocoding_result: dict) -> str:
    if geocoding_result.get("status", {}).get("code") != 0:
        return "지오코딩 실패"

    results = geocoding_result.get("results", [])
    if not results:
        return "주소 정보 없음"

    # 각 주소 타입별로 정보 추출
    address_info = {}

    for result in results:
        name = result.get("name", "")
        region = result.get("region", {})

        # 행정구역 정보 추출
        area1 = region.get("area1", {}).get("name", "")  # 시/도
        area2 = region.get("area2", {}).get("name", "")  # 시/군/구
        area3 = region.get("area3", {}).get("name", "")  # 읍/면/동
        area4 = region.get("area4", {}).get("name", "")  # 리

        coords = region.get("area2", {}).get("coords", {}).get("center", {})
        lat = coords.get("y")
        lng = coords.get("x")

        if name == "roadaddr":
            # 도로명주소
            land = result.get("land", {})
            road_name = land.get("name", "")
            building_number = land.get("number1", "")
            building_sub = land.get("number2", "")
            zipcode = land.get("addition1", {}).get("value", "")

            # 도로명주소 조합 (읍까지만)
            road_address = f"{area1} {area2}"
            if area3:
                # area3이 '읍', '면', '동' 중 하나인지 확인
                if area3.endswith("읍") or area3.endswith("면") or area3.endswith("동"):
                    road_address += f" {area3}"
            # area4(리)는 포함하지 않음

            address_info["road_address"] = {
                "full_address": road_address.strip(),
                "road_name": road_name,
                "building_number": building_number,
                "building_sub": building_sub,
                "zipcode": zipcode,
                "coordinates": {"lat": lat, "lng": lng},
            }

        elif name == "addr":
            # 지번주소 (읍까지만)
            land = result.get("land", {})
            land_type = land.get("type", "")
            land_number1 = land.get("number1", "")
            land_number2 = land.get("number2", "")

            land_address = f"{area1} {area2}"
            if area3:
                if area3.endswith("읍") or area3.endswith("면") or area3.endswith("동"):
                    land_address += f" {area3}"
            # area4(리)는 포함하지 않음

            address_info["land_address"] = {
                "full_address": land_address.strip(),
                "land_type": land_type,
                "land_number1": land_number1,
                "land_number2": land_number2,
                "coordinates": {"lat": lat, "lng": lng},
            }

        elif name in ["legalcode", "admcode"]:
            code = result.get("code", {})
            address_info["administrative"] = {
                "area1": area1,
                "area2": area2,
                "area3": area3,
                "area4": area4,
                "code_id": code.get("id", ""),
                "mapping_id": code.get("mappingId", ""),
                "coordinates": {"lat": lat, "lng": lng},
            }

    # 읍/면/동까지만 반환
    if "road_address" in address_info:
        road = address_info["road_address"]
        main_address = road.get('full_address', '').strip()
        address_info["main_address"] = main_address
    elif "land_address" in address_info:
        land = address_info["land_address"]
        main_address = land.get('full_address', '').strip()
        address_info["main_address"] = main_address
    else:
        admin = address_info.get("administrative", {})
        # area3이 읍/면/동이면 포함, 아니면 area1 area2까지만
        area1 = admin.get('area1', '')
        area2 = admin.get('area2', '')
        area3 = admin.get('area3', '')
        main_address = f"{area1} {area2}"
        if area3 and (area3.endswith("읍") or area3.endswith("면") or area3.endswith("동")):
            main_address += f" {area3}"
        address_info["main_address"] = main_address.strip()

    return address_info["main_address"]
