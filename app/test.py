import requests
from dotenv import load_dotenv
import os

load_dotenv()
client_id = os.getenv("NAVER_CLIENT_ID")
client_secret = os.getenv("NAVER_CLIENT_SECRET")

# 고정 문자열 주소
address = '충청북도 청주시 흥덕구 산단로 54 한국폴리텍대학 청주캠퍼스'

# 네이버 Geocoding API 호출 함수 정의
def geocode_address(address):
    url = f"https://naveropenapi.apigw.ntruss.com/map-geocode/v2/geocode?query={address}"
    headers = {
        'X-NCP-APIGW-API-KEY-ID': client_id,
        'X-NCP-APIGW-API-KEY': client_secret
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data['addresses']:
            location = data['addresses'][0]
            return location['y'], location['x']
        else:
            return None, None
    else:
        print(f"Error {response.status_code}: {response.text}")
        return None, None

# 주소를 좌표로 변환
latitude, longitude = geocode_address(address)

# 결과 출력
if latitude and longitude:
    print(f"주소: {address}")
    print(f"위도: {latitude}")
    print(f"경도: {longitude}")
else:
    print("좌표를 찾을 수 없습니다.")