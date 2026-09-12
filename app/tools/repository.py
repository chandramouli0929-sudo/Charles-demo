"""
Deterministic repository tools — NO LLM involved.
Used by RepositoryAgent to inspect codebases reliably.
"""

from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path
from typing import List


def list_files(repo_path: str, extensions: List[str] = [".py"]) -> List[str]:
    """Return absolute paths of all files matching the given extensions."""
    result = []
    path = Path(repo_path)
    if not path.exists():
        return result

    for root, dirs, files in os.walk(path):
        # Skip hidden dirs and __pycache__
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for f in files:
            if any(f.endswith(ext) for ext in extensions):
                result.append(str(Path(root) / f))

    return sorted(result)


def read_file(file_path: str) -> str:
    """Read and return file content. Returns empty string on error."""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except Exception:
        return ""


def search_code(repo_path: str, query: str) -> List[dict]:
    """
    Search for a query string in the codebase.
    Uses ripgrep if available, else Python grep fallback.

    Returns list of {file, line_number, line_content}
    """
    results = []

    # Try ripgrep first (fast)
    try:
        proc = subprocess.run(
            ["rg", "--json", "-n", query, repo_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode in (0, 1):  # 0=found, 1=not found (not an error)
            import json
            for line in proc.stdout.splitlines():
                try:
                    obj = json.loads(line)
                    if obj.get("type") == "match":
                        data = obj["data"]
                        results.append({
                            "file": data["path"]["text"],
                            "line_number": data["line_number"],
                            "line_content": data["lines"]["text"].rstrip(),
                        })
                except Exception:
                    pass
            return results[:50]
    except FileNotFoundError:
        pass  # ripgrep not available, use Python fallback

    # Python fallback
    for file_path in list_files(repo_path):
        try:
            content = Path(file_path).read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                if query.lower() in line.lower():
                    results.append({
                        "file": file_path,
                        "line_number": i,
                        "line_content": line.rstrip(),
                    })
                    if len(results) >= 50:
                        return results
        except Exception:
            pass

    return results


def find_functions(file_path: str) -> List[str]:
    """Use Python AST to extract all function and class names from a file."""
    try:
        content = Path(file_path).read_text(encoding="utf-8")
        tree = ast.parse(content)
        names = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(f"def {node.name}()")
            elif isinstance(node, ast.ClassDef):
                names.append(f"class {node.name}")
        return names
    except Exception:
        return []


def get_file_summary(file_path: str, max_lines: int = 50) -> str:
    """Return first max_lines of file + list of functions/classes found."""
    try:
        content = Path(file_path).read_text(encoding="utf-8")
        lines = content.splitlines()
        preview = "\n".join(lines[:max_lines])
        symbols = find_functions(file_path)
        symbols_str = ", ".join(symbols[:10]) if symbols else "none"
        return f"[Symbols: {symbols_str}]\n\n{preview}"
    except Exception as exc:
        return f"[Error reading file: {exc}]"
