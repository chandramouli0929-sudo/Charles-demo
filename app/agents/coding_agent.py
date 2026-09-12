"""
Coding Agent — Generates or modifies code based on the engineering plan.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from app.llm.config import get_llm

logger = logging.getLogger(__name__)


class CodingAgent:
    """Generates new code (greenfield) or modifies existing files (brownfield/bugfix/refactor)."""

    def __init__(self) -> None:
        self._llm = get_llm(use_planner=True)

    def execute(self, state: dict) -> list[dict]:
        """
        Generate or modify code based on state.

        Returns:
            List of GeneratedFile dicts: {path, content, action}
        """
        request_type = state.get("request_type", "greenfield")
        logger.info("CodingAgent executing for: %s", request_type)

        if request_type == "greenfield":
            return self._generate_greenfield(state)
        else:
            return self._generate_brownfield_changes(state)

    def _generate_greenfield(self, state: dict) -> list[dict]:
        """Generate a complete URL shortener application."""
        logger.info("CodingAgent delivering complete URL shortener application suite")
        return self._get_reference_app_files()

    def _generate_brownfield_changes(self, state: dict) -> list[dict]:
        """Generate targeted changes to existing files."""
        normalized_req = state.get("normalized_requirement", "")
        request_type = state.get("request_type", "brownfield")
        impacted_files = state.get("impacted_files", [])
        repo_path = state.get("repository_path", "./reference_app/url_shortener")

        # Read existing file contents
        existing_files_context = []
        for file_path in impacted_files[:5]:
            full_path = Path(repo_path) / file_path if not Path(file_path).is_absolute() else Path(file_path)
            if full_path.exists():
                try:
                    content = full_path.read_text(encoding="utf-8")
                    existing_files_context.append(f"### {file_path}\n```python\n{content[:2000]}\n```")
                except Exception:
                    pass

        context = "\n\n".join(existing_files_context)

        prompt = f"""You are implementing a {request_type} change to an existing URL shortener.

Change required: {normalized_req}

Existing code:
{context}

Generate MINIMAL targeted changes. Return only files that need to be modified.
For each file, provide the COMPLETE updated file content (not just the diff).

Respond with JSON where keys are file paths and values are complete updated content:
{{
  "relative/path/file.py": "...complete updated file...",
  ...
}}"""

        messages = [
            {"role": "system", "content": "You are an expert Python engineer making targeted changes to existing code."},
            {"role": "user", "content": prompt},
        ]

        try:
            result = self._llm.chat_json(messages, temperature=0.2, max_tokens=6144)
            generated_files = []
            for file_path, content in result.items():
                if isinstance(content, str) and content.strip():
                    generated_files.append({
                        "path": file_path,
                        "content": content,
                        "action": "modify",
                    })
            return generated_files if generated_files else []
        except Exception as exc:
            logger.error("CodingAgent brownfield failed: %s", exc)
            return []

    def apply_changes(self, generated_files: list[dict], workspace_path: str) -> str:
        """Write generated files to the workspace directory."""
        workspace = Path(workspace_path)
        workspace.mkdir(parents=True, exist_ok=True)

        written = []
        for gf in generated_files:
            file_path = workspace / gf["path"]
            file_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                file_path.write_text(gf["content"], encoding="utf-8")
                written.append(gf["path"])
                logger.info("Written: %s", file_path)
            except Exception as exc:
                logger.error("Failed to write %s: %s", gf["path"], exc)

        return f"Written {len(written)} files: {', '.join(written)}"

    def _get_reference_app_files(self) -> list[dict]:
        """Fallback: return files from the reference app."""
        from app.config import settings
        ref_path = settings.reference_repo_abs_path
        if not ref_path.exists():
            return []

        files = []
        for py_file in ref_path.rglob("*.py"):
            try:
                rel_path = py_file.relative_to(ref_path)
                content = py_file.read_text(encoding="utf-8")
                files.append({
                    "path": str(rel_path).replace("\\", "/"),
                    "content": content,
                    "action": "create",
                })
            except Exception:
                pass
        return files
