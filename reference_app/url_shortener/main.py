"""URL Shortener FastAPI application entry point."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict

# Ensure local modules (api, db, models, services) resolve regardless of current working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from api.urls import redirect_router, router as urls_router
from db.database import create_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="URL Shortener API",
    description=(
        "A production-ready URL shortening service built with FastAPI, "
        "SQLAlchemy 2.0 async, and Redis caching."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AgentForge URL Shortener</title>
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --heading: #f0f6fc;
      --accent: #238636;
      --accent-hover: #2ea043;
      --primary: #58a6ff;
      --muted: #8b949e;
      --card-highlight: #21262d;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      display: flex;
      flex-direction: column;
      align-items: center;
      min-height: 100vh;
      padding: 40px 20px;
    }
    .container {
      width: 100%;
      max-width: 680px;
    }
    header {
      text-align: center;
      margin-bottom: 32px;
    }
    .badge {
      display: inline-block;
      padding: 4px 12px;
      font-size: 12px;
      font-weight: 600;
      color: #3fb950;
      background: rgba(63, 185, 80, 0.15);
      border: 1px solid rgba(63, 185, 80, 0.3);
      border-radius: 20px;
      margin-bottom: 12px;
    }
    h1 {
      font-size: 32px;
      font-weight: 700;
      color: var(--heading);
      letter-spacing: -0.5px;
    }
    p.subtitle {
      color: var(--muted);
      margin-top: 8px;
      font-size: 15px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 24px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }
    .input-group {
      display: flex;
      gap: 12px;
    }
    input[type="url"] {
      flex: 1;
      background: #0d1117;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 16px;
      font-size: 15px;
      color: var(--heading);
      outline: none;
      transition: border-color 0.2s;
    }
    input[type="url"]:focus {
      border-color: var(--primary);
    }
    button {
      background: var(--accent);
      color: #ffffff;
      border: none;
      border-radius: 8px;
      padding: 12px 24px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      transition: background-color 0.2s;
      white-space: nowrap;
    }
    button:hover {
      background: var(--accent-hover);
    }
    .result-box {
      margin-top: 20px;
      padding: 16px;
      background: var(--card-highlight);
      border: 1px solid #388bfd40;
      border-radius: 8px;
      display: none;
    }
    .result-header {
      font-size: 13px;
      text-transform: uppercase;
      font-weight: 700;
      color: var(--primary);
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .short-link-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: #0d1117;
      padding: 10px 14px;
      border-radius: 6px;
      border: 1px solid var(--border);
      margin-bottom: 12px;
    }
    .short-url-text {
      color: #58a6ff;
      font-size: 16px;
      font-weight: 600;
      text-decoration: none;
      word-break: break-all;
    }
    .short-url-text:hover {
      text-decoration: underline;
    }
    .action-btns {
      display: flex;
      gap: 8px;
    }
    .btn-secondary {
      background: #21262d;
      border: 1px solid var(--border);
      color: var(--text);
      padding: 6px 14px;
      font-size: 13px;
    }
    .btn-secondary:hover {
      background: #30363d;
    }
    .btn-visit {
      background: #1f6feb;
      color: white;
      text-decoration: none;
      padding: 6px 14px;
      font-size: 13px;
      border-radius: 6px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
    }
    .btn-visit:hover {
      background: #388bfd;
    }
    .meta-details {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-top: 14px;
      text-align: center;
    }
    .meta-item {
      background: #0d1117;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px;
    }
    .meta-label {
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      font-weight: 600;
    }
    .meta-val {
      font-size: 16px;
      color: var(--heading);
      font-weight: 700;
      margin-top: 4px;
    }
    .footer-links {
      text-align: center;
      margin-top: 20px;
      font-size: 13px;
      color: var(--muted);
    }
    .footer-links a {
      color: var(--primary);
      text-decoration: none;
      margin: 0 8px;
    }
    .footer-links a:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="badge">● AgentForge Live Engine</div>
      <h1>URL Shortener</h1>
      <p class="subtitle">Enter any long URL below to generate a fast, persistent short link and track real-time clicks.</p>
    </header>

    <div class="card">
      <form id="shortenForm" onsubmit="handleShorten(event)">
        <div class="input-group">
          <input type="url" id="longUrl" placeholder="https://example.com/very/long/url..." required autofocus />
          <button type="submit" id="submitBtn">Shorten URL</button>
        </div>
      </form>

      <div id="resultBox" class="result-box">
        <div class="result-header">
          <span>Shortened Link Created</span>
          <span id="activeBadge" style="color: #3fb950;">● Active</span>
        </div>
        <div class="short-link-row">
          <a id="shortLinkTag" class="short-url-text" target="_blank" href="#"></a>
          <div class="action-btns">
            <button class="btn-secondary" onclick="copyLink()">📋 Copy</button>
            <a id="visitBtn" class="btn-visit" target="_blank" href="#">↗ Open</a>
          </div>
        </div>

        <div class="meta-details">
          <div class="meta-item">
            <div class="meta-label">Short Code</div>
            <div class="meta-val" id="metaCode">-</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">Total Clicks</div>
            <div class="meta-val" id="metaClicks">0</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">URL ID</div>
            <div class="meta-val" id="metaId">-</div>
          </div>
        </div>
        <div style="text-align: right; margin-top: 10px;">
          <button class="btn-secondary" onclick="refreshAnalytics()" style="padding: 4px 10px; font-size: 12px;">🔄 Refresh Clicks</button>
        </div>
      </div>
    </div>

    <div class="footer-links">
      <a href="/docs" target="_blank">Swagger API Docs</a> • 
      <a href="/health" target="_blank">Health Check</a> • 
      <a href="http://localhost:8501" target="_blank">AgentForge Control Center</a>
    </div>
  </div>

  <script>
    let currentUrlId = null;
    let currentShortUrl = "";

    async function handleShorten(e) {
      e.preventDefault();
      const input = document.getElementById('longUrl');
      const submitBtn = document.getElementById('submitBtn');
      const url = input.value.trim();
      if (!url) return;

      submitBtn.disabled = true;
      submitBtn.innerText = "Shortening...";

      try {
        const resp = await fetch('/api/v1/urls/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url })
        });
        if (!resp.ok) throw new Error("HTTP error " + resp.status);
        const data = await resp.json();

        currentUrlId = data.id;
        currentShortUrl = data.short_url;

        document.getElementById('shortLinkTag').href = data.short_url;
        document.getElementById('shortLinkTag').innerText = data.short_url;
        document.getElementById('visitBtn').href = data.short_url;
        document.getElementById('metaCode').innerText = data.short_code;
        document.getElementById('metaId').innerText = data.id;
        document.getElementById('metaClicks').innerText = "0";

        document.getElementById('resultBox').style.display = 'block';
      } catch (err) {
        alert("Failed to create short URL: " + err.message);
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerText = "Shorten URL";
      }
    }

    async function refreshAnalytics() {
      if (!currentUrlId) return;
      try {
        const resp = await fetch(`/api/v1/urls/${currentUrlId}/analytics`);
        if (resp.ok) {
          const data = await resp.json();
          document.getElementById('metaClicks').innerText = data.total_clicks;
        }
      } catch (err) {
        console.error(err);
      }
    }

    function copyLink() {
      if (!currentShortUrl) return;
      navigator.clipboard.writeText(currentShortUrl).then(() => {
        alert("Short URL copied to clipboard: " + currentShortUrl);
      });
    }
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse, tags=["ui"], summary="URL Shortener Web Interface")
async def root_ui() -> HTMLResponse:
    return HTMLResponse(content=_UI_HTML)

app.include_router(urls_router)

@app.get("/health", tags=["health"], summary="Health check")
async def health_check() -> Dict[str, str]:
    return {"status": "healthy", "service": "url-shortener"}

# Redirect router must come LAST — its /{short_code} catch-all would otherwise
# shadow /, /health, /docs, /redoc and other fixed paths.
app.include_router(redirect_router)


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Running startup: creating database tables...")
    await create_tables()
    logger.info("Database tables ready.")


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Any) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "Not Found", "detail": getattr(exc, "detail", "Not found")},
    )


@app.exception_handler(422)
async def validation_error_handler(request: Request, exc: Any) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "Validation Error", "detail": str(exc)},
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Any) -> JSONResponse:
    logger.exception("Unhandled server error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal Server Error", "detail": "An unexpected error occurred."},
    )
