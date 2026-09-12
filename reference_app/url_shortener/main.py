"""URL Shortener FastAPI application entry point."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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

app.include_router(urls_router)


@app.get("/health", tags=["health"], summary="Health check")
async def health_check() -> Dict[str, str]:
    return {"status": "healthy", "service": "url-shortener"}


# Redirect router must come LAST — its /{short_code} catch-all would otherwise
# shadow /health, /docs, /redoc and other fixed paths.
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
