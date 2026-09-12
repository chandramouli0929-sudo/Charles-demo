"""Tests for URL creation, redirect, deactivation, and details endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "url-shortener"


async def test_create_url(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/urls/", json={"url": "https://www.example.com/some/very/long/path"}
    )
    assert response.status_code == 201
    data = response.json()
    assert "short_code" in data
    assert len(data["short_code"]) == 7
    assert "short_url" in data
    assert data["is_active"] is True


async def test_create_same_url_returns_same_code(client: AsyncClient) -> None:
    """Same URL always yields the same short_code (deterministic)."""
    url = "https://www.deterministic-test.com/page"
    r1 = await client.post("/api/v1/urls/", json={"url": url})
    r2 = await client.post("/api/v1/urls/", json={"url": url})
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["short_code"] == r2.json()["short_code"]


async def test_get_url_details(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/api/v1/urls/", json={"url": "https://details-test.example.com/"}
    )
    url_id = create_resp.json()["id"]
    response = await client.get(f"/api/v1/urls/{url_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == url_id
    assert "short_code" in data


async def test_redirect_success(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/api/v1/urls/", json={"url": "https://redirect-target.example.com/"}
    )
    short_code = create_resp.json()["short_code"]
    response = await client.get(f"/{short_code}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://redirect-target.example.com/"


async def test_redirect_not_found(client: AsyncClient) -> None:
    response = await client.get("/zzzzzzz", follow_redirects=False)
    assert response.status_code == 404


async def test_deactivate_url(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/api/v1/urls/", json={"url": "https://deactivate-me.example.com/"}
    )
    url_id = create_resp.json()["id"]
    short_code = create_resp.json()["short_code"]

    del_resp = await client.delete(f"/api/v1/urls/{url_id}")
    assert del_resp.status_code == 200

    redir_resp = await client.get(f"/{short_code}", follow_redirects=False)
    assert redir_resp.status_code == 410


async def test_get_url_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/urls/99999")
    assert response.status_code == 404


async def test_deactivate_url_not_found(client: AsyncClient) -> None:
    response = await client.delete("/api/v1/urls/99999")
    assert response.status_code == 404


async def test_create_url_with_custom_alias(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/urls/",
        json={"url": "https://example.com/custom-test", "custom_alias": "my-custom-link"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["short_code"] == "my-custom-link"
    assert "my-custom-link" in data["short_url"]

    # Verify redirection works with custom alias
    redir = await client.get("/my-custom-link", follow_redirects=False)
    assert redir.status_code == 302
    assert redir.headers["location"] == "https://example.com/custom-test"


async def test_create_url_duplicate_custom_alias(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/urls/",
        json={"url": "https://first.com", "custom_alias": "unique-alias"},
    )
    dup = await client.post(
        "/api/v1/urls/",
        json={"url": "https://different-second.com", "custom_alias": "unique-alias"},
    )
    assert dup.status_code == 400
    assert "already in use" in dup.json()["detail"]


async def test_create_urls_batch(client: AsyncClient) -> None:
    payload = {
        "urls": [
            {"url": "https://batch-one.com", "custom_alias": "b-one"},
            {"url": "https://batch-two.com", "custom_alias": "b-two"},
            {"url": "https://batch-three.com"},
        ]
    }
    response = await client.post("/api/v1/urls/batch", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    assert data["items"][0]["short_code"] == "b-one"
    assert data["items"][1]["short_code"] == "b-two"
    assert len(data["items"][2]["short_code"]) == 7

    # Verify redirection works for batch generated items
    r1 = await client.get("/b-one", follow_redirects=False)
    assert r1.status_code == 302
    assert r1.headers["location"] == "https://batch-one.com"
