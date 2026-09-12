"""
LangGraph Workflow — The full EngineeringState state machine.

Graph structure:
START → intent → scope_gate
scope_gate → [out_of_scope → summary] | [clarification needed → summary] | [continue → requirement]
requirement → [brownfield/bugfix/refactor → repository → architecture] | [greenfield → architecture]
architecture → planner → human_approval (INTERRUPT)
human_approval → [approved → coding → testing → validation] | [rejected → summary]
validation → [pass → summary] | [fail + retry < max → remediation → testing] | [max retries → summary]
summary → END
"""

from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import StateGraph, END, START

from app.graph.state import EngineeringState
from app.graph.nodes import (
    node_intent,
    node_scope_gate,
    node_requirement,
    node_repository,
    node_architecture,
    node_planner,
    node_human_approval,
    node_coding,
    node_testing,
    node_validation,
    node_remediation,
    node_summary,
)
from app.config import settings

logger = logging.getLogger(__name__)


# ── Routing functions ─────────────────────────────────────────────────────────

def route_scope_gate(state: EngineeringState) -> Literal["requirement", "summary"]:
    wf_status = state.get("workflow_status", "running")
    if wf_status in ("out_of_scope", "waiting_clarification"):
        return "summary"
    return "requirement"


def route_after_requirement(state: EngineeringState) -> Literal["repository", "architecture"]:
    request_type = state.get("request_type", "greenfield")
    if request_type in ("brownfield", "bugfix", "refactor"):
        return "repository"
    return "architecture"


def route_after_approval(state: EngineeringState) -> Literal["coding", "summary"]:
    approval_status = state.get("approval_status", "pending")
    if approval_status == "approved":
        return "coding"
    return "summary"


def route_after_validation(state: EngineeringState) -> Literal["summary", "remediation"]:
    validation_results = state.get("validation_results", {})
    retry_count = state.get("retry_count", 0)
    max_retries = settings.max_remediation_retries

    if validation_results.get("passed", True):
        return "summary"
    if retry_count < max_retries:
        return "remediation"
    return "summary"


def route_after_remediation(state: EngineeringState) -> Literal["testing"]:
    return "testing"


# ── Graph Builder ─────────────────────────────────────────────────────────────

def create_workflow(checkpointer=None):
    """
    Build and compile the AgentForge LangGraph workflow.

    Args:
        checkpointer: Optional LangGraph checkpointer for state persistence.
                      Pass SqliteSaver for resumable workflows.

    Returns:
        Compiled LangGraph graph.
    """
    graph = StateGraph(EngineeringState)

    # ── Add nodes ─────────────────────────────────────────────────────────────
    graph.add_node("intent", node_intent)
    graph.add_node("scope_gate", node_scope_gate)
    graph.add_node("requirement", node_requirement)
    graph.add_node("repository", node_repository)
    graph.add_node("architecture", node_architecture)
    graph.add_node("planner", node_planner)
    graph.add_node("human_approval", node_human_approval)
    graph.add_node("coding", node_coding)
    graph.add_node("testing", node_testing)
    graph.add_node("validation", node_validation)
    graph.add_node("remediation", node_remediation)
    graph.add_node("summary", node_summary)

    # ── Add edges ─────────────────────────────────────────────────────────────
    graph.add_edge(START, "intent")
    graph.add_edge("intent", "scope_gate")

    graph.add_conditional_edges(
        "scope_gate",
        route_scope_gate,
        {"requirement": "requirement", "summary": "summary"},
    )

    graph.add_conditional_edges(
        "requirement",
        route_after_requirement,
        {"repository": "repository", "architecture": "architecture"},
    )

    graph.add_edge("repository", "architecture")
    graph.add_edge("architecture", "planner")
    graph.add_edge("planner", "human_approval")

    graph.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {"coding": "coding", "summary": "summary"},
    )

    graph.add_edge("coding", "testing")
    graph.add_edge("testing", "validation")

    graph.add_conditional_edges(
        "validation",
        route_after_validation,
        {"summary": "summary", "remediation": "remediation"},
    )

    graph.add_edge("remediation", "testing")
    graph.add_edge("summary", END)

    # ── Compile ───────────────────────────────────────────────────────────────
    compile_kwargs = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer

    return graph.compile(**compile_kwargs)
