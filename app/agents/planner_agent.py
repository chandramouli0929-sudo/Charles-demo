"""
Planner Agent — Generates a dependency-aware task DAG.
"""

from __future__ import annotations

import logging
from app.llm.config import get_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Senior Engineering Planner creating a task breakdown for a URL shortener project.

Generate a dependency-aware task graph (DAG). Each task must have:
- task_id: "T1", "T2", etc.
- description: What this task does
- agent: "coding" | "testing" | "validation"
- dependencies: List of task_ids this task depends on (empty list for first tasks)
- inputs: What data/files this task needs
- expected_outputs: Files or artifacts produced
- validation_criteria: How to verify this task succeeded
- risks: Potential issues
- status: Always "pending"

Rules:
- Keep it realistic: 3-7 tasks maximum for prototype
- First tasks have no dependencies
- Testing tasks depend on coding tasks
- Validation depends on testing
- Be specific about file names (e.g., "app/api/urls.py")

Also provide:
- validation_strategy: Overall test and validation approach
- estimated_files: All files that will be created or modified

Respond ONLY with valid JSON:
{
  "task_graph": [...],
  "validation_strategy": "...",
  "estimated_files": [...]
}
"""


class PlannerAgent:
    """Creates dependency-aware task DAGs."""

    def __init__(self) -> None:
        self._llm = get_llm(use_planner=True)

    def create_plan(
        self,
        normalized_requirement: str,
        request_type: str,
        architecture_summary: str,
        components: list,
        risks: list,
    ) -> dict:
        logger.info("PlannerAgent creating plan for: %s", request_type)

        component_names = [c.get("name", "") for c in components] if components else []
        context = (
            f"Request type: {request_type}\n"
            f"Requirement: {normalized_requirement}\n"
            f"Architecture: {architecture_summary}\n"
            f"Components: {', '.join(component_names)}\n"
            f"Known risks: {', '.join(risks[:5])}"
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        try:
            result = self._llm.chat_json(messages, temperature=0.2)
            task_graph = result.get("task_graph", [])

            # Ensure all tasks have 'status' field
            for task in task_graph:
                task.setdefault("status", "pending")
                task.setdefault("dependencies", [])
                task.setdefault("risks", [])
                task.setdefault("validation_criteria", [])

            return {
                "task_graph": task_graph,
                "validation_strategy": result.get(
                    "validation_strategy",
                    "Run pytest suite, verify API responses, check code syntax.",
                ),
                "estimated_files": result.get("estimated_files", []),
            }
        except Exception as exc:
            logger.error("PlannerAgent failed: %s", exc)
            return self._default_plan(request_type)

    def _default_plan(self, request_type: str) -> dict:
        if request_type == "greenfield":
            tasks = [
                {
                    "task_id": "T1",
                    "description": "Generate FastAPI application structure and database models",
                    "agent": "coding",
                    "dependencies": [],
                    "inputs": ["normalized_requirement", "data_model"],
                    "expected_outputs": ["main.py", "models/url.py", "models/click.py", "db/database.py"],
                    "validation_criteria": ["Files exist", "No Python syntax errors"],
                    "risks": ["Import errors between modules"],
                    "status": "pending",
                },
                {
                    "task_id": "T2",
                    "description": "Implement URL service and API routes",
                    "agent": "coding",
                    "dependencies": ["T1"],
                    "inputs": ["api_contract", "T1 outputs"],
                    "expected_outputs": ["services/url_service.py", "api/urls.py"],
                    "validation_criteria": ["Service methods exist", "Routes registered"],
                    "risks": ["Async/await consistency"],
                    "status": "pending",
                },
                {
                    "task_id": "T3",
                    "description": "Generate unit and integration tests",
                    "agent": "testing",
                    "dependencies": ["T1", "T2"],
                    "inputs": ["generated_files"],
                    "expected_outputs": ["tests/test_urls.py", "tests/conftest.py"],
                    "validation_criteria": ["Tests can be discovered by pytest", "All tests pass"],
                    "risks": ["Test fixture setup complexity"],
                    "status": "pending",
                },
                {
                    "task_id": "T4",
                    "description": "Validate implementation against requirements",
                    "agent": "validation",
                    "dependencies": ["T3"],
                    "inputs": ["test_results", "generated_files"],
                    "expected_outputs": ["validation_report"],
                    "validation_criteria": ["All acceptance criteria met", "Tests pass"],
                    "risks": ["Integration test failures"],
                    "status": "pending",
                },
            ]
        else:
            tasks = [
                {
                    "task_id": "T1",
                    "description": f"Implement {request_type} changes to existing codebase",
                    "agent": "coding",
                    "dependencies": [],
                    "inputs": ["normalized_requirement", "impacted_files"],
                    "expected_outputs": ["Modified files"],
                    "validation_criteria": ["Changes applied", "No syntax errors"],
                    "risks": ["Breaking existing behavior"],
                    "status": "pending",
                },
                {
                    "task_id": "T2",
                    "description": "Run existing tests and add regression tests",
                    "agent": "testing",
                    "dependencies": ["T1"],
                    "inputs": ["modified_files"],
                    "expected_outputs": ["Test results"],
                    "validation_criteria": ["All existing tests pass", "New tests pass"],
                    "risks": ["Test environment issues"],
                    "status": "pending",
                },
            ]

        return {
            "task_graph": tasks,
            "validation_strategy": "Run pytest, verify API endpoints respond correctly, check git diff.",
            "estimated_files": [],
        }
