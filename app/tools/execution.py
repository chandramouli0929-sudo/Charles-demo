"""Execution tools — run commands, tests, and lint checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], cwd: str = ".", timeout: int = 60) -> dict:
    """Run a shell command and return structured result."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "Timed out", "success": False}
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc), "success": False}


def run_tests(workspace_path: str, timeout: int = 120) -> dict:
    """Run pytest and parse results."""
    result = run_command(
        [sys.executable, "-m", "pytest", workspace_path, "-v", "--tb=short", "-q"],
        cwd=workspace_path,
        timeout=timeout,
    )
    output = result["stdout"] + result["stderr"]
    passed = result["returncode"] == 0

    passed_count = 0
    failed_count = 0
    for line in output.splitlines():
        if " passed" in line:
            try:
                passed_count = int(line.strip().split()[0])
            except Exception:
                pass
        if " failed" in line:
            try:
                parts = line.strip().split()
                for i, p in enumerate(parts):
                    if "failed" in p.lower() and i > 0:
                        failed_count = int(parts[i - 1])
            except Exception:
                pass

    return {
        "passed": passed,
        "total": passed_count + failed_count,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "output": output[:3000],
        "failed_tests": [],
    }


def run_lint(workspace_path: str) -> dict:
    """Run ruff linter if available."""
    result = run_command(
        [sys.executable, "-m", "ruff", "check", workspace_path],
        cwd=workspace_path,
        timeout=30,
    )
    return {
        "passed": result["success"],
        "output": result["stdout"] + result["stderr"],
        "errors": [],
    }


def check_syntax(file_path: str) -> dict:
    """Check Python syntax using py_compile."""
    result = run_command(
        [sys.executable, "-m", "py_compile", file_path],
        timeout=10,
    )
    return {
        "passed": result["success"],
        "output": result["stderr"] if not result["success"] else "Syntax OK",
    }
