"""
Repository Agent — Analyzes existing codebase using DETERMINISTIC tools.
Does NOT ask the LLM to guess at code structure. Reads files first, then
asks LLM to reason about impact.
"""

from __future__ import annotations

import ast
import logging
import os
import subprocess
from pathlib import Path
from typing import List

from app.llm.config import get_llm
from app.tools.repository import list_files, get_file_summary, find_functions

logger = logging.getLogger(__name__)


class RepositoryAgent:
    """Inspects existing repositories using deterministic tools."""

    def __init__(self) -> None:
        self._llm = get_llm()

    def analyze(
        self,
        repo_path: str,
        normalized_requirement: str,
        request_type: str,
    ) -> dict:
        """
        Analyze the repository and return structured findings.

        Uses deterministic tools (file listing, AST parsing, git log)
        BEFORE asking the LLM to reason about impact.
        """
        logger.info("RepositoryAgent analyzing: %s", repo_path)

        path = Path(repo_path)
        if not path.exists():
            logger.warning("Repository path does not exist: %s", repo_path)
            return self._empty_result()

        # ── Step 1: Deterministic — List all Python files ──────────────────
        py_files = list_files(repo_path, extensions=[".py"])

        # ── Step 2: Deterministic — Summarize key files ────────────────────
        file_summaries = []
        priority_patterns = ["api", "service", "route", "model", "main", "app"]

        for f in py_files[:20]:  # Limit to avoid token overload
            rel_path = str(Path(f).relative_to(path)) if Path(f).is_absolute() else f
            # Prioritize important files
            is_priority = any(p in rel_path.lower() for p in priority_patterns)
            if is_priority or len(file_summaries) < 8:
                summary = get_file_summary(f, max_lines=40)
                file_summaries.append(f"### {rel_path}\n{summary}")

        # ── Step 3: Deterministic — Git log ────────────────────────────────
        git_history = self._get_git_log(repo_path)

        # ── Step 4: Find test files ────────────────────────────────────────
        test_files = [f for f in py_files if "test" in f.lower()]

        # ── Step 5: LLM — Reason about impact ────────────────────────────
        codebase_context = "\n\n".join(file_summaries[:8])

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior software architect analyzing an existing URL shortener codebase. "
                    "Given the file summaries and a change request, identify impacted components and files. "
                    "Be precise — only list files that are truly impacted by this specific change.\n\n"
                    "Respond ONLY with valid JSON:\n"
                    "{\n"
                    '  "codebase_summary": "2-3 sentence overview of the codebase architecture",\n'
                    '  "impacted_files": ["relative/path/to/file.py", ...],\n'
                    '  "impacted_components": ["Component name", ...],\n'
                    '  "existing_apis": ["GET /path", "POST /path", ...],\n'
                    '  "analysis_notes": "Key observations about the codebase relevant to this change"\n'
                    "}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Change request ({request_type}): {normalized_requirement}\n\n"
                    f"Codebase file summaries:\n{codebase_context}\n\n"
                    f"All Python files: {', '.join(py_files[:30])}"
                ),
            },
        ]

        try:
            result = self._llm.chat_json(messages, temperature=0.1)
            return {
                "codebase_summary": result.get("codebase_summary", "FastAPI URL shortener application."),
                "impacted_files": result.get("impacted_files", []),
                "impacted_components": result.get("impacted_components", []),
                "existing_apis": result.get("existing_apis", []),
                "existing_tests": test_files,
                "git_history_summary": git_history,
            }
        except Exception as exc:
            logger.error("RepositoryAgent LLM step failed: %s", exc)
            return {
                "codebase_summary": f"FastAPI URL shortener at {repo_path}. Contains {len(py_files)} Python files.",
                "impacted_files": py_files[:5],
                "impacted_components": ["URL Service", "API Routes"],
                "existing_apis": [],
                "existing_tests": test_files,
                "git_history_summary": git_history,
            }

    def _get_git_log(self, repo_path: str, n: int = 5) -> str:
        """Get last N git commits. Returns empty string if git not available."""
        try:
            result = subprocess.run(
                ["git", "-C", repo_path, "log", "--oneline", f"-{n}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return "No git history available"

    def _empty_result(self) -> dict:
        return {
            "codebase_summary": "Repository not found or inaccessible.",
            "impacted_files": [],
            "impacted_components": [],
            "existing_apis": [],
            "existing_tests": [],
            "git_history_summary": "No git history available",
        }
