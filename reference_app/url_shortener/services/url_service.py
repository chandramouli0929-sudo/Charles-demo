"""Business logic for URL creation, retrieval, and click recording."""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cache.redis_client import CacheClient
from models.click import Click
from models.url import URL, URLResponse

logger = logging.getLogger(__name__)

# Base-62 alphabet (0-9, a-z, A-Z)
_BASE62_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


class URLService:
    """Service encapsulating all URL-shortener business logic."""

    @staticmethod
    def _generate_short_code(url: str, length: int = 7) -> str:
        """
        Deterministically generate a base-62 short code from a URL.

        Uses SHA-256 of the URL bytes, interprets the digest as a big integer,
        and encodes it in base-62. The same URL always produces the same code.
        This eliminates the 'different short code after restart' bug.
        """
        digest = hashlib.sha256(url.encode("utf-8")).digest()
        number = int.from_bytes(digest, byteorder="big")

        chars: list[str] = []
        base = len(_BASE62_CHARS)
        while number > 0 and len(chars) < length:
            chars.append(_BASE62_CHARS[number % base])
            number //= base

        while len(chars) < length:
            chars.append("0")

        return "".join(reversed(chars))

    async def create_url(
        self,
        db: AsyncSession,
        original_url: str,
        base_url: str,
        custom_alias: Optional[str] = None,
    ) -> URLResponse:
        """
        Create a shortened URL (supports user-defined custom alias or deterministic base-62 generation).
        """
        if custom_alias and custom_alias.strip():
            short_code = custom_alias.strip()
            # Check if this custom alias already exists
            result = await db.execute(select(URL).where(URL.short_code == short_code))
            existing = result.scalar_one_or_none()
            if existing is not None:
                if existing.original_url == original_url:
                    return URLResponse(
                        id=existing.id,
                        original_url=existing.original_url,
                        short_code=existing.short_code,
                        short_url=f"{base_url}/{existing.short_code}",
                        created_at=existing.created_at,
                        is_active=existing.is_active,
                    )
                raise ValueError(f"Custom alias '{short_code}' is already in use. Please choose another one.")
        else:
            short_code = self._generate_short_code(original_url)
            # Check for existing record
            result = await db.execute(select(URL).where(URL.short_code == short_code))
            existing = result.scalar_one_or_none()
            if existing is not None:
                logger.debug("Short code %r already exists — returning existing record", short_code)
                return URLResponse(
                    id=existing.id,
                    original_url=existing.original_url,
                    short_code=existing.short_code,
                    short_url=f"{base_url}/{existing.short_code}",
                    created_at=existing.created_at,
                    is_active=existing.is_active,
                )

        url_obj = URL(original_url=original_url, short_code=short_code)
        db.add(url_obj)
        await db.flush()
        await db.refresh(url_obj)

        return URLResponse(
            id=url_obj.id,
            original_url=url_obj.original_url,
            short_code=url_obj.short_code,
            short_url=f"{base_url}/{url_obj.short_code}",
            created_at=url_obj.created_at,
            is_active=url_obj.is_active,
        )

    async def get_by_short_code(
        self,
        db: AsyncSession,
        cache: CacheClient,
        short_code: str,
    ) -> Optional[URL]:
        """Cache-aside: check cache first, then DB."""
        cache_key = f"url:short:{short_code}"
        cached_id = await cache.get(cache_key)
        if cached_id is not None:
            result = await db.execute(select(URL).where(URL.id == int(cached_id)))
            url_obj = result.scalar_one_or_none()
            if url_obj is not None:
                return url_obj

        result = await db.execute(select(URL).where(URL.short_code == short_code))
        url_obj = result.scalar_one_or_none()

        if url_obj is not None:
            await cache.set(cache_key, str(url_obj.id))

        return url_obj

    async def get_by_id(self, db: AsyncSession, url_id: int) -> Optional[URL]:
        result = await db.execute(select(URL).where(URL.id == url_id))
        return result.scalar_one_or_none()

    async def deactivate_url(self, db: AsyncSession, url_id: int) -> bool:
        url_obj = await self.get_by_id(db, url_id)
        if url_obj is None:
            return False
        url_obj.is_active = False
        await db.flush()
        return True

    async def record_click(
        self,
        db: AsyncSession,
        url_id: int,
        user_agent: Optional[str],
        referrer: Optional[str],
    ) -> None:
        click = Click(url_id=url_id, user_agent=user_agent, referrer=referrer)
        db.add(click)
        await db.flush()
