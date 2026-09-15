from fastapi import Request

from app.sport.service import SportService


def get_sport_service(request: Request) -> SportService:
    return request.app.state.sport_service
