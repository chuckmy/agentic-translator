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

from api import call_model
from chunker import Chunk, Segment, split_into_chunks
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
    return call_model(
        system=system,
        user=user,
        temperature=temperature,
        max_tokens=max_tokens,
    )


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
    convergence_status: str = "unknown"  # accepted | max_iterations | stalled_score | stalled_recurring
    score_history: list[float] = field(default_factory=list)
    stages: list[StageLog] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stages"] = [asdict(s) for s in self.stages]
        return d


# --- stages ----------------------------------------------------------------

def stage1_identify(
    source_text: str, source_language: str, spec_text: str
) -> tuple[dict, StageLog]:
    """Micro-level contextualization of THIS chunk against the confirmed Spec.

    Returns JSON: {deviations: [...], focus_terms: [...], notes: "..."}
    """
    system = _read(PROMPTS / "identify.txt")
    user = (
        f"SOURCE LANGUAGE: {source_language}\n\n"
        f"SPECIFICATION:\n{spec_text}\n\n"
        f"SOURCE CHUNK:\n{source_text}"
    )
    t0 = time.time()
    raw, usage = _call(system, user, temperature=0.0, max_tokens=800)
    data = _extract_json(raw)
    return data, StageLog("identification", time.time() - t0, usage, data)


def _format_deviations(deviations: list) -> str:
    if not deviations:
        return "(none — chunk follows Spec defaults)"
    lines = []
    for d in deviations:
        dim = d.get("dimension", "")
        obs = d.get("observation", "")
        ins = d.get("instruction", "")
        lines.append(f"- [{dim}] {obs} → {ins}")
    return "\n".join(lines)


