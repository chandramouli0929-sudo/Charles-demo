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
    import os
    from app.config import settings
    from app.llm.provider import GeminiProvider, OpenAIProvider, AnthropicProvider

    provider = (os.environ.get("LLM_PROVIDER") or settings.llm_provider or "gemini").lower()
    api_key = (
        settings.llm_api_key
        or os.environ.get("LLM_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or ""
    )

    if not api_key:
        try:
            import streamlit as st
            api_key = (
                st.secrets.get("LLM_API_KEY")
                or st.secrets.get("llm_api_key")
                or st.secrets.get("GEMINI_API_KEY")
                or st.secrets.get("gemini_api_key")
                or st.secrets.get("OPENAI_API_KEY")
                or st.secrets.get("openai_api_key")
                or ""
            )
            if not provider or provider == "gemini":
                provider = (st.secrets.get("LLM_PROVIDER") or st.secrets.get("llm_provider") or provider).lower()
        except Exception:
            pass

    model = os.environ.get("LLM_PLANNER_MODEL") or settings.llm_planner_model if use_planner else (os.environ.get("LLM_MODEL") or settings.llm_model)

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
