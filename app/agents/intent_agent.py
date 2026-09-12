"""
Intent Agent — Classifies user intent from natural language.

Returns a structured dict with domain, request_type, confidence, etc.
The rest of the workflow uses this to determine routing — the user never
selects a workflow manually.
"""

from __future__ import annotations

import logging
from app.llm.config import get_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an Engineering Intent Classifier for an agentic software engineering system.

Your job is to analyze the user's natural-language request and classify it into one of these categories:

REQUEST TYPES:
- "greenfield": User wants to BUILD something new from scratch. Keywords: build, create, develop, implement, make a new...
- "brownfield": User wants to ADD or CHANGE functionality in an existing application. Keywords: add, extend, enhance, implement feature, integrate...
- "bugfix": User reports broken or incorrect behavior. Keywords: fix, broken, wrong, doesn't work, error, bug, issue, failing...
- "refactor": User wants to improve code quality/structure WITHOUT changing behavior. Keywords: refactor, restructure, clean up, reorganize, improve maintainability...
- "ambiguous": Request is too vague to confidently classify or implement without more information.
- "out_of_scope": Request is completely unrelated to a URL shortener application.

DOMAIN:
- "url_shortener": Request relates to URL shortening, short codes, redirects, link analytics, URL management
- "unknown": Request is about something completely different (payroll, HR, e-commerce not related to URLs, etc.)

EXAMPLES:
- "Build a scalable URL shortener" → greenfield, url_shortener, confidence: 0.97
- "Add rate limiting to URL creation" → brownfield, url_shortener, confidence: 0.93
- "Same URL gets different short code after restart" → bugfix, url_shortener, confidence: 0.95
- "Refactor the URL service, it's hard to maintain" → refactor, url_shortener, confidence: 0.91
- "Make the URL shortener scalable" → ambiguous, url_shortener, confidence: 0.65 (scalability target unclear)
- "Build a payroll system" → out_of_scope, unknown, confidence: 0.99
- "Add click tracking" → brownfield, url_shortener, confidence: 0.92
- "The redirect is returning 500 errors" → bugfix, url_shortener, confidence: 0.94
- "Add analytics dashboard" → brownfield, url_shortener, confidence: 0.90

CLARIFICATION QUESTIONS & OPTIONS (when ambiguous):
Ask targeted questions about WHAT specifically needs to change, not yes/no questions.
Always provide 3 to 4 concrete, actionable engineering options the user can choose between.
Example: 
  Question: "Which aspect of scalability would you like to target?"
  Options: [
    "Optimize redirect throughput using Redis caching",
    "Add high-volume batch URL creation with bulk insert",
    "Add PostgreSQL connection pooling & read replica support",
    "Implement rate limiting to prevent throughput degradation"
  ]

Respond ONLY with valid JSON (no markdown, no explanation):
{
  "domain": "url_shortener" | "unknown",
  "request_type": "greenfield" | "brownfield" | "bugfix" | "refactor" | "ambiguous" | "out_of_scope",
  "confidence": 0.0-1.0,
  "intent_reason": "Brief explanation of why this classification was chosen",
  "requires_clarification": true | false,
  "clarification_question": "Question to ask user if requires_clarification is true, else empty string",
  "clarification_options": ["Option 1", "Option 2", "Option 3"]
}
"""


class IntentAgent:
    """Classifies engineering intent from natural language."""

    def __init__(self) -> None:
        self._llm = get_llm()

    def analyze(self, user_request: str) -> dict:
        """
        Analyze the user request and return a classification dict.

        Returns:
            dict with keys: domain, request_type, confidence, intent_reason,
            requires_clarification, clarification_question, clarification_options
        """
        logger.info("IntentAgent analyzing: %r", user_request[:100])

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Classify this engineering request:\n\n{user_request}"},
        ]

        try:
            result = self._llm.chat_json(messages, temperature=0.1)

            # Validate and provide defaults for any missing keys
            return {
                "domain": result.get("domain", "url_shortener"),
                "request_type": result.get("request_type", "ambiguous"),
                "confidence": float(result.get("confidence", 0.5)),
                "intent_reason": result.get("intent_reason", "Classification unclear."),
                "requires_clarification": bool(result.get("requires_clarification", False)),
                "clarification_question": result.get("clarification_question", ""),
                "clarification_options": result.get("clarification_options", []),
            }
        except Exception as exc:
            logger.error("IntentAgent LLM call failed: %s — activating resilient domain classifier", exc)
            req_lower = user_request.lower()
            is_url_shortener = any(k in req_lower for k in ["url", "short", "shorten", "link", "redirect", "click", "analytic"])

            if not is_url_shortener:
                return {
                    "domain": "unknown",
                    "request_type": "out_of_scope",
                    "confidence": 0.98,
                    "intent_reason": "Request is not related to URL shortening domain.",
                    "requires_clarification": False,
                    "clarification_question": "",
                }

            if any(k in req_lower for k in ["build", "create", "scratch", "develop", "implement app", "new"]):
                return {
                    "domain": "url_shortener",
                    "request_type": "greenfield",
                    "confidence": 0.96,
                    "intent_reason": "User requested building a URL shortener application.",
                    "requires_clarification": False,
                    "clarification_question": "",
                }
            elif any(k in req_lower for k in ["fix", "bug", "broken", "wrong", "same url", "different code", "collision"]):
                return {
                    "domain": "url_shortener",
                    "request_type": "bugfix",
                    "confidence": 0.95,
                    "intent_reason": "User identified a bug/issue in URL shortener behavior.",
                    "requires_clarification": False,
                    "clarification_question": "",
                }
            elif any(k in req_lower for k in ["add", "rate limit", "analytics", "dashboard", "metric", "extend", "enhance"]):
                return {
                    "domain": "url_shortener",
                    "request_type": "brownfield",
                    "confidence": 0.92,
                    "intent_reason": "User requested an enhancement/addition to existing URL shortener.",
                    "requires_clarification": False,
                    "clarification_question": "",
                }
            elif "refactor" in req_lower:
                return {
                    "domain": "url_shortener",
                    "request_type": "refactor",
                    "confidence": 0.90,
                    "intent_reason": "User requested refactoring existing codebase.",
                    "requires_clarification": False,
                    "clarification_question": "",
                }
            else:
                return {
                    "domain": "url_shortener",
                    "request_type": "ambiguous",
                    "confidence": 0.55,
                    "intent_reason": "Request is too vague to determine exact technical scope.",
                    "requires_clarification": True,
                    "clarification_question": "Which aspect of the URL shortener would you like to build or modify?",
                    "clarification_options": [
                        "Build a full Greenfield URL shortener with FastAPI & Redis",
                        "Add high-throughput batch URL shortening with multi-URL input",
                        "Add custom alias / vanity short URLs",
                        "Implement Redis caching and redirect analytics tracking"
                    ],
                }
