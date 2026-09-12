"""
LLM Provider implementations.
Supports: Gemini, OpenAI, Anthropic, OpenAI-compatible (vLLM, etc.)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Gemini Provider
# ─────────────────────────────────────────────────────────────────────────────
FALLBACK_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-3.6-flash",
    "gemma-4-26b-a4b-it",
]


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-3.6-flash"):
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=api_key)
        self._model_name = model
        self._genai = genai

    @property
    def model_name(self) -> str:
        return self._model_name

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        prompt = self._format_messages(messages)
        config = self._genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        models_to_try = [self._model_name] + [m for m in FALLBACK_MODELS if m != self._model_name]
        last_error = None

        for m_name in models_to_try:
            try:
                client = self._genai.GenerativeModel(m_name)
                response = client.generate_content(prompt, generation_config=config)
                if response and response.text:
                    if m_name != self._model_name:
                        logger.info("Auto-switched from %s to available model: %s", self._model_name, m_name)
                    return response.text
            except Exception as exc:
                err_str = str(exc).lower()
                if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                    logger.warning("Model %s quota exceeded, trying fallback...", m_name)
                    last_error = exc
                    continue
                logger.error("Gemini call error on %s: %s", m_name, exc)
                last_error = exc
                continue

        if last_error:
            raise last_error
        return ""

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> dict:
        # Append JSON instruction
        msgs = list(messages)
        if msgs and msgs[-1]["role"] == "user":
            msgs[-1] = {
                "role": "user",
                "content": msgs[-1]["content"] + "\n\nRespond with valid JSON only. No markdown, no explanation.",
            }
        text = self.chat(msgs, temperature=temperature, max_tokens=max_tokens)
        return _parse_json(text)

    def _format_messages(self, messages: list[dict[str, str]]) -> str:
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                parts.append(f"[System Instructions]\n{content}")
            elif role == "assistant":
                parts.append(f"[Assistant]\n{content}")
            else:
                parts.append(f"[User]\n{content}")
        return "\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI Provider
# ─────────────────────────────────────────────────────────────────────────────
class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str = ""):
        from openai import OpenAI  # type: ignore

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self._model_name = model

    @property
    def model_name(self) -> str:
        return self._model_name

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self._model_name,
            messages=messages,  # type: ignore
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> dict:
        response = self._client.chat.completions.create(
            model=self._model_name,
            messages=messages,  # type: ignore
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or "{}"
        return json.loads(text)


# ─────────────────────────────────────────────────────────────────────────────
# Anthropic Provider
# ─────────────────────────────────────────────────────────────────────────────
class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-20241022"):
        import anthropic  # type: ignore

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model_name = model

    @property
    def model_name(self) -> str:
        return self._model_name

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        system_msgs = [m["content"] for m in messages if m["role"] == "system"]
        user_msgs = [m for m in messages if m["role"] != "system"]
        system = "\n".join(system_msgs) if system_msgs else None

        kwargs_: dict[str, Any] = {
            "model": self._model_name,
            "max_tokens": max_tokens,
            "messages": user_msgs,
        }
        if system:
            kwargs_["system"] = system

        response = self._client.messages.create(**kwargs_)
        return response.content[0].text if response.content else ""

    def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> dict:
        msgs = list(messages)
        if msgs and msgs[-1]["role"] == "user":
            msgs[-1] = {
                "role": "user",
                "content": msgs[-1]["content"] + "\n\nRespond with valid JSON only.",
            }
        text = self.chat(msgs, temperature=temperature, max_tokens=max_tokens)
        return _parse_json(text)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _parse_json(text: str) -> dict:
    """Extract JSON from a string that may contain markdown fences."""
    # Try direct parse
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip markdown fences
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try finding first { ... }
    match2 = re.search(r"\{[\s\S]+\}", text)
    if match2:
        try:
            return json.loads(match2.group(0))
        except json.JSONDecodeError:
            pass
    return {"error": "Failed to parse JSON", "raw": text}
