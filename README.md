# api.dalae37.com

[DaLae37's API](https://api.dalae37.com)의 소스 코드

![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688?logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Language-Python_3.12-3776AB?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Container-Docker-2496ED?logo=docker&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=githubactions&logoColor=white)

## Docker

Sport API 이미지 :

```text
ghcr.io/dalae37/sport-api-dalae37-com
```

## 환경 변수

- `CACHE_TTL_SECONDS` : 응답 캐시 시간 (기본값 `600`초)
- `TIMEZONE` : API 기준 시간대 (기본값 `Asia/Seoul`)

## 개발 환경

이 프로젝트는 아래 경을 사용해서 개발됨

* **Python:** 3.12 이상
* **FastAPI:** 0.115 이상
* **HTTP Client:** httpx
* **Data Model:** Pydantic
* **Container:** Docker

## 라이선스 (License)

[BSD 3-Clause](LICENSE)
