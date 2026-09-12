"""
Unit tests for scope detection and planner logic.
"""

from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest


MOCK_PLAN_RESPONSE = {
    "task_graph": [
        {
            "task_id": "T1",
            "description": "Set up FastAPI project structure",
            "agent": "coding",
            "dependencies": [],
            "inputs": ["normalized_requirement"],
            "expected_outputs": ["main.py", "api/urls.py"],
            "validation_criteria": ["Files exist", "No syntax errors"],
            "risks": ["Import errors"],
            "status": "pending",
        },
        {
            "task_id": "T2",
            "description": "Implement database models",
            "agent": "coding",
            "dependencies": ["T1"],
            "inputs": ["data_model"],
            "expected_outputs": ["models/url.py", "models/click.py"],
            "validation_criteria": ["SQLAlchemy models valid"],
            "risks": ["Migration issues"],
            "status": "pending",
        },
        {
            "task_id": "T3",
            "description": "Write unit and integration tests",
            "agent": "testing",
            "dependencies": ["T1", "T2"],
            "inputs": ["generated_files"],
            "expected_outputs": ["tests/test_urls.py"],
            "validation_criteria": ["All tests pass"],
            "risks": ["Test environment issues"],
            "status": "pending",
        },
    ],
    "validation_strategy": "Run pytest, check all endpoints respond correctly.",
    "estimated_files": ["main.py", "api/urls.py", "models/url.py", "tests/test_urls.py"],
}


@patch("app.llm.config.get_llm")
def test_planner_produces_task_graph(mock_get_llm):
    mock_llm = MagicMock()
    mock_llm.chat_json.return_value = MOCK_PLAN_RESPONSE
    mock_get_llm.return_value = mock_llm

    from app.agents.planner_agent import PlannerAgent
    agent = PlannerAgent()
    result = agent.create_plan(
        normalized_requirement="Build a URL shortener with FastAPI and SQLite.",
        request_type="greenfield",
        architecture_summary="FastAPI + SQLite + Redis cache",
        components=[],
        risks=[],
    )

    assert "task_graph" in result
    assert len(result["task_graph"]) > 0


@patch("app.llm.config.get_llm")
def test_planner_task_has_required_fields(mock_get_llm):
    mock_llm = MagicMock()
    mock_llm.chat_json.return_value = MOCK_PLAN_RESPONSE
    mock_get_llm.return_value = mock_llm

    from app.agents.planner_agent import PlannerAgent
    agent = PlannerAgent()
    result = agent.create_plan(
        normalized_requirement="Build URL shortener",
        request_type="greenfield",
        architecture_summary="FastAPI",
        components=[],
        risks=[],
    )

    required_fields = {"task_id", "description", "agent", "dependencies", "status"}
    for task in result["task_graph"]:
        assert required_fields.issubset(task.keys()), f"Task missing fields: {task}"


@patch("app.llm.config.get_llm")
def test_planner_dependencies_are_valid(mock_get_llm):
    mock_llm = MagicMock()
    mock_llm.chat_json.return_value = MOCK_PLAN_RESPONSE
    mock_get_llm.return_value = mock_llm

    from app.agents.planner_agent import PlannerAgent
    agent = PlannerAgent()
    result = agent.create_plan(
        normalized_requirement="Build URL shortener",
        request_type="greenfield",
        architecture_summary="FastAPI",
        components=[],
        risks=[],
    )

    task_ids = {t["task_id"] for t in result["task_graph"]}
    for task in result["task_graph"]:
        for dep in task.get("dependencies", []):
            assert dep in task_ids, f"Task {task['task_id']} depends on unknown {dep}"


def test_scope_detection_url_shortener():
    """Scope detection: URL shortener keywords should classify as in-scope."""
    url_shortener_keywords = [
        "url shortener", "short code", "redirect", "short url",
        "link shortener", "url analytics", "click tracking",
        "rate limiting", "url creation", "short link",
    ]
    # Simple keyword-based scope check (used as fallback in intent agent)
    def is_likely_url_shortener(text: str) -> bool:
        text_lower = text.lower()
        return any(kw in text_lower for kw in url_shortener_keywords)

    assert is_likely_url_shortener("Add analytics to my URL shortener") is True
    assert is_likely_url_shortener("Fix the redirect bug") is True
    assert is_likely_url_shortener("Build me a payroll system") is False
    assert is_likely_url_shortener("Create short links for our marketing campaign") is True
