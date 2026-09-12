"""Summary agent — compiles the final engineering outcome."""

from __future__ import annotations


def compile_summary(state: dict) -> dict:
    """Compile the final engineering outcome from workflow state."""
    test_results = state.get("test_results", {})
    validation_results = state.get("validation_results", {})
    generated_files = state.get("generated_files", [])

    # Determine overall status
    if validation_results.get("passed") and (not test_results or test_results.get("passed")):
        status = "IMPLEMENTATION VALIDATED"
    elif state.get("retry_count", 0) >= state.get("max_retries", 2):
        status = "MAXIMUM RETRIES REACHED — PARTIAL IMPLEMENTATION"
    elif state.get("workflow_status") == "failed":
        status = f"IMPLEMENTATION FAILED — {state.get('error_message', 'Unknown error')}"
    else:
        status = "COMPLETE"

    return {
        "request": state.get("user_request", ""),
        "intent": state.get("request_type", "unknown"),
        "normalized_requirement": state.get("normalized_requirement", ""),
        "assumptions": state.get("assumptions", []),
        "architecture_summary": state.get("architecture_summary", ""),
        "technology_stack": state.get("technology_stack", []),
        "tasks_total": len(state.get("task_graph", [])),
        "tasks_completed": len([t for t in state.get("task_graph", []) if t.get("status") == "done"]),
        "generated_files": [f["path"] for f in generated_files],
        "git_diff": state.get("git_diff", ""),
        "test_results": test_results,
        "validation_results": validation_results,
        "risks": state.get("risks", []),
        "tradeoffs": state.get("tradeoffs", []),
        "status": status,
        "retry_count": state.get("retry_count", 0),
        "error_message": state.get("error_message", ""),
    }
