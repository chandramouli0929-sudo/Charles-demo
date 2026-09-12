"""
Integration test: Workflow state transitions (no real LLM calls)
Uses mocked agents to test graph routing logic.
"""

from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest


def test_state_structure():
    """EngineeringState TypedDict has all required keys."""
    from app.graph.state import EngineeringState
    # TypedDict doesn't enforce at runtime, but we can instantiate a partial one
    state: EngineeringState = {
        "request_id": "test-123",
        "user_request": "Build a URL shortener",
        "workflow_status": "running",
        "retry_count": 0,
        "approval_status": "pending",
        "approval_required": True,
    }
    assert state["request_id"] == "test-123"
    assert state["workflow_status"] == "running"


@patch("app.llm.config.get_llm")
def test_intent_node_sets_state(mock_get_llm):
    """node_intent populates intent fields in state."""
    mock_llm = MagicMock()
    mock_llm.chat_json.return_value = {
        "domain": "url_shortener",
        "request_type": "greenfield",
        "confidence": 0.97,
        "intent_reason": "User wants to build new app",
        "requires_clarification": False,
        "clarification_question": "",
    }
    mock_get_llm.return_value = mock_llm

    from app.graph.nodes import node_intent
    state = {
        "request_id": "test-456",
        "user_request": "Build a URL shortener",
        "workflow_status": "running",
        "retry_count": 0,
        "approval_status": "pending",
        "approval_required": True,
        "clarification_answered": False,
        "clarification_answer": "",
        "generated_files": [],
        "workflow_trace": [],
    }

    result = node_intent(state)

    assert result.get("request_type") == "greenfield"
    assert result.get("domain") == "url_shortener"
    assert result.get("confidence", 0) > 0


@patch("app.llm.config.get_llm")
def test_scope_gate_out_of_scope(mock_get_llm):
    """node_scope_gate routes out-of-scope correctly."""
    from app.graph.nodes import node_scope_gate
    state = {
        "request_id": "test-789",
        "user_request": "Build a payroll system",
        "domain": "unknown",
        "request_type": "out_of_scope",
        "workflow_status": "running",
        "requires_clarification": False,
        "clarification_answered": False,
        "retry_count": 0,
        "approval_status": "pending",
        "workflow_trace": [],
    }

    result = node_scope_gate(state)
    assert result.get("workflow_status") == "out_of_scope"
