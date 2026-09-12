"""
AgentForge — Engineering State Schema

This TypedDict defines ALL state that flows through the LangGraph workflow.
Every agent reads from and writes to this state object.
"""

from __future__ import annotations

from typing import TypedDict, Optional


class TaskItem(TypedDict):
    task_id: str
    description: str
    agent: str
    dependencies: list[str]
    inputs: list[str]
    expected_outputs: list[str]
    validation_criteria: list[str]
    risks: list[str]
    status: str  # pending | running | done | failed


class GeneratedFile(TypedDict):
    path: str
    content: str
    action: str  # create | modify | delete


class TestResult(TypedDict):
    passed: bool
    total: int
    passed_count: int
    failed_count: int
    output: str
    failed_tests: list[str]


class EngineeringState(TypedDict, total=False):
    # ── Identity ──────────────────────────────────────────────────────────────
    request_id: str
    user_request: str

    # ── Intent Classification ─────────────────────────────────────────────────
    domain: str                    # url_shortener | unknown
    request_type: str              # greenfield | brownfield | bugfix | refactor | ambiguous | out_of_scope
    confidence: float              # 0.0 – 1.0
    intent_reason: str             # Human-readable explanation of classification
    requires_clarification: bool
    clarification_question: str    # Question to ask user if ambiguous
    clarification_answered: bool
    clarification_answer: str      # User's answer to clarification

    # ── Requirement Analysis ──────────────────────────────────────────────────
    normalized_requirement: str
    functional_requirements: list[str]
    non_functional_requirements: list[str]
    assumptions: list[str]
    ambiguities: list[str]
    acceptance_criteria: list[str]

    # ── Repository / Codebase Analysis ───────────────────────────────────────
    repository_path: str
    codebase_summary: str          # Brief overview of existing codebase
    impacted_files: list[str]
    impacted_components: list[str]
    existing_apis: list[str]
    existing_tests: list[str]
    git_history_summary: str

    # ── Architecture ──────────────────────────────────────────────────────────
    architecture_summary: str
    components: list[dict]         # {name, description, technology}
    api_contract: dict             # OpenAPI-like summary
    data_model: dict               # Table/schema descriptions
    technology_stack: list[str]

    # ── Planning ──────────────────────────────────────────────────────────────
    task_graph: list[TaskItem]
    risks: list[str]
    tradeoffs: list[str]
    validation_strategy: str

    # ── Human Approval ────────────────────────────────────────────────────────
    approval_required: bool
    approval_status: str           # pending | approved | rejected | modification_requested
    modification_notes: str        # If user requests changes

    # ── Execution ─────────────────────────────────────────────────────────────
    workspace_path: str
    generated_files: list[GeneratedFile]
    git_diff: str
    branch_name: str

    # ── Testing & Validation ──────────────────────────────────────────────────
    test_results: TestResult
    lint_results: dict             # {passed: bool, output: str, errors: list}
    validation_results: dict       # {passed: bool, checks: list, evidence: str}
    retry_count: int

    # ── Final Output ──────────────────────────────────────────────────────────
    final_summary: dict
    workflow_status: str           # running | waiting_clarification | waiting_approval | executing | complete | failed
    error_message: str
    workflow_trace: list[dict]     # [{step, agent, duration_ms, status}]
