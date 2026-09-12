"""Redis cache client with in-memory fallback."""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "true").lower() in ("true", "1", "yes")

_cache_instance: Optional["CacheClient"] = None


class _InMemoryStore:
    """Simple in-process dict with best-effort TTL (checked on read)."""

    def __init__(self) -> None:
        self._store: Dict[str, Tuple[str, Optional[float]]] = {}

    def get(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: str, ttl: int = 3600) -> None:
        expires_at = time.monotonic() + ttl if ttl > 0 else None
        self._store[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


class CacheClient:
    """Async cache client. Uses Redis when available; falls back to in-memory."""

    def __init__(self, redis_client=None) -> None:
        self._redis = redis_client
        self._memory = _InMemoryStore() if redis_client is None else None

    async def get(self, key: str) -> Optional[str]:
        if self._redis is not None:
            try:
                value = await self._redis.get(key)
                return value.decode("utf-8") if isinstance(value, bytes) else value
            except Exception as exc:
                logger.warning("Redis GET error: %s — falling back to miss", exc)
                return None
        assert self._memory is not None
        return self._memory.get(key)

    async def set(self, key: str, value: str, ttl: int = 3600) -> None:
        if self._redis is not None:
            try:
                await self._redis.set(key, value, ex=ttl)
            except Exception as exc:
                logger.warning("Redis SET error: %s", exc)
            return
        assert self._memory is not None
        self._memory.set(key, value, ttl)

    async def delete(self, key: str) -> None:
        if self._redis is not None:
            try:
                await self._redis.delete(key)
            except Exception as exc:
                logger.warning("Redis DELETE error: %s", exc)
            return
        assert self._memory is not None
        self._memory.delete(key)

    async def ping(self) -> bool:
        if self._redis is not None:
            try:
                await self._redis.ping()
                return True
            except Exception:
                return False
        return False


async def get_cache() -> CacheClient:
    """Singleton factory. Tries Redis first, falls back to in-memory."""
    global _cache_instance
    if _cache_instance is not None:
        return _cache_instance

    if REDIS_ENABLED:
        try:
            import redis.asyncio as aioredis  # type: ignore[import]
            client = aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
            await client.ping()
            logger.info("Connected to Redis at %s", REDIS_URL)
            _cache_instance = CacheClient(redis_client=client)
            return _cache_instance
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — using in-memory cache", exc)

    _cache_instance = CacheClient(redis_client=None)
    return _cache_instance
