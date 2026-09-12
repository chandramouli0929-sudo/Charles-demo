"""LLM Provider abstraction — base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """Send a chat request and return the text response."""
        ...

    @abstractmethod
    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> dict:
        """Send a chat request expecting a JSON response. Returns parsed dict."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the active model name."""
        ...
