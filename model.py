"""Persistent TranslationModel + Engine (v0.10.0).

A **TranslationModel** is an editable, versioned bundle living at
`models/<id>/`. It holds the Spec, glossary, TM files, paired examples,
style guide, accumulated style decisions, and a `manifest.yaml` that
records LLM/pipeline settings, version, lock state, and source-file
hashes.

A **TranslationModel** can be **locked** (`lock_state: locked`) and then
**compiled** into an **Engine** — a frozen, immutable snapshot at
`engines/<id>@<version>/` that bundles everything needed to reproduce
its behaviour, including the prompt files active at compile time.

The two-layer split lets translators use Engines (fixed quality,
auditable) while developers iterate on Models, with feedback flowing
back as model edits then a new compile.

This file deliberately avoids any LLM calls or Streamlit imports so it
can be exercised from the CLI and tests.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from references import References, parse_pair_table

ROOT = Path(__file__).parent

SCHEMA_VERSION = 1
SYSTEM_VERSION = "0.10.0"

# Directories inside a model that contribute to its hash + are copied into engines.
TRACKED_DIRS = ("spec", "glossary", "tm", "style", "decisions")

# Prompt files that are bundled into engines for reproducibility.
BUNDLED_PROMPTS = (
    "identify.txt",
    "propose_spec.txt",
    "refine_spec.txt",
    "translate.txt",
    "verify.txt",
    "verify_spec.txt",
    "update_memory.txt",
    "align_segments.txt",
)


# ---------------------------------------------------------------------------
# location resolution (overridable for future Azure Blob / SMB mounts)
# ---------------------------------------------------------------------------

def models_dir() -> Path:
    return Path(os.environ.get("AT_MODELS_DIR", ROOT / "models")).resolve()


def engines_dir() -> Path:
    return Path(os.environ.get("AT_ENGINES_DIR", ROOT / "engines")).resolve()


def prompts_dir() -> Path:
    return ROOT / "prompts"


# ---------------------------------------------------------------------------
# hashing
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _iter_source_files(root: Path, subdirs: Iterable[str]) -> list[Path]:
    out: list[Path] = []
    for sub in subdirs:
        d = root / sub
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.is_file() and not p.name.startswith(".") and not p.name.endswith(".sqlite"):
                out.append(p)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def compute_hash(root: Path, subdirs: Iterable[str] = TRACKED_DIRS) -> tuple[dict[str, str], str]:
    sources: dict[str, str] = {}
    for f in _iter_source_files(root, subdirs):
        rel = f.relative_to(root).as_posix()
        sources[rel] = _sha256_file(f)
    canonical = json.dumps(sources, sort_keys=True, ensure_ascii=False).encode("utf-8")
    combined = "sha256:" + hashlib.sha256(canonical).hexdigest()
    return sources, combined


# ---------------------------------------------------------------------------
# semver helpers
# ---------------------------------------------------------------------------

def _parse_semver(s: str) -> tuple[int, int, int]:
    parts = s.strip().split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Not a valid semver: {s!r}")
    a, b, c = (int(p) for p in parts)
    return a, b, c


def _bump_semver(current: str, kind: str) -> str:
    a, b, c = _parse_semver(current)
    kind = kind.lower()
    if kind == "patch":
        return f"{a}.{b}.{c + 1}"
    if kind == "minor":
        return f"{a}.{b + 1}.0"
    if kind == "major":
        return f"{a + 1}.0.0"
    raise ValueError(f"bump must be patch | minor | major (got {kind!r})")


# ---------------------------------------------------------------------------
# TranslationModel (editable)
# ---------------------------------------------------------------------------

_DEFAULT_PIPELINE = {
    "max_iterations": 3,
    "mqm_threshold": 95.0,
    "dual_verifier": False,
    "chunk_max_chars": 1500,
    "chunk_max_segments": 6,
}

_DEFAULT_LLM = {
    "provider": "anthropic",
    "model": "claude-sonnet-4-6",
    "temperature": 0.3,
}


@dataclass
class TranslationModel:
    """An editable, versioned translation Model on disk."""
    id: str
    model_dir: Path
    manifest: dict = field(default_factory=dict)

    # --- factory --------------------------------------------------------

    @classmethod
    def new(
        cls,
        id: str,
        *,
        display_name: str | None = None,
        description: str = "",
        source_language: str = "Japanese",
        target_language: str = "English",
        locale: str = "",
        created_by: str = "",
        base_dir: Path | None = None,
    ) -> "TranslationModel":
        base = (base_dir or models_dir()).resolve()
        model_dir = base / id
        if model_dir.exists():
            raise FileExistsError(f"Model already exists: {model_dir}")
        for sub in TRACKED_DIRS:
            (model_dir / sub).mkdir(parents=True, exist_ok=True)
        # placeholder spec narrative so the model has something to lock
        (model_dir / "spec" / "narrative.md").write_text(
            f"# Translation Specification ({id})\n\n"
            "(Replace this placeholder with the locked spec — author via the "
            "Streamlit UI in Model-dev mode, or by editing this file directly.)\n",
            encoding="utf-8",
        )
        (model_dir / "decisions" / "style_decisions.yaml").write_text(
            "# Cross-document style decisions accumulated from post-edit feedback.\n"
            "{}\n",
            encoding="utf-8",
        )
        (model_dir / "CHANGELOG.md").write_text(
            f"# Changelog for model `{id}`\n\n## 0.1.0 (draft)\n- Initial scaffold.\n",
            encoding="utf-8",
        )
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "id": id,
            "display_name": display_name or id,
            "description": description,
            "source_language": source_language,
            "target_language": target_language,
            "locale": locale,
            "llm": dict(_DEFAULT_LLM),
            "pipeline": dict(_DEFAULT_PIPELINE),
            "version": "0.1.0",
            "lock_state": "draft",
            "created_at": _now(),
            "created_by": created_by,
            "locked_at": None,
            "locked_by": None,
            "sources": {},
            "hash": None,
            "engines": [],
        }
        m = cls(id=id, model_dir=model_dir, manifest=manifest)
        m.save()
        return m

    @classmethod
    def load(cls, id_or_dir: str | Path, *, base_dir: Path | None = None) -> "TranslationModel":
        if isinstance(id_or_dir, Path) or "/" in str(id_or_dir):
            model_dir = Path(id_or_dir).resolve()
        else:
            base = (base_dir or models_dir()).resolve()
            model_dir = base / str(id_or_dir)
        manifest_path = model_dir / "manifest.yaml"
        if not manifest_path.exists():
            raise FileNotFoundError(f"No manifest.yaml at {model_dir}")
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        return cls(id=manifest.get("id", model_dir.name), model_dir=model_dir, manifest=manifest)

    # --- persistence ----------------------------------------------------

    def save(self) -> None:
        self.model_dir.mkdir(parents=True, exist_ok=True)
        (self.model_dir / "manifest.yaml").write_text(
            yaml.safe_dump(self.manifest, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    # --- state queries --------------------------------------------------

    @property
    def version(self) -> str:
        return self.manifest.get("version", "0.1.0")

    @property
    def is_locked(self) -> bool:
        return self.manifest.get("lock_state") == "locked"

    @property
    def spec_narrative_path(self) -> Path:
        return self.model_dir / "spec" / "narrative.md"

    @property
    def spec_narrative(self) -> str:
        p = self.spec_narrative_path
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def has_drift(self) -> tuple[bool, list[str]]:
        """For a locked model: are the actual files still consistent with the recorded hashes?"""
        if not self.is_locked:
            return (False, [])
        current, _combined = compute_hash(self.model_dir)
        recorded = self.manifest.get("sources", {})
        drifted = []
        all_keys = set(current) | set(recorded)
        for k in sorted(all_keys):
            if current.get(k) != recorded.get(k):
                drifted.append(k)
        return (bool(drifted), drifted)

    # --- mutations ------------------------------------------------------

    def write_spec(self, narrative_md: str) -> None:
        if self.is_locked:
            raise RuntimeError(f"Model {self.id} is locked. Unlock before editing.")
        self.spec_narrative_path.parent.mkdir(parents=True, exist_ok=True)
        self.spec_narrative_path.write_text(narrative_md, encoding="utf-8")

    def write_text_in_model(self, rel_path: str, text: str) -> None:
        if self.is_locked:
            raise RuntimeError(f"Model {self.id} is locked. Unlock before editing.")
        out = self.model_dir / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")

    def lock(self, *, bump: str, by: str = "") -> None:
        if self.is_locked:
            raise RuntimeError(f"Model {self.id} is already locked at {self.version}.")
        new_version = _bump_semver(self.version, bump)
        sources, combined = compute_hash(self.model_dir)
        self.manifest["sources"] = sources
        self.manifest["hash"] = combined
        self.manifest["version"] = new_version
        self.manifest["lock_state"] = "locked"
        self.manifest["locked_at"] = _now()
        self.manifest["locked_by"] = by or self.manifest.get("created_by", "")
        self.save()

    def unlock(self) -> None:
        if not self.is_locked:
            return
        self.manifest["lock_state"] = "draft"
        # Keep locked_at/locked_by for traceability of the last lock.
        self.save()

    # --- references (used by both Model-dev and Engine modes) ----------

    def references(self) -> References:
        """Build a References from the on-disk Model artifacts.

        v0.10: bulk loading (same shape as the current References).
        v0.11+: this becomes a ReferenceStore + per-chunk Retriever.
        """
        return _references_from_dir(self.model_dir)


# ---------------------------------------------------------------------------
# Engine (frozen)
# ---------------------------------------------------------------------------

@dataclass
class Engine:
    """A compiled, immutable Engine snapshot."""
    id: str            # model id
    version: str
    engine_dir: Path
    manifest: dict = field(default_factory=dict)
    seal: dict = field(default_factory=dict)

    @property
    def display_id(self) -> str:
        return f"{self.id}@{self.version}"

    # --- compile --------------------------------------------------------

    @classmethod
    def compile_from(
        cls,
        model: TranslationModel,
        *,
        base_dir: Path | None = None,
        compiled_by: str = "",
    ) -> "Engine":
        if not model.is_locked:
            raise RuntimeError(
                f"Model {model.id} must be locked before compile (run `at model lock` first)."
            )
        drifted, files = model.has_drift()
        if drifted:
            raise RuntimeError(
                f"Locked model {model.id} has drifted files: {files}. "
                "Unlock, re-lock with --bump, then compile."
            )

        target_root = (base_dir or engines_dir()).resolve()
        engine_dir = target_root / f"{model.id}@{model.version}"
        if engine_dir.exists():
            raise FileExistsError(f"Engine already exists: {engine_dir}")
        engine_dir.mkdir(parents=True, exist_ok=False)

        # 1. Copy tracked source dirs
        for sub in TRACKED_DIRS:
            src = model.model_dir / sub
            if src.exists():
                shutil.copytree(src, engine_dir / sub)

        # 2. Bundle prompts (any that exist on the system right now)
        prompts_src = prompts_dir()
        prompts_out = engine_dir / "prompts"
        prompts_out.mkdir(exist_ok=True)
        prompt_hashes: dict[str, str] = {}
        for fname in BUNDLED_PROMPTS:
            src_p = prompts_src / fname
            if src_p.exists():
                shutil.copy2(src_p, prompts_out / fname)
                prompt_hashes[f"prompts/{fname}"] = _sha256_file(src_p)

        # 3. Copy model manifest as-is for traceability
        manifest_copy = dict(model.manifest)
        (engine_dir / "manifest.yaml").write_text(
            yaml.safe_dump(manifest_copy, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

        # 4. Compute combined engine hash over EVERYTHING (sources + prompts + manifest)
        engine_sources, _ = compute_hash(engine_dir, subdirs=TRACKED_DIRS)
        engine_sources.update(prompt_hashes)
        engine_sources["manifest.yaml"] = _sha256_file(engine_dir / "manifest.yaml")
        canonical = json.dumps(engine_sources, sort_keys=True, ensure_ascii=False).encode("utf-8")
        engine_hash = "sha256:" + hashlib.sha256(canonical).hexdigest()

        seal = {
            "schema_version": SCHEMA_VERSION,
            "engine_id": model.id,
            "version": model.version,
            "compiled_at": _now(),
            "compiled_by": compiled_by or model.manifest.get("locked_by", ""),
            "compiled_from": {
                "model_hash": model.manifest.get("hash"),
                "model_locked_at": model.manifest.get("locked_at"),
            },
            "system_version": SYSTEM_VERSION,
            "prompt_hashes": prompt_hashes,
            "source_hashes": {k: v for k, v in engine_sources.items() if not k.startswith("prompts/") and k != "manifest.yaml"},
            "engine_hash": engine_hash,
        }
        (engine_dir / "seal.json").write_text(
            json.dumps(seal, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # 5. Record compile in the source model manifest
        model.manifest.setdefault("engines", []).append({
            "version": model.version,
            "compiled_at": seal["compiled_at"],
            "compiled_by": seal["compiled_by"],
            "engine_hash": engine_hash,
        })
        # The model just got a metadata change — but it's bookkeeping, not Spec content,
        # so we record but do NOT bump version or unlock. Save through the locked state.
        model.save()

        # 6. Optionally make engine read-only (best-effort, no error if it fails)
        _try_make_readonly(engine_dir)

        return cls(
            id=model.id,
            version=model.version,
            engine_dir=engine_dir,
            manifest=manifest_copy,
            seal=seal,
        )

    # --- load + verify --------------------------------------------------

    @classmethod
    def load(cls, id_at_version_or_dir: str | Path, *, base_dir: Path | None = None) -> "Engine":
        if isinstance(id_at_version_or_dir, Path) or "/" in str(id_at_version_or_dir):
            engine_dir = Path(id_at_version_or_dir).resolve()
        else:
            base = (base_dir or engines_dir()).resolve()
            engine_dir = base / str(id_at_version_or_dir)
        seal_path = engine_dir / "seal.json"
        manifest_path = engine_dir / "manifest.yaml"
        if not seal_path.exists() or not manifest_path.exists():
            raise FileNotFoundError(f"Not a valid engine directory: {engine_dir}")
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        return cls(
            id=seal.get("engine_id", manifest.get("id", "")),
            version=seal.get("version", manifest.get("version", "")),
            engine_dir=engine_dir,
            manifest=manifest,
            seal=seal,
        )

    def verify(self) -> tuple[bool, list[str]]:
        """Re-hash the engine and check against the seal. Returns (ok, drifted_files)."""
        recorded = dict(self.seal.get("source_hashes", {}))
        recorded.update(self.seal.get("prompt_hashes", {}))
        recorded["manifest.yaml"] = _sha256_file(self.engine_dir / "manifest.yaml")
        drifted: list[str] = []
        for rel, h in recorded.items():
            p = self.engine_dir / rel
            if not p.exists():
                drifted.append(rel + " (missing)")
                continue
            if _sha256_file(p) != h:
                drifted.append(rel)
        return (not drifted, drifted)

    # --- runtime accessors ---------------------------------------------

    @property
    def spec_narrative(self) -> str:
        p = self.engine_dir / "spec" / "narrative.md"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    @property
    def prompts_dir(self) -> Path:
        return self.engine_dir / "prompts"

    def references(self) -> References:
        return _references_from_dir(self.engine_dir)

    def pipeline_kwargs(self) -> dict:
        pl = dict(_DEFAULT_PIPELINE)
        pl.update(self.manifest.get("pipeline", {}) or {})
        return pl

    def llm_settings(self) -> dict:
        ll = dict(_DEFAULT_LLM)
        ll.update(self.manifest.get("llm", {}) or {})
        return ll


# ---------------------------------------------------------------------------
# References loader shared by Model and Engine
# ---------------------------------------------------------------------------

def _references_from_dir(root: Path) -> References:
    refs = References()
    # Glossary: glossary/terms.csv (or .tsv) — source,target[,...]
    for name in ("terms.csv", "terms.tsv"):
        p = root / "glossary" / name
        if p.exists():
            refs.glossary = parse_pair_table(p.read_text(encoding="utf-8"))
            break
    # Paired examples: style/paired_examples.csv (or .tsv)
    for name in ("paired_examples.csv", "paired_examples.tsv"):
        p = root / "style" / name
        if p.exists():
            refs.paired = parse_pair_table(p.read_text(encoding="utf-8"))
            break
    # Parallel target-language texts: every file under style/parallel_texts/
    par_dir = root / "style" / "parallel_texts"
    if par_dir.exists():
        refs.parallel = [
            (f.name, f.read_text(encoding="utf-8", errors="replace"))
            for f in sorted(par_dir.iterdir())
            if f.is_file() and not f.name.startswith(".")
        ]
    # Style guide
    sg = root / "style" / "style_guide.md"
    if sg.exists():
        refs.style_guide = sg.read_text(encoding="utf-8")
    return refs


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------

def list_models(base_dir: Path | None = None) -> list[TranslationModel]:
    base = (base_dir or models_dir()).resolve()
    if not base.exists():
        return []
    out: list[TranslationModel] = []
    for d in sorted(base.iterdir()):
        if d.is_dir() and (d / "manifest.yaml").exists():
            try:
                out.append(TranslationModel.load(d))
            except Exception:
                continue
    return out


def list_engines(base_dir: Path | None = None) -> list[Engine]:
    base = (base_dir or engines_dir()).resolve()
    if not base.exists():
        return []
    out: list[Engine] = []
    for d in sorted(base.iterdir()):
        if d.is_dir() and (d / "seal.json").exists():
            try:
                out.append(Engine.load(d))
            except Exception:
                continue
    return out


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _try_make_readonly(path: Path) -> None:
    """Best-effort: strip write bits on all files under path. Silently skip on failure."""
    try:
        for p in path.rglob("*"):
            try:
                mode = p.stat().st_mode
                p.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
            except OSError:
                pass
    except Exception:
        pass


def _undo_readonly(path: Path) -> None:
    """For engine removal: re-enable writes so shutil.rmtree can clean up."""
    for p in path.rglob("*"):
        try:
            mode = p.stat().st_mode
            p.chmod(mode | stat.S_IWUSR)
        except OSError:
            pass


def remove_engine(engine: Engine) -> None:
    _undo_readonly(engine.engine_dir)
    shutil.rmtree(engine.engine_dir)
