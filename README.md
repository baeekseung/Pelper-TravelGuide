# TravelGuide-Service

여행 가이드 서비스를 위한 FastAPI 애플리케이션입니다.

## 환경 설정

프로젝트를 실행하기 전에 다음 환경변수들을 설정해야 합니다:

### 1. .env 파일 생성
프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 다음 내용을 추가하세요:

```env
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key_here

# Naver API Keys
NAVER_CLIENT_ID=your_naver_client_id_here
NAVER_CLIENT_SECRET=your_naver_client_secret_here

# Naver Map API Keys
NAVER_MAP_CLIENT_ID=your_naver_map_client_id_here
NAVER_MAP_CLIENT_SECRET=your_naver_map_client_secret_here

# Default Locale
DEFAULT_LOCALE=ko_KR
```

### 2. API 키 발급 방법

#### OpenAI API Key
1. [OpenAI Platform](https://platform.openai.com/)에서 계정 생성
2. API Keys 섹션에서 새 키 생성

#### Naver API Keys
1. [Naver Cloud Platform](https://www.ncloud.com/)에서 계정 생성
2. Application 등록 후 Client ID와 Client Secret 발급

#### Naver Map API Keys
1. [Naver Cloud Platform](https://www.ncloud.com/)에서 계정 생성
2. Maps API 서비스 신청
3. Application 등록 후 API Key ID와 Secret Key 발급

## 설치 및 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 애플리케이션 실행
python -m app.main
```

## 보안 주의사항

- `.env` 파일은 절대 Git에 커밋하지 마세요
- API 키는 환경변수로만 관리하고 코드에 하드코딩하지 마세요
- 프로덕션 환경에서는 더 안전한 키 관리 시스템을 사용하세요
