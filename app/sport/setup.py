from zoneinfo import ZoneInfo

import httpx

from app.core.cache import TTLCache
from app.sport.config import SportSettings
from app.sport.providers.kbo import KBOClient
from app.sport.providers.kleague import KLeagueClient
from app.sport.service import SportService


def create_sport_service(
    http_client: httpx.AsyncClient,
    settings: SportSettings,
) -> SportService:
    timezone_info = ZoneInfo(settings.timezone)
    return SportService(
        kbo_client=KBOClient(http_client, timezone_info),
        kleague_client=KLeagueClient(
            http_client,
            timezone_info=timezone_info,
        ),
        cache=TTLCache(settings.cache_ttl_seconds),
        timezone_info=timezone_info,
    )
