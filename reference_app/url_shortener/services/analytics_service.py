"""Analytics service for URL click statistics."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.click import Click, ClickRecord
from models.url import URL, URLAnalyticsResponse

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Provides analytics queries over the clicks table."""

    async def get_analytics(self, db: AsyncSession, url_id: int) -> URLAnalyticsResponse:
        """Return aggregated analytics for a URL."""
        url_result = await db.execute(select(URL).where(URL.id == url_id))
        url_obj = url_result.scalar_one_or_none()
        if url_obj is None:
            raise ValueError(f"URL with id={url_id} not found")

        total_result = await db.execute(
            select(func.count(Click.id)).where(Click.url_id == url_id)
        )
        total_clicks: int = total_result.scalar_one() or 0

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_result = await db.execute(
            select(func.count(Click.id)).where(
                Click.url_id == url_id,
                Click.clicked_at >= today_start,
            )
        )
        clicks_today: int = today_result.scalar_one() or 0

        recent_result = await db.execute(
            select(Click)
            .where(Click.url_id == url_id)
            .order_by(Click.clicked_at.desc())
            .limit(10)
        )
        recent_clicks_orm = recent_result.scalars().all()
        recent_clicks = [ClickRecord.model_validate(c) for c in recent_clicks_orm]

        return URLAnalyticsResponse(
            url_id=url_id,
            short_code=url_obj.short_code,
            original_url=url_obj.original_url,
            total_clicks=total_clicks,
            clicks_today=clicks_today,
            recent_clicks=recent_clicks,
        )

    async def get_click_trend(
        self, db: AsyncSession, url_id: int, days: int = 7
    ) -> List[dict]:
        """Return daily click counts for the last N days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(Click.clicked_at).where(
                Click.url_id == url_id,
                Click.clicked_at >= cutoff,
            )
        )
        rows = result.scalars().all()

        counts: dict[str, int] = {}
        today = datetime.utcnow().date()
        for i in range(days):
            day = today - timedelta(days=days - 1 - i)
            counts[day.isoformat()] = 0

        for clicked_at in rows:
            day_str = clicked_at.date().isoformat()
            if day_str in counts:
                counts[day_str] += 1

        return [{"date": d, "count": c} for d, c in sorted(counts.items())]
