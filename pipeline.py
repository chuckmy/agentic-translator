"""Agentic translation pipeline.

Implements the 4-stage cycle:
  1. Identification  -> situational analysis as JSON
  2. Prompting       -> deterministic assembly of the translation prompt
  3. Generation      -> the translation itself
  4. Verification    -> independent judgement; loop back if 'revise'

CLI usage:
    python pipeline.py --source "..." --target "English"
or:
    python pipeline.py --source-file path/to/source.txt --target "English"
"""
from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable

from api import get_client, get_model
from chunker import split_into_chunks
from memory import DocumentMemory, update_memory
from references import References

ROOT = Path(__file__).parent
PROMPTS = ROOT / "prompts"
SPECS = ROOT / "specs"


# --- helpers ---------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_json(text: str) -> dict:
    """Be tolerant: find the outermost {...} even if the model added prose."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text).rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in:\n{text}")
    return json.loads(text[start : end + 1])


def _call(system: str, user: str, *, temperature: float, max_tokens: int = 2000) -> tuple[str, dict]:
    resp = get_client().messages.create(
        model=get_model(),
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    usage = {
        "input_tokens": resp.usage.input_tokens,
        "output_tokens": resp.usage.output_tokens,
    }
    return text, usage


# --- data structures -------------------------------------------------------

@dataclass
class StageLog:
    name: str
    duration_s: float
    usage: dict
    output: object


@dataclass
class PipelineResult:
    final_translation: str
    accepted: bool
    iterations: int
    identification: dict
    verification: dict
    stages: list[StageLog] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stages"] = [asdict(s) for s in self.stages]
        return d


# --- stages ----------------------------------------------------------------

def stage1_identify(source_text: str, source_language: str) -> tuple[dict, StageLog]:
    system = _read(PROMPTS / "identify.txt")
    user = f"SOURCE LANGUAGE: {source_language}\n\nSOURCE TEXT:\n{source_text}"
    t0 = time.time()
    raw, usage = _call(system, user, temperature=0.0, max_tokens=600)
    data = _extract_json(raw)
    return data, StageLog("identification", time.time() - t0, usage, data)


def stage2_build_prompt(
    *,
    spec_text: str,
    references: References,
    identification: dict,
    source_text: str,
    source_language: str,
    target_language: str,
    refinement: str = "",
    memory: DocumentMemory | None = None,
) -> str:
    template = _read(PROMPTS / "translate.txt")
    if memory is None or memory.is_empty():
        memory_terms = "(no terminology established yet)"
        memory_summary = "(no summary yet — this is the first or only chunk)"
        memory_prev = "(this is the first or only chunk)"
    else:
        memory_terms = memory.to_terms_block()
        memory_summary = memory.to_summary_block()
        memory_prev = memory.to_prev_chunk_block(target_language)
    return template.format(
        spec=spec_text.strip(),
        references=references.to_context_block(),
        memory_terms=memory_terms,
        memory_summary=memory_summary,
        memory_prev=memory_prev,
        skopos=identification.get("skopos", ""),
        audience=identification.get("audience", ""),
        register=identification.get("register", ""),
        genre=identification.get("genre", ""),
        stance=identification.get("stance", ""),
        notes=identification.get("notes", ""),
        refinement=refinement.strip() or "(none)",
        source_text=source_text,
        source_language=source_language,
        target_language=target_language,
    )


def stage3_generate(prompt: str) -> tuple[str, StageLog]:
    t0 = time.time()
    raw, usage = _call(
        system="You are a careful, professional translator.",
        user=prompt,
        temperature=0.3,
        max_tokens=4000,
    )
    return raw.strip(), StageLog("generation", time.time() - t0, usage, raw.strip())


SEVERITY_WEIGHTS = {"critical": -25, "major": -5, "minor": -1}
DEFAULT_ACCEPT_THRESHOLD = -2  # allows up to 2 minor errors; any major/critical → revise


def _score_errors(errors: list[dict]) -> tuple[int, dict]:
    score = 0
    counts = {"critical": 0, "major": 0, "minor": 0}
    for e in errors:
        sev = (e.get("severity") or "minor").lower()
        if sev not in counts:
            sev = "minor"
        counts[sev] += 1
        score += SEVERITY_WEIGHTS[sev]
    return score, counts


def stage4_verify(
    *,
    source_text: str,
    translation: str,
    identification: dict,
    spec_text: str,
    references: References,
    target_language: str,
    accept_threshold: int = DEFAULT_ACCEPT_THRESHOLD,
) -> tuple[dict, StageLog]:
    system = _read(PROMPTS / "verify.txt")
    user = (
        f"TARGET LANGUAGE: {target_language}\n\n"
        f"SPEC:\n{spec_text}\n\n"
        f"REFERENCE MATERIALS:\n{references.to_context_block()}\n\n"
        f"SITUATIONAL ANALYSIS:\n{json.dumps(identification, ensure_ascii=False, indent=2)}\n\n"
        f"SOURCE TEXT:\n{source_text}\n\n"
        f"TRANSLATION:\n{translation}"
    )
    t0 = time.time()
    raw, usage = _call(system, user, temperature=0.0, max_tokens=2000)
    data = _extract_json(raw)
    errors = data.get("errors", []) or []
    score, counts = _score_errors(errors)
    verdict = "accept" if score >= accept_threshold else "revise"
    out = {
        "errors": errors,
        "summary": data.get("summary", ""),
        "score": score,
        "counts": counts,
        "verdict": verdict,
        "accept_threshold": accept_threshold,
    }
    return out, StageLog("verification", time.time() - t0, usage, out)


def _format_errors_as_refinement(errors: list[dict]) -> str:
    """Turn MQM error list into actionable instructions for the next Stage 2 prompt."""
    if not errors:
        return ""
    lines = [
        "The previous translation had the following issues. Address each one in the new translation:",
    ]
    for e in errors:
        sev = (e.get("severity") or "minor").upper()
        cat = e.get("category", "")
        span = e.get("span", "")
        expl = e.get("explanation", "")
        lines.append(f"- [{sev} | {cat}] \"{span}\" — {expl}")
    return "\n".join(lines)


# --- orchestration ---------------------------------------------------------

def run_pipeline(
    *,
    source_text: str,
    source_language: str = "Japanese",
    target_language: str = "English",
    spec_text: str | None = None,
    spec_path: Path | None = None,
    references: References | None = None,
    memory: DocumentMemory | None = None,
    max_iterations: int = 2,
    accept_threshold: int = DEFAULT_ACCEPT_THRESHOLD,
    on_event: Callable[[str, object], None] | None = None,
) -> PipelineResult:
    if spec_text is None:
        spec_path = spec_path or (SPECS / "default.md")
        spec_text = _read(spec_path)
    if references is None:
        references = References()
    stages: list[StageLog] = []

    def emit(name, payload):
        if on_event:
            on_event(name, payload)

    emit("start", {
        "target_language": target_language,
        "spec_chars": len(spec_text),
        "references": references.summary(),
    })

    # Stage 1
    identification, log1 = stage1_identify(source_text, source_language)
    stages.append(log1)
    emit("identification", identification)

    refinement = ""
    translation = ""
    verification: dict = {}
    iterations = 0
    accepted = False

    for i in range(1, max_iterations + 1):
        iterations = i
        # Stage 2
        prompt = stage2_build_prompt(
            spec_text=spec_text,
            references=references,
            identification=identification,
            source_text=source_text,
            source_language=source_language,
            target_language=target_language,
            refinement=refinement,
            memory=memory,
        )
        emit("prompting", {"iteration": i, "prompt_chars": len(prompt)})

        # Stage 3
        translation, log3 = stage3_generate(prompt)
        stages.append(log3)
        emit("generation", {"iteration": i, "translation": translation})

        # Stage 4
        verification, log4 = stage4_verify(
            source_text=source_text,
            translation=translation,
            identification=identification,
            spec_text=spec_text,
            references=references,
            target_language=target_language,
            accept_threshold=accept_threshold,
        )
        stages.append(log4)
        emit("verification", {"iteration": i, **verification})

        if verification.get("verdict") == "accept":
            accepted = True
            break
        refinement = _format_errors_as_refinement(verification.get("errors", []))

    return PipelineResult(
        final_translation=translation,
        accepted=accepted,
        iterations=iterations,
        identification=identification,
        verification=verification,
        stages=stages,
    )


# --- document-level orchestration -----------------------------------------

@dataclass
class DocumentResult:
    final_translation: str
    chunk_results: list[PipelineResult] = field(default_factory=list)
    memory: DocumentMemory = field(default_factory=DocumentMemory)
    memory_update_usage: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "final_translation": self.final_translation,
            "chunks": [r.to_dict() for r in self.chunk_results],
            "memory": {
                "proper_nouns": self.memory.proper_nouns,
                "summary": self.memory.summary,
                "chunks_completed": self.memory.chunks_completed,
            },
            "memory_update_usage": self.memory_update_usage,
        }


def run_document_pipeline(
    *,
    source_text: str,
    source_language: str = "Japanese",
    target_language: str = "English",
    spec_text: str | None = None,
    spec_path: Path | None = None,
    references: References | None = None,
    max_iterations: int = 2,
    accept_threshold: int = DEFAULT_ACCEPT_THRESHOLD,
    chunk_max_chars: int = 1500,
    on_event: Callable[[str, object], None] | None = None,
) -> DocumentResult:
    """Translate a (potentially long) document chunk-by-chunk with running memory.

    For single-chunk inputs this behaves like run_pipeline() with no memory.
    """
    if spec_text is None:
        spec_path = spec_path or (SPECS / "default.md")
        spec_text = _read(spec_path)
    if references is None:
        references = References()

    chunks = split_into_chunks(source_text, max_chars=chunk_max_chars)
    if not chunks:
        raise ValueError("Empty source text.")

    def emit(name, payload):
        if on_event:
            on_event(name, payload)

    emit("doc_start", {"chunks": len(chunks), "target_language": target_language})

    memory = DocumentMemory()
    chunk_results: list[PipelineResult] = []
    memory_update_usage: list[dict] = []

    for i, chunk in enumerate(chunks, start=1):
        emit("chunk_start", {"index": i, "total": len(chunks), "source": chunk})
        result = run_pipeline(
            source_text=chunk,
            source_language=source_language,
            target_language=target_language,
            spec_text=spec_text,
            references=references,
            memory=memory if memory.chunks_completed > 0 else None,
            max_iterations=max_iterations,
            accept_threshold=accept_threshold,
            on_event=on_event,
        )
        chunk_results.append(result)
        emit("chunk_done", {
            "index": i,
            "total": len(chunks),
            "translation": result.final_translation,
            "accepted": result.accepted,
            "iterations": result.iterations,
        })

        # Update memory unless this is the last chunk (no need; nothing follows)
        if i < len(chunks):
            try:
                delta, usage = update_memory(
                    memory=memory,
                    chunk_source=chunk,
                    chunk_translation=result.final_translation,
                    target_language=target_language,
                )
                memory_update_usage.append(usage)
                emit("memory_updated", {
                    "index": i,
                    "new_terms": delta.get("new_terms", {}),
                    "summary": memory.summary,
                    "notes": delta.get("notes", ""),
                })
            except Exception as e:
                emit("memory_error", {"index": i, "error": str(e)})
        else:
            # Last chunk: just record context for completeness
            memory.prev_source = chunk
            memory.prev_translation = result.final_translation
            memory.chunks_completed += 1

    final = "\n\n".join(r.final_translation for r in chunk_results)
    emit("doc_done", {"chunks": len(chunks), "final_chars": len(final)})

    return DocumentResult(
        final_translation=final,
        chunk_results=chunk_results,
        memory=memory,
        memory_update_usage=memory_update_usage,
    )


# --- CLI -------------------------------------------------------------------

def _cli():
    p = argparse.ArgumentParser()
    p.add_argument("--source", help="Source text (inline)")
    p.add_argument("--source-file", help="Path to source text file")
    p.add_argument("--source-language", default="Japanese")
    p.add_argument("--target", default="English", help="Target language")
    p.add_argument("--spec", default=None, help="Path to spec markdown")
    p.add_argument("--max-iterations", type=int, default=2)
    args = p.parse_args()

    if args.source_file:
        source_text = Path(args.source_file).read_text(encoding="utf-8")
    elif args.source:
        source_text = args.source
    else:
        raise SystemExit("Provide --source or --source-file.")

    spec_path = Path(args.spec) if args.spec else None

    def on_event(name, payload):
        print(f"\n=== {name} ===")
        if isinstance(payload, (dict, list)):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(payload)

    result = run_document_pipeline(
        source_text=source_text,
        source_language=args.source_language,
        target_language=args.target,
        spec_path=spec_path,
        max_iterations=args.max_iterations,
        on_event=on_event,
    )

    print("\n" + "=" * 60)
    print(f"FINAL TRANSLATION ({len(result.chunk_results)} chunk(s))")
    print("=" * 60)
    print(result.final_translation)
    print("=" * 60)
    if result.memory.proper_nouns:
        print("Established terminology:")
        for s, t in result.memory.proper_nouns.items():
            print(f"  {s} → {t}")
    total_in = sum(s.usage["input_tokens"] for r in result.chunk_results for s in r.stages)
    total_out = sum(s.usage["output_tokens"] for r in result.chunk_results for s in r.stages)
    mu_in = sum(u["input_tokens"] for u in result.memory_update_usage)
    mu_out = sum(u["output_tokens"] for u in result.memory_update_usage)
    print(f"Tokens: pipeline in={total_in} out={total_out} · memory in={mu_in} out={mu_out}")


if __name__ == "__main__":
    _cli()
