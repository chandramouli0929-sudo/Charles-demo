"""LLM provider factory — returns the correct provider based on settings."""

from __future__ import annotations

from functools import lru_cache
from app.llm.base import BaseLLMProvider


@lru_cache(maxsize=2)
def get_llm(use_planner: bool = False) -> BaseLLMProvider:
    """
    Factory function. Returns a cached LLM provider instance.

    Args:
        use_planner: If True, use the more powerful planner model.
    """
    from app.config import settings
    from app.llm.provider import GeminiProvider, OpenAIProvider, AnthropicProvider

    provider = settings.llm_provider.lower()
    api_key = settings.llm_api_key
    model = settings.llm_planner_model if use_planner else settings.llm_model

    if provider == "gemini":
        return GeminiProvider(api_key=api_key, model=model)
    elif provider in ("openai", "openai_compatible"):
        return OpenAIProvider(
            api_key=api_key,
            model=model,
            base_url=settings.llm_base_url,
        )
    elif provider == "anthropic":
        return AnthropicProvider(api_key=api_key, model=model)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider!r}. Use: gemini | openai | anthropic | openai_compatible")
