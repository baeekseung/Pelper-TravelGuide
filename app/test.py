import requests
from dotenv import load_dotenv
import os

load_dotenv()

client_id = os.getenv("NAVER_MAP_CLIENT_ID")
client_secret = os.getenv("NAVER_MAP_REVERSEGEO_CLIENT_KEY")

def geocode_address(address):
    url = f"https://maps.apigw.ntruss.com/map-geocode/v2/geocode?query={address}"
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