def _format_focus_terms(focus_terms: list) -> str:
    if not focus_terms:
        return "(none)"
    lines = []
    for ft in focus_terms:
        src = ft.get("src", "")
        tgt = ft.get("tgt", "")
        if tgt:
            lines.append(f"- {src} → {tgt}")
        else:
            lines.append(f"- {src} (no fixed target — translator decides)")
    return "\n".join(lines)


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
        memory_style = "(no style decisions recorded yet)"
        memory_summary = "(no summary yet — this is the first or only chunk)"
        memory_prev = "(this is the first or only chunk)"
    else:
        memory_terms = memory.to_terms_block()
        memory_style = memory.to_style_block()
        memory_summary = memory.to_summary_block()
        memory_prev = memory.to_prev_chunk_block(target_language)
    return template.format(
        spec=spec_text.strip(),
        references=references.to_context_block(),
        memory_terms=memory_terms,
        memory_style=memory_style,
        memory_summary=memory_summary,
        memory_prev=memory_prev,
        deviations=_format_deviations(identification.get("deviations", []) or []),
        focus_terms=_format_focus_terms(identification.get("focus_terms", []) or []),
        notes=identification.get("notes", "") or "(none)",
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


# Legacy negative-sum scoring (kept for trace logs / research comparability)
SEVERITY_WEIGHTS = {"critical": -25, "major": -5, "minor": -1}

# MQM positive penalty weights (Lommel/Burchardt/Uszkoreit 2014; Freitag et al. TACL 2021)
MQM_WEIGHTS = {"critical": 25, "major": 5, "minor": 1}
MQM_NORMALIZE_UNIT_CHARS = 100  # penalty is per 100 source characters
DEFAULT_MQM_THRESHOLD = 95.0    # publication-quality benchmark (Burchardt et al.)

# Scoring criteria metadata (surfaced to the UI and trace logs)
SCORING_CRITERIA = {
    "standard": "MQM (Multidimensional Quality Metrics)",
    "normalize_unit": "per 100 source characters",
    "weights": MQM_WEIGHTS,
    "default_threshold": DEFAULT_MQM_THRESHOLD,
    "bands": {
        "publication_quality": ">= 95",
        "business_quality": "90–94",
        "needs_major_revision": "< 85",
    },
    "references": [
        "Lommel, Uszkoreit & Burchardt (2014) — MQM framework",
        "Burchardt et al. (2014) — quality bands",
        "Freitag et al. (TACL 2021) — MQM for MT evaluation",
    ],
}


def _score_errors(errors: list[dict]) -> tuple[int, dict]:
    """Legacy negative-sum score (kept for backward-compatible trace fields)."""
    score = 0
    counts = {"critical": 0, "major": 0, "minor": 0}
    for e in errors:
        sev = (e.get("severity") or "minor").lower()
        if sev not in counts:
            sev = "minor"
        counts[sev] += 1
        score += SEVERITY_WEIGHTS[sev]
    return score, counts


def _compute_mqm_score(errors: list[dict], source_length: int) -> tuple[float, int, dict]:
    """MQM 0–100 score, normalized per 100 source characters. Higher = better."""
    counts = {"critical": 0, "major": 0, "minor": 0}
    penalty = 0
    for e in errors:
        sev = (e.get("severity") or "minor").lower()
        if sev not in counts:
            sev = "minor"
        counts[sev] += 1
        penalty += MQM_WEIGHTS[sev]
    n = max(source_length, 1)
    score = max(0.0, 100.0 - penalty * MQM_NORMALIZE_UNIT_CHARS / n)
    return round(score, 1), penalty, counts


def _run_verifier(
    *,
    prompt_file: str,
    source_text: str,
    translation: str,
    identification: dict,
    spec_text: str,
    references: References,
    target_language: str,
) -> tuple[dict, dict]:
    """Run a single verifier (MQM or Spec-grounded). Returns (parsed_dict, usage)."""
    system = _read(PROMPTS / prompt_file)
    user = (
        f"TARGET LANGUAGE: {target_language}\n\n"
        f"SPEC:\n{spec_text}\n\n"
        f"REFERENCE MATERIALS:\n{references.to_context_block()}\n\n"
        f"CHUNK CONTEXT (micro-level deviations and focus terms vs. the Spec):\n"
        f"{json.dumps(identification, ensure_ascii=False, indent=2)}\n\n"
        f"SOURCE TEXT:\n{source_text}\n\n"
        f"TRANSLATION:\n{translation}"
    )
    raw, usage = _call(system, user, temperature=0.0, max_tokens=2500)
    data = _extract_json(raw)
    return data, usage


_SEV_ORDER = {"minor": 0, "major": 1, "critical": 2}


def _merge_errors(errs_a: list[dict], errs_b: list[dict]) -> list[dict]:
    """Merge two error lists. Dedup by (span, category) — keep the one with max severity."""
    merged: dict[tuple[str, str], dict] = {}
    for e in list(errs_a) + list(errs_b):
        key = (e.get("span", ""), e.get("category", ""))
        if key in merged:
            cur_sev = (merged[key].get("severity") or "minor").lower()
            new_sev = (e.get("severity") or "minor").lower()
            if _SEV_ORDER.get(new_sev, 0) > _SEV_ORDER.get(cur_sev, 0):
                merged[key] = e
        else:
            merged[key] = e
    return list(merged.values())


def stage4_verify(
    *,
    source_text: str,
    translation: str,
    identification: dict,
    spec_text: str,
    references: References,
    target_language: str,
    accept_threshold: float = DEFAULT_MQM_THRESHOLD,
    dual_verifier: bool = False,
) -> tuple[dict, StageLog]:
    t0 = time.time()

    # Verifier 1: MQM (always runs)
    v1, usage1 = _run_verifier(
        prompt_file="verify.txt",
        source_text=source_text, translation=translation,
        identification=identification, spec_text=spec_text,
        references=references, target_language=target_language,
    )

    verifier_outputs = [{"name": "mqm", "data": v1, "usage": usage1}]
    errors = v1.get("errors", []) or []
    spec_compliance_v1 = v1.get("spec_compliance", {}) or {}
    checked = list(spec_compliance_v1.get("checked_sections", []) or [])
    concerns = list(spec_compliance_v1.get("concerns", []) or [])
    summary = v1.get("summary", "")

    # Verifier 2: Spec-grounded (optional)
    if dual_verifier:
        v2, usage2 = _run_verifier(
            prompt_file="verify_spec.txt",
            source_text=source_text, translation=translation,
            identification=identification, spec_text=spec_text,
            references=references, target_language=target_language,
        )
        verifier_outputs.append({"name": "spec_grounded", "data": v2, "usage": usage2})
        errors = _merge_errors(errors, v2.get("errors", []) or [])
        sc2 = v2.get("spec_compliance", {}) or {}
        # Union of checked sections, concatenated concerns
        for s in sc2.get("checked_sections", []) or []:
            if s not in checked:
                checked.append(s)
        for c in sc2.get("concerns", []) or []:
            if c not in concerns:
                concerns.append(c)
        if v2.get("summary"):
            summary = (summary + " | Spec-grounded: " + v2["summary"]).strip(" |")

    # Legacy negative-sum (kept for trace/research compat)
    legacy_score, _ = _score_errors(errors)
    # MQM 0–100 (primary, used for verdict)
    mqm_score, penalty, counts = _compute_mqm_score(errors, len(source_text))
    verdict = "accept" if mqm_score >= accept_threshold else "revise"

    # Quality band label
    if mqm_score >= 95:
        band = "publication_quality"
    elif mqm_score >= 90:
        band = "business_quality"
    elif mqm_score >= 85:
        band = "marginal"
    else:
        band = "needs_major_revision"

    # Combined usage for the stage log
    combined_usage = {
        "input_tokens": sum(v["usage"].get("input_tokens", 0) for v in verifier_outputs),
        "output_tokens": sum(v["usage"].get("output_tokens", 0) for v in verifier_outputs),
    }

    out = {
        "errors": errors,
        "summary": summary,
        "score": mqm_score,                # primary (MQM 0–100)
        "legacy_score": legacy_score,      # kept for research comparability
        "penalty": penalty,
        "source_length": len(source_text),
        "counts": counts,
        "verdict": verdict,
        "accept_threshold": accept_threshold,
        "quality_band": band,
        "scoring_criteria": SCORING_CRITERIA,
        "spec_compliance": {
            "checked_sections": checked,
            "concerns": concerns,
        },
        "verifier_outputs": verifier_outputs,
        "dual_verifier": dual_verifier,
    }
    return out, StageLog("verification", time.time() - t0, combined_usage, out)


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
        spec_section = e.get("spec_section", "")
        tag = f"{sev} | {cat}"
        if spec_section:
            tag += f" | Spec: {spec_section}"
        lines.append(f"- [{tag}] \"{span}\" — {expl}")
    return "\n".join(lines)


# --- orchestration ---------------------------------------------------------

def _error_signature(errors: list[dict]) -> set[tuple[str, str]]:
    """(category, severity) set — used to detect non-converging revision loops."""
    sig = set()
    for e in errors:
        cat = (e.get("category") or "").lower()
        sev = (e.get("severity") or "minor").lower()
        sig.add((cat, sev))
    return sig


def run_pipeline(
    *,
    source_text: str,
    source_language: str = "Japanese",
    target_language: str = "English",
    spec_text: str | None = None,
    spec_path: Path | None = None,
    references: References | None = None,
    memory: DocumentMemory | None = None,
    max_iterations: int = 3,
    accept_threshold: float = DEFAULT_MQM_THRESHOLD,
    dual_verifier: bool = False,
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
    identification, log1 = stage1_identify(source_text, source_language, spec_text)
    stages.append(log1)
    emit("identification", identification)

    refinement = ""
    translation = ""
    verification: dict = {}
    iterations = 0
    accepted = False
    convergence_status = "max_iterations"
    score_history: list[float] = []
    prev_score: float | None = None
    prev_error_sig: set[tuple[str, str]] | None = None

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
            dual_verifier=dual_verifier,
        )
        stages.append(log4)
        emit("verification", {"iteration": i, **verification})

        score = verification.get("score", 0)
        score_history.append(score)

        if verification.get("verdict") == "accept":
            accepted = True
            convergence_status = "accepted"
            break

        errors = verification.get("errors", []) or []
        cur_sig = _error_signature(errors)

        # Early stopping (from iteration 2 onward) — higher MQM score = better
        if i >= 2 and prev_score is not None:
            if score <= prev_score:
                convergence_status = "stalled_score"
                emit("early_stop", {
                    "iteration": i,
                    "reason": "MQM score did not improve",
                    "prev_score": prev_score,
                    "score": score,
                })
                break
            if prev_error_sig and cur_sig & prev_error_sig:
                convergence_status = "stalled_recurring"
                emit("early_stop", {
                    "iteration": i,
                    "reason": "same (category,severity) errors recurred",
                    "recurring": sorted(list(cur_sig & prev_error_sig)),
                })
                break

        prev_score = score
        prev_error_sig = cur_sig
        refinement = _format_errors_as_refinement(errors)

    return PipelineResult(
        final_translation=translation,
        accepted=accepted,
        iterations=iterations,
        identification=identification,
        verification=verification,
        convergence_status=convergence_status,
        score_history=score_history,
        stages=stages,
    )


# --- document-level orchestration -----------------------------------------

@dataclass
class DocumentResult:
    final_translation: str
    chunk_results: list[PipelineResult] = field(default_factory=list)
    chunks: list[Chunk] = field(default_factory=list)
    memory: DocumentMemory = field(default_factory=DocumentMemory)
    memory_update_usage: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "final_translation": self.final_translation,
            "chunks": [r.to_dict() for r in self.chunk_results],
            "segments": [
                {
                    "chunk_index": c.index,
                    "id_range": c.id_range,
                    "segments": [
                        {"id": s.id, "text": s.text} for s in c.segments
                    ],
                }
                for c in self.chunks
            ],
            "memory": {
                "proper_nouns": self.memory.proper_nouns,
                "style_decisions": self.memory.style_decisions,
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
    max_iterations: int = 3,
    accept_threshold: float = DEFAULT_MQM_THRESHOLD,
    chunk_max_chars: int = 1500,
    chunk_max_segments: int = 6,
    dual_verifier: bool = False,
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

    chunks = split_into_chunks(
        source_text, max_chars=chunk_max_chars, max_segments=chunk_max_segments
    )
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
        emit("chunk_start", {
            "index": i,
            "total": len(chunks),
            "source": chunk.text,
            "id_range": chunk.id_range,
            "segments": [{"id": s.id, "text": s.text} for s in chunk.segments],
        })
        result = run_pipeline(
            source_text=chunk.text,
            source_language=source_language,
            target_language=target_language,
            spec_text=spec_text,
            references=references,
            memory=memory if memory.chunks_completed > 0 else None,
            max_iterations=max_iterations,
            accept_threshold=accept_threshold,
            dual_verifier=dual_verifier,
            on_event=on_event,
        )
        chunk_results.append(result)
        emit("chunk_done", {
            "index": i,
            "total": len(chunks),
            "id_range": chunk.id_range,
            "translation": result.final_translation,
            "accepted": result.accepted,
            "iterations": result.iterations,
            "convergence_status": result.convergence_status,
            "score_history": result.score_history,
        })

        # Update memory unless this is the last chunk (no need; nothing follows)
        if i < len(chunks):
            try:
                delta, usage = update_memory(
                    memory=memory,
                    chunk_source=chunk.text,
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
            memory.prev_source = chunk.text
            memory.prev_translation = result.final_translation
            memory.chunks_completed += 1

    final = "\n\n".join(r.final_translation for r in chunk_results)
    emit("doc_done", {"chunks": len(chunks), "final_chars": len(final)})

    return DocumentResult(
        final_translation=final,
        chunk_results=chunk_results,
        chunks=chunks,
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
    p.add_argument("--max-iterations", type=int, default=3)
    p.add_argument("--dual-verifier", action="store_true",
                   help="Run a second Spec-grounded verifier and merge results.")
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
        dual_verifier=args.dual_verifier,
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
