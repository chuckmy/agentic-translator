"""Centralized Anthropic API key management.

Priority for the API key, highest first:
  1. Runtime override set via set_api_key() (used when the user supplies a key in the UI)
  2. ANTHROPIC_API_KEY in .env (developer convenience; not present in public deployments)

If neither is set, get_client() raises a clear error that the UI can surface.
"""
from __future__ import annotations

import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
PLACEHOLDER = "REPLACE_ME"

_runtime_override: str | None = None


def _is_real(key: str | None) -> bool:
    return bool(key) and PLACEHOLDER not in (key or "")


def set_api_key(key: str | None) -> None:
    """Override the API key for subsequent calls. Pass None or "" to clear the override."""
    global _runtime_override
    _runtime_override = (key or "").strip() or None


def get_api_key() -> str:
    if _is_real(_runtime_override):
        return _runtime_override  # type: ignore[return-value]
    env_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if _is_real(env_key):
        return env_key
    raise RuntimeError(
        "No Anthropic API key configured. "
        "Enter your key in the sidebar (or set ANTHROPIC_API_KEY in .env)."
    )


def has_api_key() -> bool:
    if _is_real(_runtime_override):
        return True
    return _is_real(os.environ.get("ANTHROPIC_API_KEY", ""))


def env_has_real_key() -> bool:
    return _is_real(os.environ.get("ANTHROPIC_API_KEY", ""))


def get_client() -> Anthropic:
    return Anthropic(api_key=get_api_key())


def get_model() -> str:
    return DEFAULT_MODEL
