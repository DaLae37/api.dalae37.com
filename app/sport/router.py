from typing import Annotated

from fastapi import APIRouter, Depends

from app.sport.dependencies import get_sport_service
from app.sport.models import TeamSnapshot
from app.sport.service import SportService


router = APIRouter(prefix="/sport", tags=["Sport"])


@router.get("/kbo/samsunglions", response_model=TeamSnapshot)
async def get_samsung_lions(
    service: Annotated[SportService, Depends(get_sport_service)],
) -> TeamSnapshot:
    return await service.get_samsung_lions()


@router.get("/kleague/fcseoul", response_model=TeamSnapshot)
async def get_fc_seoul(
    service: Annotated[SportService, Depends(get_sport_service)],
) -> TeamSnapshot:
    return await service.get_fc_seoul()

