"""
LLM provider abstraction.

Every agent that talks to a language model goes through `LLMClient.chat()`,
which takes a provider-neutral message list and optional tool specs and
returns text and/or tool calls. Three providers are implemented:

  - openai     — OpenAI Chat Completions (OPENAI_API_KEY)
  - anthropic  — Anthropic Messages API via the official SDK (ANTHROPIC_API_KEY)
  - ollama     — a local Ollama server through its OpenAI-compatible endpoint
                 (OLLAMA_BASE_URL, OLLAMA_MODEL); no key needed, works offline

Select with LLM_PROVIDER, or leave it on "auto" to pick the first provider
that has credentials (anthropic → openai → ollama).

Neutral message format (a superset of what the agents need):
  {"role": "system"|"user"|"assistant"|"tool", "content": str|None,
   "tool_calls": [ToolCall, ...]        # assistant only
   "tool_call_id": str, "name": str}    # tool only
"""

from __future__ import annotations

import json
import logging

from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    has_anthropic_key,
    has_openai_key,
)

logger = logging.getLogger(__name__)


class LLMNotConfigured(ValueError):
    """No usable provider: missing key or unknown LLM_PROVIDER."""


# ---------------------------------------------------------------------------
# Neutral types
# ---------------------------------------------------------------------------

@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON schema for the arguments object


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: dict = field(default_factory=dict)


class LLMClient(Protocol):
    provider: str
    model: str
    supports_tools: bool

    def chat(
        self,
        messages: list[dict],
        tools: list[ToolSpec] | None = None,
        *,
        max_tokens: int = 4000,
        temperature: float | None = 0.7,
        json_mode: bool = False,
    ) -> LLMResponse: ...


def _parse_args(raw: Any) -> dict:
    """Tool arguments arrive as a JSON string (OpenAI) or a dict (Anthropic)."""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        logger.warning("Could not parse tool arguments: %r", raw)
        return {}


# ---------------------------------------------------------------------------
# OpenAI (and OpenAI-compatible: Ollama)
# ---------------------------------------------------------------------------

class OpenAIProvider:
    provider = "openai"
    supports_tools = True

    def __init__(self, api_key: str, model: str, base_url: str | None = None, provider: str = "openai"):
        from openai import OpenAI

        self.provider = provider
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    @staticmethod
    def _to_openai(messages: list[dict]) -> list[dict]:
        out = []
        for m in messages:
            if m["role"] == "assistant" and m.get("tool_calls"):
                out.append({
                    "role": "assistant",
                    "content": m.get("content") or None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        }
                        for tc in m["tool_calls"]
                    ],
                })
            elif m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m.get("content") or ""})
            else:
                out.append({"role": m["role"], "content": m.get("content") or ""})
        return out

    def chat(self, messages, tools=None, *, max_tokens=4000, temperature=0.7, json_mode=False) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": self._to_openai(messages),
            "max_tokens": max_tokens,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if tools:
            kwargs["tools"] = [
                {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
                for t in tools
            ]
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        msg = choice.message
        calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=_parse_args(tc.function.arguments))
            for tc in (msg.tool_calls or [])
        ]
        usage = {}
        if resp.usage:
            usage = {"input_tokens": resp.usage.prompt_tokens, "output_tokens": resp.usage.completion_tokens}
        return LLMResponse(
            text=msg.content or "",
            tool_calls=calls,
            stop_reason="tool_use" if calls else (choice.finish_reason or "end_turn"),
            usage=usage,
        )


class OllamaProvider(OpenAIProvider):
    """Ollama exposes an OpenAI-compatible API at /v1; tool support depends on the model."""

    def __init__(self, base_url: str, model: str):
        super().__init__(api_key="ollama", model=model, base_url=base_url.rstrip("/") + "/v1", provider="ollama")

    def chat(self, messages, tools=None, *, max_tokens=4000, temperature=0.7, json_mode=False) -> LLMResponse:
        try:
            return super().chat(messages, tools, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode)
        except Exception as e:  # models without tool support return a 400 mentioning "tools"
            if tools and "tool" in str(e).lower():
                logger.warning("Ollama model %s does not support tools; retrying without", self.model)
                self.supports_tools = False
                return super().chat(messages, None, max_tokens=max_tokens, temperature=temperature, json_mode=json_mode)
            raise


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

