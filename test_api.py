"""Minimal provider connectivity test.

Run after putting your API key in .env:
    source .venv/bin/activate
    python test_api.py
"""
from dotenv import load_dotenv

load_dotenv()

import api

if not api.has_api_key():
    provider = api.provider_label()
    key_env = api.PROVIDERS[api.get_provider()]["key_env"]
    raise SystemExit(f"ERROR: set {key_env} in .env first for {provider}.")

text, usage = api.call_model(
    system="You are a concise multilingual assistant.",
    user="Say 'hello from the translation API' in Japanese, English, and Traditional Chinese. One line each.",
    max_tokens=200,
    temperature=0.0,
)

print(f"Provider: {api.provider_label()}")
print(f"Model: {api.get_model()}")
print(f"Input tokens: {usage['input_tokens']}")
print(f"Output tokens: {usage['output_tokens']}")
print("---")
print(text)
