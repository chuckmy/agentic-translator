"""Centralized LLM provider and API key management.

Supported providers:
  - anthropic: Anthropic Messages API
  - openai: OpenAI Responses API

Priority for the selected provider's API key, highest first:
  1. Runtime override set via set_api_key() (used when the user supplies a key in the UI)
  2. Provider-specific key in .env (developer convenience; not present in public deployments)

If neither is set, call_model() raises a clear error that the UI can surface.
"""
from __future__ import annotations

import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

PROVIDERS = {
    "anthropic": {
        "label": "Anthropic",
        "key_env": "ANTHROPIC_API_KEY",
        "model_env": "ANTHROPIC_MODEL",
        "default_model": "claude-sonnet-4-6",
        "placeholder": "sk-ant-api03-...",
    },
    "openai": {
        "label": "OpenAI",
        "key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "default_model": "gpt-5.4-mini",
        "placeholder": "sk-...",
    },
}

PLACEHOLDER = "REPLACE_ME"

_provider = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()
if _provider not in PROVIDERS:
    _provider = "anthropic"

_runtime_overrides: dict[str, str | None] = {name: None for name in PROVIDERS}


def _is_real(key: str | None) -> bool:
    return bool(key) and PLACEHOLDER not in (key or "")


def provider_names() -> list[str]:
    return list(PROVIDERS.keys())


def provider_label(provider: str | None = None) -> str:
    return PROVIDERS[get_provider() if provider is None else provider]["label"]


def provider_placeholder(provider: str | None = None) -> str:
    return PROVIDERS[get_provider() if provider is None else provider]["placeholder"]


def set_provider(provider: str) -> None:
    global _provider
    provider = provider.strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")
    _provider = provider


def get_provider() -> str:
    return _provider


def set_api_key(key: str | None, provider: str | None = None) -> None:
    """Override the selected provider's API key. Pass None or "" to clear it."""
    provider = get_provider() if provider is None else provider
    _runtime_overrides[provider] = (key or "").strip() or None


def get_api_key(provider: str | None = None) -> str:
    provider = get_provider() if provider is None else provider
    if _is_real(_runtime_overrides.get(provider)):
        return _runtime_overrides[provider]  # type: ignore[return-value]
    env_key = os.environ.get(PROVIDERS[provider]["key_env"], "").strip()
    if _is_real(env_key):
        return env_key
    label = provider_label(provider)
    key_env = PROVIDERS[provider]["key_env"]
    raise RuntimeError(
        f"No {label} API key configured. "
        f"Enter your key in the sidebar (or set {key_env} in .env)."
    )


def has_api_key(provider: str | None = None) -> bool:
    provider = get_provider() if provider is None else provider
    if _is_real(_runtime_overrides.get(provider)):
        return True
    return _is_real(os.environ.get(PROVIDERS[provider]["key_env"], ""))


def env_has_real_key(provider: str | None = None) -> bool:
    provider = get_provider() if provider is None else provider
    return _is_real(os.environ.get(PROVIDERS[provider]["key_env"], ""))


def get_model(provider: str | None = None) -> str:
    provider = get_provider() if provider is None else provider
    return os.environ.get(
        PROVIDERS[provider]["model_env"],
        PROVIDERS[provider]["default_model"],
    )


def _usage(input_tokens: int | None, output_tokens: int | None) -> dict:
    return {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
    }


def _anthropic_text_and_usage(resp) -> tuple[str, dict]:
    text = "".join(b.text for b in resp.content if b.type == "text")
    return text, _usage(resp.usage.input_tokens, resp.usage.output_tokens)


def _openai_text_and_usage(resp) -> tuple[str, dict]:
    text = getattr(resp, "output_text", None)
    if text is None:
        chunks = []
        for item in getattr(resp, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", "") in {"output_text", "text"}:
                    chunks.append(getattr(content, "text", ""))
        text = "".join(chunks)
    usage = getattr(resp, "usage", None)
    return text, _usage(
        getattr(usage, "input_tokens", 0),
        getattr(usage, "output_tokens", 0),
    )


def _provider_error_message(provider: str, exc: Exception) -> str:
    label = provider_label(provider)
    key_env = PROVIDERS[provider]["key_env"]
    name = exc.__class__.__name__
    status = getattr(exc, "status_code", None)
    if status == 401 or "Authentication" in name:
        return (
            f"{label} authentication failed. "
            f"Check the API key entered in the sidebar or {key_env} in .env."
        )
    return f"{label} API call failed: {exc}"


def call_model(
    *,
    system: str,
    user: str | None = None,
    messages: list[dict] | None = None,
    temperature: float,
    max_tokens: int,
) -> tuple[str, dict]:
    """Call the selected provider and return (text, usage)."""
    if messages is None:
        if user is None:
            raise ValueError("Provide either user or messages.")
        messages = [{"role": "user", "content": user}]

    provider = get_provider()
    if provider == "anthropic":
        try:
            resp = Anthropic(api_key=get_api_key("anthropic")).messages.create(
                model=get_model("anthropic"),
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=messages,
            )
        except Exception as exc:
            raise RuntimeError(_provider_error_message(provider, exc)) from None
        return _anthropic_text_and_usage(resp)

    if provider == "openai":
        try:
            resp = OpenAI(api_key=get_api_key("openai")).responses.create(
                model=get_model("openai"),
                instructions=system,
                input=messages,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        except Exception as exc:
            raise RuntimeError(_provider_error_message(provider, exc)) from None
        return _openai_text_and_usage(resp)

    raise ValueError(f"Unsupported provider: {provider}")