class AnthropicProvider:
    provider = "anthropic"
    supports_tools = True

    def __init__(self, api_key: str, model: str):
        import anthropic

        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key)

    @staticmethod
    def to_anthropic(messages: list[dict]) -> tuple[str | None, list[dict]]:
        """
        Split off the system prompt and convert to Anthropic content blocks.
        Consecutive tool results are grouped into one user message, as the
        Messages API requires all results for a turn's tool_use blocks together.
        """
        system: str | None = None
        out: list[dict] = []
        pending_results: list[dict] = []

        def flush():
            nonlocal pending_results
            if pending_results:
                out.append({"role": "user", "content": pending_results})
                pending_results = []

        for m in messages:
            role = m["role"]
            if role == "system":
                system = (system + "\n\n" + m["content"]) if system else m["content"]
            elif role == "tool":
                pending_results.append({"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m.get("content") or ""})
            elif role == "assistant":
                flush()
                blocks: list[dict] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m.get("tool_calls") or []:
                    blocks.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments})
                out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})
            else:
                flush()
                out.append({"role": "user", "content": m.get("content") or ""})
        flush()
        return system, out

    def chat(self, messages, tools=None, *, max_tokens=4000, temperature=0.7, json_mode=False) -> LLMResponse:
        system, converted = self.to_anthropic(messages)
        if json_mode:
            # Structured-output-by-instruction keeps this provider-neutral
            converted = converted + [{"role": "user", "content": "Respond with a single JSON object and nothing else."}]
        kwargs: dict[str, Any] = {"model": self.model, "max_tokens": max_tokens, "messages": converted}
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools
            ]
        # Note: temperature is intentionally not sent — current Claude models reject sampling params.

        resp = self._client.messages.create(**kwargs)
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=_parse_args(block.input)))
        usage = {"input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
        return LLMResponse(text="".join(text_parts), tool_calls=calls, stop_reason=resp.stop_reason or "end_turn", usage=usage)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def resolve_provider() -> str | None:
    """Which provider LLM_PROVIDER + credentials resolve to, or None if nothing is usable."""
    choice = (LLM_PROVIDER or "auto").strip().lower()
    if choice == "auto":
        if has_anthropic_key():
            return "anthropic"
        if has_openai_key():
            return "openai"
        if OLLAMA_MODEL:
            return "ollama"
        return None
    if choice == "anthropic":
        return "anthropic" if has_anthropic_key() else None
    if choice == "openai":
        return "openai" if has_openai_key() else None
    if choice == "ollama":
        return "ollama" if OLLAMA_MODEL else None
    return None


def resolve_model(provider: str | None) -> str | None:
    return {"anthropic": ANTHROPIC_MODEL, "openai": OPENAI_MODEL, "ollama": OLLAMA_MODEL}.get(provider or "")


def llm_configured() -> bool:
    return resolve_provider() is not None


_client: LLMClient | None = None
_client_key: tuple | None = None


def get_llm() -> LLMClient:
    """Build (once) and return the configured provider client."""
    global _client, _client_key
    if _client is not None and _client_key == ("injected",):
        return _client
    provider = resolve_provider()
    if provider is None:
        choice = (LLM_PROVIDER or "auto").strip().lower()
        hint = {
            "openai": "set OPENAI_API_KEY",
            "anthropic": "set ANTHROPIC_API_KEY",
            "ollama": "set OLLAMA_MODEL (and run an Ollama server)",
        }.get(choice, "set OPENAI_API_KEY or ANTHROPIC_API_KEY, or OLLAMA_MODEL for a local model")
        raise LLMNotConfigured(
            f"No LLM provider is configured (LLM_PROVIDER={choice}): {hint}, "
            "or run with skip_recommendations=True."
        )
    key = (provider, resolve_model(provider), OLLAMA_BASE_URL)
    if _client is None or _client_key != key:
        if provider == "anthropic":
            _client = AnthropicProvider(ANTHROPIC_API_KEY, ANTHROPIC_MODEL)
        elif provider == "openai":
            _client = OpenAIProvider(OPENAI_API_KEY, OPENAI_MODEL)
        else:
            _client = OllamaProvider(OLLAMA_BASE_URL, OLLAMA_MODEL)
        _client_key = key
        logger.info("LLM provider: %s (%s)", provider, resolve_model(provider))
    return _client


def set_llm(client: LLMClient | None) -> None:
    """Inject a client (tests, or embedding the pipeline with a custom provider)."""
    global _client, _client_key
    _client = client
    _client_key = ("injected",) if client else None


def env_provider_summary() -> dict:
    provider = resolve_provider()
    return {
        "llm_provider": provider,
        "llm_model": resolve_model(provider),
        "llm_configured": provider is not None,
        "llm_provider_setting": (LLM_PROVIDER or "auto"),
        "ollama_base_url": OLLAMA_BASE_URL if provider == "ollama" else None,
    }


__all__ = [
    "AnthropicProvider", "LLMClient", "LLMNotConfigured", "LLMResponse", "OllamaProvider",
    "OpenAIProvider", "ToolCall", "ToolSpec", "env_provider_summary", "get_llm", "llm_configured",
    "resolve_model", "resolve_provider", "set_llm",
]
