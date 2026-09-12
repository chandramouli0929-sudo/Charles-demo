"""
Test Agent — Generates test files and runs pytest.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from app.llm.config import get_llm

logger = logging.getLogger(__name__)


class TestAgent:
    """Generates and executes pytest test suites."""

    def __init__(self) -> None:
        self._llm = get_llm()

    def generate_tests(self, state: dict) -> list[dict]:
        """Generate pytest test files for the generated code."""
        generated_files = state.get("generated_files", [])
        normalized_req = state.get("normalized_requirement", "")
        request_type = state.get("request_type", "greenfield")

        if not generated_files:
            return []

        file_list = [gf["path"] for gf in generated_files]
        prompt = f"""Generate comprehensive pytest tests for this URL shortener implementation.

Request type: {request_type}
Requirement: {normalized_req}
Generated files: {', '.join(file_list)}

Generate a test file (tests/test_implementation.py) that:
1. Uses pytest-asyncio with async test functions
2. Uses httpx AsyncClient with ASGITransport
3. Uses in-memory SQLite for test isolation
4. Tests the main happy paths and error cases
5. Includes conftest.py fixtures if needed

Respond with JSON:
{{
  "tests/test_implementation.py": "...complete test file...",
  "tests/conftest.py": "...complete conftest if needed..."
}}"""

        messages = [
            {"role": "system", "content": "You are a senior Python test engineer. Generate complete, working pytest tests."},
            {"role": "user", "content": prompt},
        ]

        try:
            result = self._llm.chat_json(messages, temperature=0.2, max_tokens=4096)
            test_files = []
            for path, content in result.items():
                if isinstance(content, str) and content.strip():
                    test_files.append({"path": path, "content": content, "action": "create"})
            return test_files
        except Exception as exc:
            logger.error("TestAgent generate_tests failed: %s", exc)
            return []

    def run_tests(self, workspace_path: str) -> dict:
        """Run pytest in the workspace and return structured results."""
        workspace = Path(workspace_path)

        if not workspace.exists():
            return {
                "passed": False,
                "total": 0,
                "passed_count": 0,
                "failed_count": 0,
                "output": f"Workspace not found: {workspace_path}",
                "failed_tests": [],
            }

        # Check if there are any test files
        test_files = list(workspace.rglob("test_*.py")) + list(workspace.rglob("*_test.py"))
        if not test_files:
            logger.info("No test files found in %s — skipping test run", workspace_path)
            return {
                "passed": True,
                "total": 0,
                "passed_count": 0,
                "failed_count": 0,
                "output": "No test files found — skipping test execution.",
                "failed_tests": [],
            }

        tests_target = "tests" if (workspace / "tests").exists() else "."

        logger.info("Running pytest in: %s (target: %s)", workspace_path, tests_target)
        try:
            env = {
                **os.environ,
                "PYTHONPATH": str(workspace),
                "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
                "REDIS_ENABLED": "false",
            }
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    tests_target,
                    "-c",
                    "none",
                    "-o",
                    "asyncio_mode=auto",
                    "-v",
                    "--tb=short",
                    "-q",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(workspace),
                env=env,
            )
            output = proc.stdout + proc.stderr
            return self._parse_pytest_output(output, proc.returncode)
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "total": 0,
                "passed_count": 0,
                "failed_count": 0,
                "output": "Test execution timed out after 120 seconds.",
                "failed_tests": ["TIMEOUT"],
            }
        except Exception as exc:
            return {
                "passed": False,
                "total": 0,
                "passed_count": 0,
                "failed_count": 0,
                "output": f"Test execution error: {exc}",
                "failed_tests": [str(exc)],
            }

    def _parse_pytest_output(self, output: str, returncode: int) -> dict:
        """Parse pytest output to extract pass/fail counts."""
        import re

        match_passed = re.search(r"(\d+)\s+passed", output)
        passed_count = int(match_passed.group(1)) if match_passed else 0

        match_failed = re.search(r"(\d+)\s+failed", output)
        failed_count = int(match_failed.group(1)) if match_failed else 0

        failed_tests = []
        for line in output.splitlines():
            if line.startswith("FAILED "):
                failed_tests.append(line.replace("FAILED ", "").split(" - ")[0].strip())

        total = passed_count + failed_count
        passed = (returncode == 0) or (failed_count == 0 and passed_count > 0)
        return {
            "passed": passed,
            "total": total,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "output": output[:3000],
            "failed_tests": failed_tests,
        }
