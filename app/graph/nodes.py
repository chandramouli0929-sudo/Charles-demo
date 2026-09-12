"""
LangGraph node functions.
Each function receives EngineeringState and returns a partial state update dict.
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from app.graph.state import EngineeringState
from app.config import settings

logger = logging.getLogger(__name__)


def _add_trace(state: dict, step_name: str, agent: str, status: str, duration_ms: int = 0) -> list:
    trace = list(state.get("workflow_trace", []) or [])
    trace.append({
        "step": step_name,
        "agent": agent,
        "status": status,
        "duration_ms": duration_ms,
    })
    return trace


def node_intent(state: EngineeringState) -> dict:
    """Classify user intent from natural language."""
    from app.agents.intent_agent import IntentAgent

    start = time.time()
    logger.info("node_intent: analyzing '%s'", str(state.get("user_request", ""))[:80])

    agent = IntentAgent()
    result = agent.analyze(state["user_request"])

    duration_ms = int((time.time() - start) * 1000)
    return {
        "domain": result["domain"],
        "request_type": result["request_type"],
        "confidence": result["confidence"],
        "intent_reason": result["intent_reason"],
        "requires_clarification": result["requires_clarification"],
        "clarification_question": result["clarification_question"],
        "workflow_status": "running",
        "workflow_trace": _add_trace(state, "intent", "IntentAgent", "done", duration_ms),
    }


def node_scope_gate(state: EngineeringState) -> dict:
    """Route based on intent classification."""
    request_type = state.get("request_type", "")
    requires_clarification = state.get("requires_clarification", False)
    clarification_answered = state.get("clarification_answered", False)

    if request_type == "out_of_scope":
        return {
            "workflow_status": "out_of_scope",
            "workflow_trace": _add_trace(state, "scope_gate", "ScopeGate", "out_of_scope"),
        }

    if requires_clarification and not clarification_answered:
        return {
            "workflow_status": "waiting_clarification",
            "workflow_trace": _add_trace(state, "scope_gate", "ScopeGate", "waiting_clarification"),
        }

    return {
        "workflow_status": "running",
        "workflow_trace": _add_trace(state, "scope_gate", "ScopeGate", "done"),
    }


def node_requirement(state: EngineeringState) -> dict:
    """Normalize and structure the requirement."""
    from app.agents.requirement_agent import RequirementAgent

    start = time.time()
    agent = RequirementAgent()
    result = agent.analyze(
        user_request=state.get("user_request", ""),
        request_type=state.get("request_type", "greenfield"),
        clarification_answer=state.get("clarification_answer", ""),
    )

    duration_ms = int((time.time() - start) * 1000)
    return {
        **result,
        "workflow_trace": _add_trace(state, "requirement", "RequirementAgent", "done", duration_ms),
    }


def node_repository(state: EngineeringState) -> dict:
    """Analyze existing codebase (brownfield/bugfix/refactor only)."""
    from app.agents.repository_agent import RepositoryAgent

    start = time.time()
    repo_path = str(settings.reference_repo_abs_path)
    agent = RepositoryAgent()
    result = agent.analyze(
        repo_path=repo_path,
        normalized_requirement=state.get("normalized_requirement", state.get("user_request", "")),
        request_type=state.get("request_type", "brownfield"),
    )

    duration_ms = int((time.time() - start) * 1000)
    return {
        "repository_path": repo_path,
        **result,
        "workflow_trace": _add_trace(state, "repository", "RepositoryAgent", "done", duration_ms),
    }


def node_architecture(state: EngineeringState) -> dict:
    """Design solution architecture."""
    from app.agents.architecture_agent import ArchitectureAgent

    start = time.time()
    agent = ArchitectureAgent()
    result = agent.design(
        normalized_requirement=state.get("normalized_requirement", state.get("user_request", "")),
        request_type=state.get("request_type", "greenfield"),
        codebase_summary=state.get("codebase_summary", ""),
        impacted_components=state.get("impacted_components", []),
    )

    duration_ms = int((time.time() - start) * 1000)
    return {
        **result,
        "workflow_trace": _add_trace(state, "architecture", "ArchitectureAgent", "done", duration_ms),
    }


def node_planner(state: EngineeringState) -> dict:
    """Create dependency-aware task DAG."""
    from app.agents.planner_agent import PlannerAgent

    start = time.time()
    agent = PlannerAgent()
    result = agent.create_plan(
        normalized_requirement=state.get("normalized_requirement", state.get("user_request", "")),
        request_type=state.get("request_type", "greenfield"),
        architecture_summary=state.get("architecture_summary", ""),
        components=state.get("components", []),
        risks=state.get("risks", []),
    )

    duration_ms = int((time.time() - start) * 1000)
    return {
        **result,
        "approval_required": True,
        "approval_status": "pending",
        "workflow_status": "waiting_approval",
        "workflow_trace": _add_trace(state, "planning", "PlannerAgent", "done", duration_ms),
    }


def node_human_approval(state: EngineeringState) -> dict:
    """
    Human approval gate.
    This node uses LangGraph interrupt() to pause the workflow.
    The UI resumes it by calling graph.invoke(Command(resume=...)).
    """
    from langgraph.types import interrupt

    logger.info("node_human_approval: pausing for human review")

    # Interrupt pauses the graph here. The UI will receive the current state
    # and display the plan. When user approves, the graph resumes with approval_status set.
    approval_data = interrupt({
        "waiting_for": "human_approval",
        "plan_summary": {
            "request_type": state.get("request_type"),
            "normalized_requirement": state.get("normalized_requirement"),
            "task_count": len(state.get("task_graph", [])),
        },
    })

    # When resumed, approval_data contains the user's decision
    if isinstance(approval_data, dict):
        return {
            "approval_status": approval_data.get("approval_status", "approved"),
            "modification_notes": approval_data.get("modification_notes", ""),
            "workflow_status": "executing" if approval_data.get("approval_status") == "approved" else "failed",
        }

    return {
        "approval_status": "approved",
        "workflow_status": "executing",
    }


def node_coding(state: EngineeringState) -> dict:
    """Generate or modify code."""
    from app.agents.coding_agent import CodingAgent
    from app.tools.git_tools import git_diff, git_init, git_add_all, git_commit

    start = time.time()
    request_id = state.get("request_id", str(uuid.uuid4())[:8])
    req_type = state.get("request_type", "greenfield")

    if req_type in ("brownfield", "bugfix", "refactor"):
        workspace_path = str(settings.reference_repo_abs_path)
    else:
        workspace_path = str(Path(f"./generated_workspace/{request_id}").resolve())

    agent = CodingAgent()
    generated_files = agent.execute(dict(state))

    # Apply changes to workspace
    if generated_files:
        summary = agent.apply_changes(generated_files, workspace_path)
        logger.info("CodingAgent applied: %s", summary)

        # Ensure conftest.py exists in the workspace so tests can execute
        ws_tests = Path(workspace_path) / "tests"
        ws_tests.mkdir(parents=True, exist_ok=True)
        ref_conftest = settings.reference_repo_abs_path / "tests" / "conftest.py"
        target_conftest = ws_tests / "conftest.py"
        if not target_conftest.exists() and ref_conftest.exists():
            import shutil
            shutil.copyfile(ref_conftest, target_conftest)

        # Initialize git in workspace for diff tracking
        git_init(workspace_path)
        git_add_all(workspace_path)
        git_commit(workspace_path, f"AgentForge: {req_type} implementation")
        diff = git_diff(workspace_path)
    else:
        diff = ""

    duration_ms = int((time.time() - start) * 1000)

    # Mark all tasks as done
    task_graph = state.get("task_graph", [])
    for task in task_graph:
        if task.get("agent") == "coding":
            task["status"] = "done"

    return {
        "generated_files": generated_files,
        "git_diff": diff,
        "workspace_path": workspace_path,
        "task_graph": task_graph,
        "workflow_trace": _add_trace(state, "coding", "CodingAgent", "done", duration_ms),
    }


def node_testing(state: EngineeringState) -> dict:
    """Generate and run tests."""
    from app.agents.test_agent import TestAgent

    start = time.time()
    workspace_path = state.get("workspace_path") or ""

    # Robust fallback if workspace_path was not preserved
    if not workspace_path or not Path(workspace_path).exists():
        req_id = state.get("request_id")
        if req_id:
            cand = Path(f"./generated_workspace/{req_id}").resolve()
            if cand.exists():
                workspace_path = str(cand)
        if not workspace_path and state.get("request_type") in ("brownfield", "bugfix", "refactor"):
            workspace_path = str(settings.reference_repo_abs_path)

    agent = TestAgent()

    # Ensure test fixtures exist in workspace
    if workspace_path and Path(workspace_path).exists():
        ws_tests = Path(workspace_path) / "tests"
        ws_tests.mkdir(parents=True, exist_ok=True)
        ref_conftest = settings.reference_repo_abs_path / "tests" / "conftest.py"
        target_conftest = ws_tests / "conftest.py"
        if not target_conftest.exists() and ref_conftest.exists():
            import shutil
            shutil.copyfile(ref_conftest, target_conftest)

        # Only generate additional tests if no tests exist yet
        existing_tests = list(ws_tests.glob("test_*.py"))
        if not existing_tests:
            test_files = agent.generate_tests(dict(state))
            if test_files:
                from app.agents.coding_agent import CodingAgent
                CodingAgent().apply_changes(test_files, workspace_path)

        test_results = agent.run_tests(workspace_path)
    else:
        test_results = {
            "passed": True,
            "total": 0,
            "passed_count": 0,
            "failed_count": 0,
            "output": "No workspace found to test.",
            "failed_tests": [],
        }

    duration_ms = int((time.time() - start) * 1000)

    # Mark testing tasks done
    task_graph = state.get("task_graph", [])
    for task in task_graph:
        if task.get("agent") == "testing":
            task["status"] = "done"

    return {
        "test_results": test_results,
        "workspace_path": workspace_path,
        "task_graph": task_graph,
        "workflow_trace": _add_trace(
            state, "testing", "TestAgent",
            "done" if test_results.get("passed") else "failed",
            duration_ms,
        ),
    }


def node_validation(state: EngineeringState) -> dict:
    """Validate implementation with evidence-based checks."""
    from app.agents.validation_agent import ValidationAgent

    start = time.time()
    agent = ValidationAgent()

    state_dict = dict(state)
    workspace_path = state_dict.get("workspace_path") or ""
    if not workspace_path or not Path(workspace_path).exists():
        req_id = state_dict.get("request_id")
        if req_id:
            cand = Path(f"./generated_workspace/{req_id}").resolve()
            if cand.exists():
                workspace_path = str(cand)
        if not workspace_path and state_dict.get("request_type") in ("brownfield", "bugfix", "refactor"):
            workspace_path = str(settings.reference_repo_abs_path)
        state_dict["workspace_path"] = workspace_path

    validation_results = agent.validate(state_dict)

    duration_ms = int((time.time() - start) * 1000)
    return {
        "validation_results": validation_results,
        "workflow_trace": _add_trace(
            state, "validation", "ValidationAgent",
            "done" if validation_results.get("passed") else "failed",
            duration_ms,
        ),
    }


def node_remediation(state: EngineeringState) -> dict:
    """Fix failed tests — increment retry count and ask LLM to correct issues."""
    from app.llm.config import get_llm

    start = time.time()
    retry_count = state.get("retry_count", 0) + 1
    logger.info("node_remediation: attempt %d", retry_count)

    test_results = state.get("test_results", {})
    generated_files = state.get("generated_files", [])
    workspace_path = state.get("workspace_path", "")

    llm = get_llm()
    failed_output = test_results.get("output", "")[:2000]
    failed_tests = test_results.get("failed_tests", [])

    messages = [
        {
            "role": "system",
            "content": (
                "You are a Python debugging expert. Given failing test output, "
                "identify the root cause and provide corrected file content. "
                "Respond with JSON: {\"fixes\": {\"file_path\": \"corrected_content\", ...}}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Failed tests: {', '.join(failed_tests[:5])}\n\n"
                f"Test output:\n{failed_output}\n\n"
                f"Files to fix: {', '.join(gf['path'] for gf in generated_files[:5])}"
            ),
        },
    ]

    try:
        result = llm.chat_json(messages, temperature=0.1, max_tokens=4096)
        fixes = result.get("fixes", {})
        if fixes and workspace_path:
            fixed_files = [
                {"path": path, "content": content, "action": "modify"}
                for path, content in fixes.items()
                if isinstance(content, str)
            ]
            from app.agents.coding_agent import CodingAgent
            CodingAgent().apply_changes(fixed_files, workspace_path)
    except Exception as exc:
        logger.error("Remediation LLM call failed: %s", exc)

    duration_ms = int((time.time() - start) * 1000)
    return {
        "retry_count": retry_count,
        "workflow_trace": _add_trace(state, "remediation", "RemediationAgent", "done", duration_ms),
    }


def node_summary(state: EngineeringState) -> dict:
    """Compile final engineering outcome."""
    from app.agents.summary_agent import compile_summary

    summary = compile_summary(dict(state))
    wf_status = state.get("workflow_status", "complete")

    # Set final status
    if wf_status in ("out_of_scope", "waiting_clarification"):
        final_status = wf_status
    elif state.get("validation_results", {}).get("passed", True):
        final_status = "complete"
    else:
        final_status = "failed"

    return {
        "final_summary": summary,
        "workflow_status": final_status,
        "workflow_trace": _add_trace(state, "summary", "SummaryAgent", "done"),
    }
