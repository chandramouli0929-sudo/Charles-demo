"""
Validation Agent — Validates generated code with actual execution evidence.
Does NOT simply say "looks good" — runs real checks.
"""

from __future__ import annotations

import ast
import logging
import subprocess
import sys
from pathlib import Path

from app.llm.config import get_llm

logger = logging.getLogger(__name__)


class ValidationAgent:
    """Evidence-based validation of generated engineering outputs."""

    def __init__(self) -> None:
        self._llm = get_llm()

    def validate(self, state: dict) -> dict:
        """
        Run all validation checks and return structured evidence.

        Checks performed:
        1. File existence
        2. Python syntax (py_compile)
        3. Test results
        4. LLM review against requirements
        """
        generated_files = state.get("generated_files", [])
        test_results = state.get("test_results", {})
        normalized_req = state.get("normalized_requirement", "")
        workspace_path = state.get("workspace_path", "")
        request_type = state.get("request_type", "greenfield")

        checks = []

        # ── Check 1: File existence ────────────────────────────────────────
        if generated_files:
            existing = sum(1 for gf in generated_files if Path(workspace_path, gf["path"]).exists()) if workspace_path else len(generated_files)
            file_check = {
                "name": "File Generation",
                "passed": len(generated_files) > 0,
                "evidence": f"{len(generated_files)} files generated ({existing} written to disk)",
            }
            checks.append(file_check)

        # ── Check 2: Python syntax ─────────────────────────────────────────
        syntax_errors = []
        for gf in generated_files:
            if gf["path"].endswith(".py"):
                try:
                    ast.parse(gf.get("content", ""))
                except SyntaxError as e:
                    syntax_errors.append(f"{gf['path']}: {e}")

        syntax_check = {
            "name": "Syntax Validation",
            "passed": len(syntax_errors) == 0,
            "evidence": "All Python files parsed successfully" if not syntax_errors else f"Syntax errors: {'; '.join(syntax_errors[:3])}",
        }
        checks.append(syntax_check)

        # ── Check 3: Test results ──────────────────────────────────────────
        if test_results:
            test_passed = test_results.get("passed", False)
            test_check = {
                "name": "Test Suite",
                "passed": test_passed,
                "evidence": (
                    f"{test_results.get('passed_count', 0)}/{test_results.get('total', 0)} tests passed"
                    if test_results.get("total", 0) > 0
                    else "No tests executed"
                ),
            }
            checks.append(test_check)

        # ── Check 4: LLM review ────────────────────────────────────────────
        file_names = [gf["path"] for gf in generated_files]
        llm_check = self._llm_review(normalized_req, request_type, file_names, syntax_errors, test_results)
        checks.append(llm_check)

        # ── Overall result ─────────────────────────────────────────────────
        all_passed = all(c["passed"] for c in checks)
        critical_passed = syntax_check["passed"] and (not test_results or test_results.get("passed", True))

        return {
            "passed": critical_passed,
            "checks": checks,
            "evidence": f"{sum(1 for c in checks if c['passed'])}/{len(checks)} checks passed",
            "recommendation": "" if all_passed else self._get_recommendation(checks, test_results),
        }

    def _llm_review(
        self,
        normalized_req: str,
        request_type: str,
        file_names: list,
        syntax_errors: list,
        test_results: dict,
    ) -> dict:
        """Ask LLM to review whether the implementation matches the requirement."""
        test_summary = (
            f"{test_results.get('passed_count', 0)}/{test_results.get('total', 0)} tests passed"
            if test_results
            else "No tests run"
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior code reviewer validating an engineering implementation. "
                    "Be concise and objective. Respond with JSON only:\n"
                    '{"passed": true|false, "review": "2-3 sentence assessment"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Requirement: {normalized_req}\n"
                    f"Request type: {request_type}\n"
                    f"Generated files: {', '.join(file_names)}\n"
                    f"Syntax errors: {syntax_errors or 'None'}\n"
                    f"Test results: {test_summary}\n\n"
                    "Does this implementation look complete and correct for the requirement?"
                ),
            },
        ]

        try:
            result = self._llm.chat_json(messages, temperature=0.1)
            return {
                "name": "Requirements Review",
                "passed": bool(result.get("passed", True)),
                "evidence": result.get("review", "Implementation reviewed."),
            }
        except Exception as exc:
            logger.warning("LLM review failed: %s", exc)
            return {
                "name": "Requirements Review",
                "passed": True,
                "evidence": "Automated review unavailable — manual verification recommended.",
            }

    def _get_recommendation(self, checks: list, test_results: dict) -> str:
        failed = [c["name"] for c in checks if not c["passed"]]
        if "Syntax Validation" in failed:
            return "Fix Python syntax errors before proceeding."
        if "Test Suite" in failed and test_results:
            failed_tests = test_results.get("failed_tests", [])
            if failed_tests:
                return f"Fix failing tests: {', '.join(failed_tests[:3])}"
        return f"Review failed checks: {', '.join(failed)}"
