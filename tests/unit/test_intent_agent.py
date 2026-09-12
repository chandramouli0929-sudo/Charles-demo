"""
Unit tests for Intent Agent
Tests use mocked LLM responses — no API key required for CI.
Patches get_llm at the config level so no real LLM is instantiated.
"""

from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest


MOCK_GREENFIELD_RESPONSE = {
    "domain": "url_shortener",
    "request_type": "greenfield",
    "confidence": 0.97,
    "intent_reason": "User wants to build a new URL shortener from scratch.",
    "requires_clarification": False,
    "clarification_question": "",
}

MOCK_BROWNFIELD_RESPONSE = {
    "domain": "url_shortener",
    "request_type": "brownfield",
    "confidence": 0.93,
    "intent_reason": "User wants to add rate limiting to an existing URL shortener.",
    "requires_clarification": False,
    "clarification_question": "",
}

MOCK_BUGFIX_RESPONSE = {
    "domain": "url_shortener",
    "request_type": "bugfix",
    "confidence": 0.95,
    "intent_reason": "User reports inconsistent short code generation.",
    "requires_clarification": False,
    "clarification_question": "",
}

MOCK_AMBIGUOUS_RESPONSE = {
    "domain": "url_shortener",
    "request_type": "ambiguous",
    "confidence": 0.6,
    "intent_reason": "Request is too vague — scalability target is unclear.",
    "requires_clarification": True,
    "clarification_question": "Which part needs to scale: redirect traffic, URL creation, or analytics?",
}

MOCK_OUT_OF_SCOPE_RESPONSE = {
    "domain": "unknown",
    "request_type": "out_of_scope",
    "confidence": 0.99,
    "intent_reason": "Request is about a payroll system, not a URL shortener.",
    "requires_clarification": False,
    "clarification_question": "",
}


def _run_intent(mock_response: dict, request: str) -> dict:
    """Helper: run IntentAgent.analyze() with a mocked LLM."""
    mock_llm = MagicMock()
    mock_llm.chat_json.return_value = mock_response
    # Patch at the module level where IntentAgent calls get_llm
    with patch("app.agents.intent_agent.get_llm", return_value=mock_llm):
        from app.agents.intent_agent import IntentAgent
        agent = IntentAgent()
        return agent.analyze(request)


def test_intent_greenfield():
    result = _run_intent(
        MOCK_GREENFIELD_RESPONSE,
        "Build a scalable URL shortener with APIs, persistence and analytics.",
    )
    assert result["request_type"] == "greenfield"
    assert result["domain"] == "url_shortener"
    assert result["confidence"] > 0.8
    assert result["requires_clarification"] is False


def test_intent_brownfield():
    result = _run_intent(
        MOCK_BROWNFIELD_RESPONSE,
        "Add rate limiting to the URL creation endpoint.",
    )
    assert result["request_type"] == "brownfield"
    assert result["requires_clarification"] is False


def test_intent_bugfix():
    result = _run_intent(
        MOCK_BUGFIX_RESPONSE,
        "Sometimes the same URL gets a different short code after restarting. Fix it.",
    )
    assert result["request_type"] == "bugfix"


def test_intent_ambiguous():
    result = _run_intent(
        MOCK_AMBIGUOUS_RESPONSE,
        "Make the URL shortener scalable.",
    )
    assert result["request_type"] == "ambiguous"
    assert result["requires_clarification"] is True
    assert len(result["clarification_question"]) > 0


def test_intent_out_of_scope():
    result = _run_intent(
        MOCK_OUT_OF_SCOPE_RESPONSE,
        "Build me a payroll management system.",
    )
    assert result["request_type"] == "out_of_scope"
    assert result["domain"] == "unknown"
