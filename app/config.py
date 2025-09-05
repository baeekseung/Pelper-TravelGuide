from pydantic import BaseModel
import os

from dotenv import load_dotenv
load_dotenv()

class Settings(BaseModel):
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    naver_client_id: str = os.getenv("NAVER_CLIENT_ID", "")
    naver_client_secret: str = os.getenv("NAVER_CLIENT_SECRET", "")
    default_locale: str = os.getenv("DEFAULT_LOCALE", "ko_KR")

settings = Settings()