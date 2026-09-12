"""FastAPI routers for URL management and redirects."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from cache.redis_client import CacheClient, get_cache
from db.database import get_db
from models.url import URLCreate, URLResponse, URLAnalyticsResponse
from services.analytics_service import AnalyticsService
from services.url_service import URLService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/urls", tags=["urls"])
redirect_router = APIRouter(tags=["redirect"])

_url_service = URLService()
_analytics_service = AnalyticsService()


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@router.post(
    "/",
    response_model=URLResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a shortened URL",
)
async def create_url(
    payload: URLCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> URLResponse:
    original_url = str(payload.url)
    base_url = _base_url(request)
    try:
        return await _url_service.create_url(
            db=db,
            original_url=original_url,
            base_url=base_url,
            custom_alias=payload.custom_alias,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{url_id}", response_model=URLResponse, summary="Get URL details by ID")
async def get_url(
    url_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> URLResponse:
    url_obj = await _url_service.get_by_id(db=db, url_id=url_id)
    if url_obj is None:
        raise HTTPException(status_code=404, detail="URL not found")
    base_url = _base_url(request)
    return URLResponse(
        id=url_obj.id,
        original_url=url_obj.original_url,
        short_code=url_obj.short_code,
        short_url=f"{base_url}/{url_obj.short_code}",
        created_at=url_obj.created_at,
        is_active=url_obj.is_active,
    )


@router.get(
    "/{url_id}/analytics",
    response_model=URLAnalyticsResponse,
    summary="Get analytics for a URL",
)
async def get_analytics(
    url_id: int,
    db: AsyncSession = Depends(get_db),
) -> URLAnalyticsResponse:
    try:
        return await _analytics_service.get_analytics(db=db, url_id=url_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/{url_id}", summary="Deactivate a URL")
async def deactivate_url(
    url_id: int,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    deactivated = await _url_service.deactivate_url(db=db, url_id=url_id)
    if not deactivated:
        raise HTTPException(status_code=404, detail="URL not found")
    return {"message": "URL deactivated", "url_id": url_id}


@redirect_router.get(
    "/{short_code}",
    summary="Redirect to original URL",
    response_class=RedirectResponse,
)
async def redirect_to_url(
    short_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    cache: CacheClient = Depends(get_cache),
) -> RedirectResponse:
    url_obj = await _url_service.get_by_short_code(db=db, cache=cache, short_code=short_code)

    if url_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Short code '{short_code}' not found",
        )

    if not url_obj.is_active:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This URL has been deactivated",
        )

    user_agent = request.headers.get("user-agent")
    referrer = request.headers.get("referer")
    try:
        await _url_service.record_click(
            db=db, url_id=url_obj.id, user_agent=user_agent, referrer=referrer
        )
    except Exception as exc:
        logger.warning("Failed to record click for %s: %s", short_code, exc)

    return RedirectResponse(url=url_obj.original_url, status_code=status.HTTP_302_FOUND)
