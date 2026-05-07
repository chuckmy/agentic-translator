"""Spec proposal and interactive refinement.

- propose_spec(): one-shot generation of an initial spec from source + references
- refine_spec(): multi-turn refinement, returns (new_spec, comment)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from api import get_client, get_model
from references import References

ROOT = Path(__file__).parent
PROMPTS = ROOT / "prompts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text).rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in:\n{text}")
    return json.loads(text[start : end + 1])


_DELIM_RE = re.compile(
    r"<<<COMMENT>>>\s*(?P<comment>.*?)\s*<<<END_COMMENT>>>"
    r".*?"
    r"<<<SPEC>>>\s*(?P<spec>.*?)\s*<<<END_SPEC>>>",
    re.DOTALL,
)


def _parse_delimited_refine(text: str) -> tuple[str, str]:
    """Parse the delimiter-based refine_spec output. Returns (spec, comment)."""
    m = _DELIM_RE.search(text)
    if not m:
        raise ValueError(
            "Could not find <<<COMMENT>>>/<<<SPEC>>> blocks in model output:\n" + text[:500]
        )
    return m.group("spec").strip(), m.group("comment").strip()


def propose_spec(
    *,
    source_text: str,
    source_language: str,
    target_language: str,
    references: References,
) -> tuple[str, dict]:
    """Generate an initial spec proposal. Returns (spec_markdown, usage)."""
    system = _read(PROMPTS / "propose_spec.txt")
    user = (
        f"SOURCE LANGUAGE: {source_language}\n"
        f"TARGET LANGUAGE: {target_language}\n\n"
        f"REFERENCE MATERIALS:\n{references.to_context_block()}\n\n"
        f"SOURCE TEXT:\n{source_text}"
    )
    resp = get_client().messages.create(
        model=get_model(),
        max_tokens=3000,
        temperature=0.2,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }
    return text, usage


def refine_spec(
    *,
    source_text: str,
    source_language: str,
    target_language: str,
    references: References,
    current_spec: str,
    conversation: list[dict],  # list of {"role": "user"|"assistant", "content": str}
    user_message: str,
) -> tuple[str, str, dict]:
    """Refine the spec given a new user message. Returns (new_spec, comment, usage)."""
    system = _read(PROMPTS / "refine_spec.txt")

    context = (
        f"SOURCE LANGUAGE: {source_language}\n"
        f"TARGET LANGUAGE: {target_language}\n\n"
        f"REFERENCE MATERIALS:\n{references.to_context_block()}\n\n"
        f"SOURCE TEXT:\n{source_text}\n\n"
        f"CURRENT DRAFT SPEC:\n{current_spec}"
    )

    messages = [{"role": "user", "content": context}]
    # Replay prior conversation as a compressed assistant ack + alternating turns
    if conversation:
        messages.append({"role": "assistant", "content": "Acknowledged. I have the context above."})
        messages.extend(conversation)
    messages.append({"role": "user", "content": user_message})

    resp = get_client().messages.create(
        model=get_model(),
        max_tokens=4000,
        temperature=0.2,
        system=system,
        messages=messages,
    )
    raw = "".join(b.text for b in resp.content if b.type == "text")
    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }
    # Try delimiter format first (current); fall back to JSON for older outputs
    try:
        new_spec, comment = _parse_delimited_refine(raw)
    except ValueError:
        try:
            data = _extract_json(raw)
            new_spec = data["spec_markdown"]
            comment = data["comment"]
        except Exception as e:
            raise ValueError(
                f"Could not parse refine_spec output (tried delimiters and JSON): {e}\n"
                f"Raw output:\n{raw[:1000]}"
            )
    return new_spec, comment, usage
