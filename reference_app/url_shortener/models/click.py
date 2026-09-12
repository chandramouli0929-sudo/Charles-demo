"""SQLAlchemy ORM model and Pydantic schema for click-tracking."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class Click(Base):
    """ORM model for the clicks table."""

    __tablename__ = "clicks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("urls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now()
    )
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    referrer: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)


class ClickRecord(BaseModel):
    """Response schema for a single click record."""
    id: int
    url_id: int
    clicked_at: datetime
    user_agent: Optional[str] = None
    referrer: Optional[str] = None

    model_config = {"from_attributes": True}
