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
        Generate or modify code dynamically based on state and user requirements.

        Returns:
            List of GeneratedFile dicts: {path, content, action}
        """
        request_type = state.get("request_type", "greenfield")
        logger.info("CodingAgent executing dynamically for: %s", request_type)

        # 1. Start with complete baseline files from reference app
        base_files = self._get_reference_app_files()
        file_map = {f["path"]: f["content"] for f in base_files}

        user_req = state.get("user_request", "")
        norm_req = state.get("normalized_requirement", user_req)

        # 2. Ask LLM to determine which files need changes and output the modified code
        modified_files = self._apply_llm_modifications(file_map, user_req, norm_req, request_type)

        # 3. Update file_map with LLM changes
        for path, content in modified_files.items():
            if path in file_map or path.startswith("main.py") or path.endswith(".py"):
                file_map[path] = content
                logger.info("CodingAgent dynamically updated: %s", path)

        return [
            {"path": p, "content": c, "action": "modify" if p in modified_files else "create"}
            for p, c in file_map.items()
        ]

    def _apply_llm_modifications(
        self,
        file_map: dict[str, str],
        user_req: str,
        norm_req: str,
        request_type: str,
    ) -> dict[str, str]:
        """Ask LLM to inspect relevant existing files and apply targeted user-requested changes."""
        req_lower = (user_req + " " + norm_req).lower()

        # Identify files relevant to this change
        candidate_paths = []
        if any(w in req_lower for w in ["background", "blue", "color", "ui", "style", "theme", "css", "html", "front"]):
            candidate_paths.append("main.py")
        if any(w in req_lower for w in ["short_code", "short code", "length", "hash", "deterministic", "random", "collision", "alphabet", "bug", "restart"]):
            candidate_paths.append("services/url_service.py")
        if any(w in req_lower for w in ["click", "analytics", "trend", "count"]):
            candidate_paths.append("services/analytics_service.py")
        if any(w in req_lower for w in ["route", "endpoint", "api", "redirect", "header"]):
            candidate_paths.append("api/urls.py")
        if any(w in req_lower for w in ["model", "schema", "table", "field", "expire", "expiry"]):
            candidate_paths.append("models/url.py")

        if not candidate_paths:
            # Default to main and url_service for general requests
            candidate_paths = ["main.py", "services/url_service.py"]

        # If user explicitly wants a blue background or color change, ensure main.py is included
        if "main.py" not in candidate_paths and ("blue" in req_lower or "color" in req_lower):
            candidate_paths.insert(0, "main.py")

        snippets = []
        for p in candidate_paths:
            content = file_map.get(p, "")
            if content:
                snippets.append(f"### File: {p}\n```python\n{content}\n```")

        context = "\n\n".join(snippets)

        prompt = f"""You are a senior software engineer making targeted modifications to a FastAPI URL Shortener based on the user's specific requirement.

User Request: {user_req}
Normalized Requirement: {norm_req}
Request Type: {request_type}

Relevant Existing Files:
{context}

INSTRUCTIONS:
1. Understand the user's EXACT requirement (e.g. if they asked for a blue background, change the CSS variables in main.py such as --bg, --card-bg, --primary to blue tones; if they asked for a logic change, update the corresponding service).
2. Return ONLY the files that need changes. Provide the COMPLETE updated file content for each modified file so it can be written to disk directly.
3. Respond ONLY with valid JSON:
{{
  "file_path": "...complete updated file content..."
}}"""

        messages = [
            {"role": "system", "content": "You are an expert Python engineer. Return valid JSON only with full file contents."},
            {"role": "user", "content": prompt},
        ]

        try:
            result = self._llm.chat_json(messages, temperature=0.1, max_tokens=8192)
            if isinstance(result, dict):
                # Handle possible wrapping like {"files": {...}} or {"modified_files": {...}}
                if "files" in result and isinstance(result["files"], dict):
                    result = result["files"]
                elif "modified_files" in result and isinstance(result["modified_files"], dict):
                    result = result["modified_files"]

                cleaned: dict[str, str] = {}
                for k, v in result.items():
                    if k in ("error", "raw"):
                        continue
                    norm_k = k.replace("\\", "/").lstrip("./")
                    if norm_k.endswith("main.py"):
                        norm_k = "main.py"
                    if isinstance(v, str) and len(v.strip()) > 30:
                        cleaned[norm_k] = v

                if cleaned:
                    return cleaned
        except Exception as exc:
            logger.error("CodingAgent LLM modification call failed: %s", exc)

        # Deterministic fallback for common UI/style requests if LLM call hits rate limits:
        if any(w in req_lower for w in ["blue", "blue background"]):
            main_code = file_map.get("main.py", "")
            if main_code and "--bg:" in main_code:
                updated_main = main_code.replace(
                    "--bg: #0d1117;\n      --card-bg: #161b22;\n      --border: #30363d;",
                    "--bg: #0a192f;\n      --card-bg: #112240;\n      --border: #233554;\n      --heading: #e6f1ff;",
                ).replace(
                    "--card-highlight: #21262d;",
                    "--card-highlight: #1d3557;",
                )
                logger.info("Applied deterministic blue background theme update to main.py")
                return {"main.py": updated_main}

        return {}

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
            except Exception as exc:
                logger.error("Failed to write %s: %s", gf["path"], exc)

        return f"Written {len(written)} files: {', '.join(written)}"

    def _get_reference_app_files(self) -> list[dict]:
        """Return baseline files from the reference app."""
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
