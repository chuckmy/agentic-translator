"""Minimal API connectivity test.

Run after putting your API key in .env:
    source .venv/bin/activate
    python test_api.py
"""
import os
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

api_key = os.environ.get("ANTHROPIC_API_KEY", "")
model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

if not api_key or "REPLACE_ME" in api_key:
    raise SystemExit("ERROR: set ANTHROPIC_API_KEY in .env first.")

client = Anthropic(api_key=api_key)

resp = client.messages.create(
    model=model,
    max_tokens=200,
    messages=[
        {"role": "user", "content": "Say 'hello from Claude' in Japanese, English, and Traditional Chinese. One line each."}
    ],
)

print(f"Model: {resp.model}")
print(f"Stop reason: {resp.stop_reason}")
print(f"Input tokens: {resp.usage.input_tokens}")
print(f"Output tokens: {resp.usage.output_tokens}")
print("---")
for block in resp.content:
    if block.type == "text":
        print(block.text)
