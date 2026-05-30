r"""Segment-aware chunking for translation.

Strategy E (hybrid):
- A sentence is the atomic *segment* — the minimal translation unit
  (Newmark's TU; matches Trados/memoQ "segment" terminology).
- Each segment gets a stable ID: "P{para}.S{sent}" (1-indexed).
- Segments are grouped into *chunks* for translation:
    * paragraph boundary = HARD break (no chunk crosses paragraphs)
    * within a paragraph, group up to max_segments sentences OR max_chars chars,
      whichever comes first
- A Chunk exposes .text for legacy string-consumers and .segments for
  bilingual export, trace logs, and segment-level alignment.

This module is dependency-free.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_PARA_SPLIT = re.compile(r"\n\s*\n+")
_SENT_SPLIT = re.compile(
    r"(?<=[。！？.!?])(?=\s|[「『\"\(\[]|$)|(?<=[。！？])"
)


@dataclass
class Segment:
    """One sentence-sized translation unit."""
    para_idx: int   # 1-indexed paragraph number in the whole document
    sent_idx: int   # 1-indexed sentence within its paragraph
    text: str

    @property
    def id(self) -> str:
        return f"P{self.para_idx}.S{self.sent_idx}"


@dataclass
class Chunk:
    """A group of contiguous segments from the same paragraph."""
    index: int
    segments: list[Segment] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments)

    @property
    def id_range(self) -> str:
        if not self.segments:
            return ""
        if len(self.segments) == 1:
            return self.segments[0].id
        return f"{self.segments[0].id}–{self.segments[-1].id}"

    @property
    def para_idx(self) -> int | None:
        return self.segments[0].para_idx if self.segments else None


def _split_sentences(paragraph: str) -> list[str]:
    parts = [p.strip() for p in _SENT_SPLIT.split(paragraph) if p and p.strip()]
    return parts or [paragraph.strip()]


def split_into_segments(text: str) -> list[Segment]:
    """Split text into segments without chunk grouping (for inspection/export)."""
    text = text.strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in _PARA_SPLIT.split(text) if p.strip()]
    segments: list[Segment] = []
    for para_idx, para in enumerate(paragraphs, start=1):
        for sent_idx, sent in enumerate(_split_sentences(para), start=1):
            segments.append(Segment(para_idx=para_idx, sent_idx=sent_idx, text=sent))
    return segments


def split_into_chunks(
    text: str,
    *,
    max_chars: int = 1500,
    max_segments: int = 6,
) -> list[Chunk]:
    """Split text into segment-aware chunks.

    Args:
        text: source text
        max_chars: soft cap on chunk size in characters
        max_segments: soft cap on number of sentences per chunk

    Returns:
        list of Chunk objects, each containing ordered Segments with stable IDs.
        Paragraph boundaries are never crossed.
    """
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in _PARA_SPLIT.split(text) if p.strip()]
    chunks: list[Chunk] = []
    chunk_idx = 0

    for para_idx, para in enumerate(paragraphs, start=1):
        sentences = _split_sentences(para)
        para_segments = [
            Segment(para_idx=para_idx, sent_idx=i, text=s)
            for i, s in enumerate(sentences, start=1)
        ]

        buf: list[Segment] = []
        size = 0
        for seg in para_segments:
            seg_len = len(seg.text)
            would_exceed = bool(buf) and (
                size + seg_len + 1 > max_chars or len(buf) >= max_segments
            )
            if would_exceed:
                chunk_idx += 1
                chunks.append(Chunk(index=chunk_idx, segments=buf))
                buf, size = [seg], seg_len
            else:
                buf.append(seg)
                size += seg_len + 1
        if buf:
            chunk_idx += 1
            chunks.append(Chunk(index=chunk_idx, segments=buf))

    return chunks
