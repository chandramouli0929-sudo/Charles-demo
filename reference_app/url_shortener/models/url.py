"""SQLAlchemy ORM model and Pydantic schemas for URLs."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, HttpUrl
from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class URL(Base):
    """ORM model for the urls table."""

    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    short_code: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── Pydantic schemas ──────────────────────────────────────────────────────────


class URLCreate(BaseModel):
    """Input schema for creating a shortened URL."""
    url: HttpUrl
    custom_alias: Optional[str] = None


class URLResponse(BaseModel):
    """Response schema for a shortened URL."""
    id: int
    original_url: str
    short_code: str
    short_url: str
    created_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class ClickRecordBrief(BaseModel):
    """Minimal click record used inside analytics."""
    id: int
    url_id: int
    clicked_at: datetime
    user_agent: Optional[str] = None
    referrer: Optional[str] = None

    model_config = {"from_attributes": True}


class URLAnalyticsResponse(BaseModel):
    """Analytics response schema."""
    url_id: int
    short_code: str
    original_url: str
    total_clicks: int
    clicks_today: int
    recent_clicks: List[ClickRecordBrief]
