from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    ProviderDataNotFoundError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    UnexpectedProviderResponseError,
)
from app.sport.config import SportSettings, get_sport_settings
from app.sport.router import router as sport_router
from app.sport.setup import create_sport_service


def create_app(settings: SportSettings | None = None) -> FastAPI:
    resolved_settings = settings or get_sport_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        timeout = httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=5.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Accept": "application/json, text/html;q=0.9",
                "User-Agent": "SportAPI/1.0 (+official-site-client)",
            },
        ) as http_client:
            application.state.sport_service = create_sport_service(
                http_client,
                resolved_settings,
            )
            yield

    application = FastAPI(
        title="api.dalae37.com /sport",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.include_router(sport_router)

    @application.get("/healthz", tags=["Health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @application.exception_handler(ProviderTimeoutError)
    async def provider_timeout_handler(
        request: Request,
        exc: ProviderTimeoutError,
    ) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=504,
            content={"detail": "Time out error occurs"},
        )

    @application.exception_handler(ProviderUnavailableError)
    @application.exception_handler(UnexpectedProviderResponseError)
    @application.exception_handler(ProviderDataNotFoundError)
    async def provider_failure_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        del request, exc
        return JSONResponse(
            status_code=502,
            content={"detail": "Can't fetch data from the provider"},
        )

    return application


app = create_app()
