"""
Requirement Agent — Normalizes and structures the user's requirement.
"""

from __future__ import annotations

import logging
from app.llm.config import get_llm

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Senior Requirements Engineer for a URL shortener engineering project.

Your job is to take a user's natural-language requirement and produce a structured, clear engineering specification.

Guidelines:
- Normalize ambiguous language into precise engineering statements
- Separate functional requirements (what the system must DO) from non-functional (performance, security, reliability)
- Make implicit assumptions explicit
- Define clear acceptance criteria
- For brownfield changes: assume the existing app has FastAPI + SQLAlchemy + Redis
- For bug fixes: frame as "the system should always..." 
- For refactoring: focus on code quality metrics, not new functionality

Respond ONLY with valid JSON:
{
  "normalized_requirement": "Clear, unambiguous one-paragraph statement of what needs to be built/changed",
  "functional_requirements": ["FR1: ...", "FR2: ...", ...],
  "non_functional_requirements": ["NFR1: ...", ...],
  "assumptions": ["Assumption 1: ...", ...],
  "ambiguities": ["Remaining uncertainty 1: ...", ...],
  "acceptance_criteria": ["AC1: Given... When... Then...", ...]
}
"""


class RequirementAgent:
    """Normalizes and structures engineering requirements."""

    def __init__(self) -> None:
        self._llm = get_llm()

    def analyze(
        self,
        user_request: str,
        request_type: str,
        clarification_answer: str = "",
    ) -> dict:
        """
        Analyze and normalize the requirement.

        Args:
            user_request: Original user input
            request_type: greenfield | brownfield | bugfix | refactor | ambiguous
            clarification_answer: Optional follow-up answer from user
        """
        logger.info("RequirementAgent analyzing: type=%s", request_type)

        context = f"Request type: {request_type}\nUser request: {user_request}"
        if clarification_answer:
            context += f"\nUser clarification: {clarification_answer}"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        try:
            result = self._llm.chat_json(messages, temperature=0.2)
            return {
                "normalized_requirement": result.get("normalized_requirement", user_request),
                "functional_requirements": result.get("functional_requirements", []),
                "non_functional_requirements": result.get("non_functional_requirements", []),
                "assumptions": result.get("assumptions", []),
                "ambiguities": result.get("ambiguities", []),
                "acceptance_criteria": result.get("acceptance_criteria", []),
            }
        except Exception as exc:
            logger.error("RequirementAgent failed: %s", exc)
            return {
                "normalized_requirement": user_request,
                "functional_requirements": [],
                "non_functional_requirements": [],
                "assumptions": ["System uses FastAPI + SQLAlchemy + SQLite/PostgreSQL + Redis"],
                "ambiguities": [],
                "acceptance_criteria": [],
            }
