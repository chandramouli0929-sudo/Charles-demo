"""
Architecture Agent — Designs solution architecture, APIs, and data model.
"""

from __future__ import annotations

import logging
from app.llm.config import get_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Senior Software Architect designing solutions for a URL shortener application.

Technology stack: FastAPI (Python), SQLAlchemy 2.0 async, SQLite (dev) / PostgreSQL (prod), Redis cache.

Design principles:
- Keep it simple and runnable — this is a prototype, not a microservices platform
- Prefer modifying existing patterns over introducing new abstractions
- For greenfield: design clean FastAPI structure with services, models, and API layers
- For brownfield/bugfix/refactor: make minimal targeted changes
- Redis is used as a cache-aside for redirects only (not for analytics)
- PostgreSQL/SQLite used for analytics (no Kafka for prototype)
- Document async event pipeline as future improvement

Respond ONLY with valid JSON:
{
  "architecture_summary": "2-3 paragraph description of the solution design",
  "components": [
    {"name": "Component", "description": "What it does", "technology": "FastAPI/SQLAlchemy/Redis", "role": "api|service|model|cache|db"}
  ],
  "api_contract": {
    "endpoints": [
      {"method": "POST", "path": "/api/v1/urls", "description": "...", "request_body": "...", "response": "..."}
    ]
  },
  "data_model": {
    "tables": [
      {"name": "urls", "fields": [{"name": "id", "type": "Integer PK", "description": "..."}]}
    ]
  },
  "technology_stack": ["FastAPI", "SQLAlchemy 2.0", "SQLite/PostgreSQL", "Redis"],
  "risks": ["Risk 1: ...", ...],
  "tradeoffs": ["Trade-off 1: ...", ...]
}
"""


class ArchitectureAgent:
    """Designs solution architecture and API contracts."""

    def __init__(self) -> None:
        self._llm = get_llm(use_planner=True)  # Use smarter model for architecture

    def design(
        self,
        normalized_requirement: str,
        request_type: str,
        codebase_summary: str = "",
        impacted_components: list = [],
    ) -> dict:
        logger.info("ArchitectureAgent designing for: %s", request_type)

        context = f"Request type: {request_type}\nRequirement: {normalized_requirement}"
        if codebase_summary:
            context += f"\n\nExisting codebase: {codebase_summary}"
        if impacted_components:
            context += f"\nImpacted components: {', '.join(impacted_components)}"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        try:
            result = self._llm.chat_json(messages, temperature=0.3)
            return {
                "architecture_summary": result.get("architecture_summary", "FastAPI + SQLAlchemy + Redis architecture."),
                "components": result.get("components", []),
                "api_contract": result.get("api_contract", {"endpoints": []}),
                "data_model": result.get("data_model", {"tables": []}),
                "technology_stack": result.get("technology_stack", ["FastAPI", "SQLAlchemy", "SQLite", "Redis"]),
                "risks": result.get("risks", []),
                "tradeoffs": result.get("tradeoffs", []),
            }
        except Exception as exc:
            logger.error("ArchitectureAgent failed: %s", exc)
            return self._default_architecture(request_type, normalized_requirement)

    def _default_architecture(self, request_type: str, requirement: str) -> dict:
        return {
            "architecture_summary": (
                "FastAPI application with SQLAlchemy 2.0 async ORM, SQLite for development "
                "(PostgreSQL for production), and Redis cache-aside for URL redirect lookups. "
                "Short codes are generated deterministically using SHA-256 hash encoded in base-62."
            ),
            "components": [
                {"name": "FastAPI App", "description": "REST API layer", "technology": "FastAPI", "role": "api"},
                {"name": "URL Service", "description": "Business logic", "technology": "Python", "role": "service"},
                {"name": "SQLAlchemy ORM", "description": "Database persistence", "technology": "SQLAlchemy 2.0", "role": "db"},
                {"name": "Redis Cache", "description": "Redirect cache", "technology": "Redis", "role": "cache"},
            ],
            "api_contract": {
                "endpoints": [
                    {"method": "POST", "path": "/api/v1/urls", "description": "Create short URL", "request_body": '{"url": "https://..."}', "response": "URLResponse"},
                    {"method": "GET", "path": "/{short_code}", "description": "Redirect to original URL", "request_body": "", "response": "302 Redirect"},
                    {"method": "GET", "path": "/api/v1/urls/{id}/analytics", "description": "Click analytics", "request_body": "", "response": "URLAnalyticsResponse"},
                    {"method": "DELETE", "path": "/api/v1/urls/{id}", "description": "Deactivate URL", "request_body": "", "response": '{"message": "..."}'},
                ]
            },
            "data_model": {
                "tables": [
                    {"name": "urls", "fields": [
                        {"name": "id", "type": "Integer PK", "description": "Primary key"},
                        {"name": "original_url", "type": "String(2048)", "description": "The long URL"},
                        {"name": "short_code", "type": "String(20) UNIQUE", "description": "Deterministic short code"},
                        {"name": "created_at", "type": "DateTime", "description": "Creation timestamp"},
                        {"name": "is_active", "type": "Boolean", "description": "Active/deactivated flag"},
                    ]},
                    {"name": "clicks", "fields": [
                        {"name": "id", "type": "Integer PK", "description": "Primary key"},
                        {"name": "url_id", "type": "Integer FK", "description": "Reference to urls.id"},
                        {"name": "clicked_at", "type": "DateTime", "description": "Click timestamp"},
                        {"name": "user_agent", "type": "String(512)", "description": "Browser user agent"},
                    ]},
                ]
            },
            "technology_stack": ["FastAPI", "SQLAlchemy 2.0", "SQLite/PostgreSQL", "Redis", "Pydantic v2"],
            "risks": [
                "SQLite not suitable for multi-instance production deployment",
                "Synchronous analytics writes add latency to redirect path",
            ],
            "tradeoffs": [
                "SQLite chosen for zero-config demo setup; PostgreSQL available via Docker",
                "Synchronous click recording chosen over async pipeline for prototype simplicity",
                "Redis optional with in-memory fallback for development",
            ],
        }
