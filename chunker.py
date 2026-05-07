r"""Split source text into paragraph-sized chunks.

Strategy:
- Split on blank-line paragraph breaks (\n\s*\n).
- If any paragraph exceeds max_chars, further split on sentence boundaries
  (Japanese: 。！？; Latin: . ! ?).
- Never split mid-sentence in the simple cases.
- Returns list of non-empty chunk strings, original order preserved.
"""
from __future__ import annotations

import re

_PARA_SPLIT = re.compile(r"\n\s*\n+")
_SENT_SPLIT = re.compile(
    r"(?<=[。！？.!?])(?=\s|[「『\"\(\[]|$)|(?<=[。！？])"
)


def _split_sentences(paragraph: str) -> list[str]:
    parts = [p.strip() for p in _SENT_SPLIT.split(paragraph) if p and p.strip()]
    return parts or [paragraph.strip()]


def _pack(units: list[str], max_chars: int) -> list[str]:
    """Greedy-pack units (sentences) into chunks no larger than max_chars."""
    chunks: list[str] = []
    buf: list[str] = []
    size = 0
    for u in units:
        u_len = len(u)
        if buf and size + u_len + 1 > max_chars:
            chunks.append(" ".join(buf).strip())
            buf, size = [u], u_len
        else:
            buf.append(u)
            size += u_len + 1
    if buf:
        chunks.append(" ".join(buf).strip())
    return chunks


def split_into_chunks(text: str, *, max_chars: int = 1500) -> list[str]:
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in _PARA_SPLIT.split(text) if p.strip()]
    chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            chunks.append(para)
        else:
            sentences = _split_sentences(para)
            chunks.extend(_pack(sentences, max_chars))
    return chunks
