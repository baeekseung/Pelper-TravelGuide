import requests
from ..config import settings

def get_location():
    url = f"https://www.googleapis.com/geolocation/v1/geolocate?key={settings.google_cloud_key}"
    data = {
        "considerIp": True,
    }

    result = requests.post(url, data)

    return result.json()["location"]["lat"], result.json()["location"]["lng"]

