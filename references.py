"""Reference materials handling.

Four categories:
- glossary:    list of (source_term, target_term) pairs
- paired:      list of (source, target) translation examples
- parallel:    list of target-language texts (genre voice exemplars)
- style_guide: free-form markdown / text
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field


@dataclass
class References:
    glossary: list[tuple[str, str]] = field(default_factory=list)
    paired: list[tuple[str, str]] = field(default_factory=list)
    parallel: list[tuple[str, str]] = field(default_factory=list)  # (filename, text)
    style_guide: str | None = None

    def is_empty(self) -> bool:
        return not (self.glossary or self.paired or self.parallel or self.style_guide)

    def summary(self) -> str:
        parts = []
        parts.append(f"glossary entries: {len(self.glossary)}")
        parts.append(f"paired examples: {len(self.paired)}")
        parts.append(f"parallel texts: {len(self.parallel)}")
        parts.append(f"style guide: {'yes' if self.style_guide else 'no'}")
        return " · ".join(parts)

    def to_context_block(self, *, max_paired: int = 8, max_parallel: int = 3) -> str:
        """Format for inclusion in an LLM prompt. Empty -> '(none provided)'."""
        if self.is_empty():
            return "(no reference materials provided)"
        parts: list[str] = []

        if self.style_guide:
            parts.append("## Style guide\n\n" + self.style_guide.strip())

        if self.glossary:
            parts.append("## Glossary (source → target)\n")
            for s, t in self.glossary:
                parts.append(f"- `{s}` → `{t}`")

        if self.paired:
            parts.append("## Paired translation examples\n")
            for i, (s, t) in enumerate(self.paired[:max_paired], 1):
                parts.append(f"### Example {i}\n**Source:** {s}\n**Target:** {t}")
            if len(self.paired) > max_paired:
                parts.append(f"_(+{len(self.paired) - max_paired} more not shown)_")

        if self.parallel:
            parts.append("## Parallel target-language texts (genre voice exemplars)\n")
            for i, (name, doc) in enumerate(self.parallel[:max_parallel], 1):
                snippet = doc.strip()
                if len(snippet) > 1500:
                    snippet = snippet[:1500] + "\n[...truncated...]"
                parts.append(f"### {name}\n{snippet}")
            if len(self.parallel) > max_parallel:
                parts.append(f"_(+{len(self.parallel) - max_parallel} more not shown)_")

        return "\n\n".join(parts)


def parse_pair_table(text: str) -> list[tuple[str, str]]:
    """Parse TSV or CSV with two columns. Tolerates optional header row."""
    text = text.strip()
    if not text:
        return []

    # Auto-detect delimiter
    sample = text.splitlines()[0]
    delim = "\t" if "\t" in sample else ","

    pairs: list[tuple[str, str]] = []
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    for i, row in enumerate(reader):
        if len(row) < 2:
            continue
        a, b = row[0].strip(), row[1].strip()
        if not a or not b:
            continue
        # Skip header row if it looks like one
        if i == 0 and a.lower() in {"source", "src", "原文", "source_term"}:
            continue
        pairs.append((a, b))
    return pairs
