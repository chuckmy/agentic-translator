"""Document-level translation memory (DelTA-lite).

Three persistent layers across chunks of a single document:
  - proper_nouns:    source_term -> target_term ledger (established terminology)
  - summary:         50-150 word running summary in the target language
  - prev_source / prev_translation: the immediately preceding chunk (short-term context)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from api import call_model

ROOT = Path(__file__).parent
PROMPTS = ROOT / "prompts"


@dataclass
class DocumentMemory:
    proper_nouns: dict[str, str] = field(default_factory=dict)
    summary: str = ""
    prev_source: str = ""
    prev_translation: str = ""
    chunks_completed: int = 0

    def is_empty(self) -> bool:
        return self.chunks_completed == 0

    def to_terms_block(self) -> str:
        if not self.proper_nouns:
            return "(no terminology established yet)"
        lines = ["| Source | Target |", "|---|---|"]
        for s, t in self.proper_nouns.items():
            lines.append(f"| {s} | {t} |")
        return "\n".join(lines)

    def to_prev_chunk_block(self, target_language: str) -> str:
        if not self.prev_source:
            return "(this is the first chunk)"
        return (
            f"**Previous chunk source:**\n{self.prev_source}\n\n"
            f"**Previous chunk translation ({target_language}):**\n{self.prev_translation}"
        )

    def to_summary_block(self) -> str:
        return self.summary or "(no summary yet — first chunk)"


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


def update_memory(
    *,
    memory: DocumentMemory,
    chunk_source: str,
    chunk_translation: str,
    target_language: str,
) -> tuple[dict, dict]:
    """Run one memory-update LLM call. Returns (delta, usage).

    delta = {"new_terms": {...}, "updated_summary": "...", "notes": "..."}
    Mutates `memory` in place.
    """
    system = _read(PROMPTS / "update_memory.txt")
    user = (
        f"TARGET LANGUAGE: {target_language}\n\n"
        f"CURRENT MEMORY:\n"
        f"- Proper-noun ledger:\n{memory.to_terms_block()}\n"
        f"- Running summary:\n{memory.summary or '(empty — this is the first chunk)'}\n\n"
        f"CHUNK JUST TRANSLATED:\n"
        f"SOURCE:\n{chunk_source}\n\n"
        f"TRANSLATION:\n{chunk_translation}"
    )
    raw, usage = call_model(
        system=system,
        user=user,
        temperature=0.0,
        max_tokens=1500,
    )
    delta = _extract_json(raw)

    # Mutate memory
    new_terms = delta.get("new_terms", {}) or {}
    for k, v in new_terms.items():
        memory.proper_nouns[str(k)] = str(v)
    if delta.get("updated_summary"):
        memory.summary = delta["updated_summary"]
    memory.prev_source = chunk_source
    memory.prev_translation = chunk_translation
    memory.chunks_completed += 1

    return delta, usage
