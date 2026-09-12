"""Tests for URL analytics endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_analytics_initial(client: AsyncClient) -> None:
    """A freshly created URL has zero clicks."""
    create_resp = await client.post(
        "/api/v1/urls/", json={"url": "https://analytics-initial.example.com/"}
    )
    assert create_resp.status_code == 201
    url_id = create_resp.json()["id"]

    analytics_resp = await client.get(f"/api/v1/urls/{url_id}/analytics")
    assert analytics_resp.status_code == 200
    data = analytics_resp.json()
    assert data["url_id"] == url_id
    assert data["total_clicks"] == 0
    assert data["clicks_today"] == 0
    assert data["recent_clicks"] == []


async def test_analytics_after_redirect(client: AsyncClient) -> None:
    """After one redirect, click count should be 1."""
    create_resp = await client.post(
        "/api/v1/urls/", json={"url": "https://analytics-click.example.com/"}
    )
    assert create_resp.status_code == 201
    url_id = create_resp.json()["id"]
    short_code = create_resp.json()["short_code"]

    redir_resp = await client.get(f"/{short_code}", follow_redirects=False)
    assert redir_resp.status_code == 302

    analytics_resp = await client.get(f"/api/v1/urls/{url_id}/analytics")
    assert analytics_resp.status_code == 200
    data = analytics_resp.json()
    assert data["total_clicks"] == 1
    assert data["clicks_today"] == 1
    assert len(data["recent_clicks"]) == 1


async def test_analytics_multiple_clicks(client: AsyncClient) -> None:
    """Multiple redirects accumulate correctly."""
    create_resp = await client.post(
        "/api/v1/urls/", json={"url": "https://multi-click.example.com/"}
    )
    url_id = create_resp.json()["id"]
    short_code = create_resp.json()["short_code"]

    for _ in range(3):
        await client.get(f"/{short_code}", follow_redirects=False)

    analytics_resp = await client.get(f"/api/v1/urls/{url_id}/analytics")
    assert analytics_resp.json()["total_clicks"] == 3


async def test_analytics_not_found(client: AsyncClient) -> None:
    """Analytics for a non-existent URL returns 404."""
    response = await client.get("/api/v1/urls/99999/analytics")
    assert response.status_code == 404
