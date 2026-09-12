"""Git tools — deterministic git operations via subprocess."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _run_git(args: list[str], cwd: str, timeout: int = 15) -> tuple[bool, str]:
    """Run a git command and return (success, output)."""
    try:
        result = subprocess.run(
            ["git", "--no-pager"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "GIT_PAGER": "cat"},
        )
        return result.returncode == 0, (result.stdout + result.stderr).strip()
    except FileNotFoundError:
        return False, "git not found"
    except subprocess.TimeoutExpired:
        return False, "git command timed out"
    except Exception as exc:
        return False, str(exc)


def git_status(repo_path: str) -> str:
    ok, out = _run_git(["-C", repo_path, "status", "--short"], cwd=repo_path)
    return out if ok else ""


def git_diff(repo_path: str) -> str:
    ok, out = _run_git(["-C", repo_path, "diff", "HEAD"], cwd=repo_path)
    if not ok or not out:
        # Try unstaged diff
        ok2, out2 = _run_git(["-C", repo_path, "diff"], cwd=repo_path)
        return out2 if ok2 else ""
    return out


def git_log(repo_path: str, n: int = 5) -> str:
    ok, out = _run_git(["-C", repo_path, "log", "--oneline", f"-{n}"], cwd=repo_path)
    return out if ok else "No git history available"


def git_init(repo_path: str) -> bool:
    Path(repo_path).mkdir(parents=True, exist_ok=True)
    ok, _ = _run_git(["init", repo_path], cwd=repo_path)
    if ok:
        _run_git(["-C", repo_path, "config", "user.email", "agentforge@demo.com"], cwd=repo_path)
        _run_git(["-C", repo_path, "config", "user.name", "AgentForge"], cwd=repo_path)
    return ok


def git_add_all(repo_path: str) -> bool:
    ok, _ = _run_git(["-C", repo_path, "add", "-A"], cwd=repo_path)
    return ok


def git_commit(repo_path: str, message: str) -> bool:
    ok, _ = _run_git(
        ["-C", repo_path, "commit", "-m", message, "--allow-empty"],
        cwd=repo_path,
    )
    return ok


def create_branch(repo_path: str, branch_name: str) -> bool:
    ok, _ = _run_git(
        ["-C", repo_path, "checkout", "-b", branch_name],
        cwd=repo_path,
    )
    return ok
