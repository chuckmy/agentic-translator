# Changelog

## v0.10.1 - 2026-05-30

### Added

- **Company-shared deployment mode** — set `AT_COMPANY_MODE=1` in the server env and the BYOK sidebar is hidden; translators silently use the server's `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`. Designed for Tailscale-fronted localhost deployments where one company-paid key serves the whole team.
- **`docs/deploy-tailscale.md`** — comprehensive guide for self-hosting on an always-on Mac / Linux box exposed to remote translators via Tailscale. Covers server install, env config, launchd auto-start, Tailscale ACL recommendations, maintenance, troubleshooting, and cost breakdown.
- **`scripts/start-server.sh`** — bash launcher that sources `~/.config/agentic-translator/server.env` and starts headless Streamlit on `0.0.0.0:8501`.
- **`scripts/co.translab.agentic-translator.plist`** — macOS launchd template for boot-time auto-start.
- **`scripts/tailscale-acl.example.json`** — recommended ACL that gives translators only port 8501 on the server and admins full access + SSH.
- `.env.example` documents `AT_MODELS_DIR`, `AT_ENGINES_DIR`, `AT_COMPANY_MODE`.

### Notes

- This patch contains no breaking changes; v0.10.0 deployments work unchanged. Setting `AT_COMPANY_MODE=1` is purely additive.

## v0.10.0 - 2026-05-30

### Added

- **TranslationModel**: a persistent, versioned bundle on disk (`models/<id>/`) with `manifest.yaml`, structured/narrative spec, glossary, TM, paired examples, style guide, accumulated style decisions, and a CHANGELOG. Models have semver versions and `draft` / `locked` states.
- **Engine**: a frozen, immutable compile snapshot (`engines/<id>@<version>/`) that bundles everything needed to reproduce a model's behaviour, **including the prompt files** active at compile time. Engines carry a `seal.json` with content hashes, system version, and compile provenance. Files are made read-only on best-effort basis.
- **Lock / Compile workflow**: `at model lock --bump patch|minor|major` freezes content hashes and bumps the semver. `at model compile` produces an Engine snapshot. Drift detection on locked models.
- **CLI** (`cli.py`, run via `python -m cli ...` or the `at` alias): `model new / list / show / edit / lock / unlock / compile`, `engine list / show / verify / remove`.
- **Streamlit Mode switcher**: three modes — `session only` (legacy), `model dev` (author a model), `engine` (use a compiled engine). Engine mode hides Sections 1 and 3 since refs and spec come from the engine.
- **Lock & Compile button** in Model dev mode: writes the current Spec to the model, locks it with a chosen bump, and compiles an Engine in one click.
- `run_document_pipeline(engine=...)`: when an Engine is supplied, its spec, references, prompts, and pipeline knobs are used; the system's live prompts are swapped out for the engine's bundled prompts during the run.
- `pipeline.py --engine <id>@<version>` flag for CLI translation against a frozen Engine.
- Environment variables `AT_MODELS_DIR` and `AT_ENGINES_DIR` to relocate Model/Engine storage (forward path to Azure Blob / shared mounts).
- New dependencies: `pyyaml>=6.0`, `typer>=0.12`, `rich>=13.0`.

### Changed

- Pipeline's `PROMPTS` module-level path is now swappable; engine runs use the engine's bundled prompts and restore the system path on exit.

### Notes

- Models and engines are gitignored by default — they are user-authored / reproducible artefacts, not system code.
- v0.11+ will activate Glossary/TM at scale (BM25 + per-chunk filtering, TMX import); v0.10 stores them on disk but does not yet retrieve.

## v0.9.0 - 2026-05-30

### Added

- Adopted the 12-section **Translation Parameters** spec framework (Source Profile, Specialized Domain, Target Language and Locale, Skopos, Audience, Register and Voice, Content Correspondence, Terminology Guidance, Style Decisions, Preserve/Localize/Avoid, Layout and Formatting, Open Questions).
- Added segment-aware chunking with stable `P{n}.S{n}` IDs and a `max_segments` cap; paragraphs are never crossed.
- Added document-level **style decisions ledger** updated across chunks alongside the proper-noun ledger.
- Added micro-level Stage 1 identification that contextualizes each chunk against the locked Spec (deviations, focus_terms, notes) instead of re-deriving macro categories.
- Added MQM 0–100 scoring (Lommel/Burchardt 2014, Freitag et al. TACL 2021) with quality bands (publication ≥95 / business 90–94 / needs revision <85) and full scoring-criteria transparency in the UI.
- Added optional **dual verifier**: a second Spec-grounded reviewer that walks the 12 sections; results merged with MQM verifier.
- Added convergence tracking and early stopping (`stalled_score`, `stalled_recurring`) with `score_history`.
- Added bilingual exporters (sentence-level and chunk-level, CSV/Excel) with LLM-based alignment fallback when sentence counts diverge.
- Added process trace exporters (Markdown / Excel / JSON) covering chunks, iterations, errors, and Spec-compliance concerns.
- Added system paper drafts (`docs/system_paper_draft.md`, `docs/system_paper_draft_ja.md`) and arXiv build pipeline (`paper/`, `scripts/build_arxiv_from_md.py`).
- Added `openpyxl>=3.1` for Excel exporters.

### Changed

- Default `max_iterations` raised from 2 to 3; default accept threshold migrated from `-2` (legacy negative-sum) to `95.0` (MQM 0–100). Session-state migrates automatically.
- Verifier prompt now requires `spec_section` for every error and reports `spec_compliance.checked_sections` / `concerns`.
- `chunker.split_into_chunks` now returns `Chunk` objects (with `.segments`, `.text`, `.id_range`) instead of plain strings.
- UI shows segment counts alongside chunk counts and surfaces an MQM signal-light verdict (🟢/🟡/🔴) per iteration.

### Notes

- This is a breaking change to the public Python API (`split_into_chunks` return type, score scale). Downstream consumers must migrate.
- Empirical validation of the spec-driven architecture remains future work.

## v0.8.0 - 2026-05-16

### Added

- Added provider selection for Anthropic Claude API and OpenAI API.
- Added OpenAI Responses API support through a shared provider abstraction.
- Added recommended model guidance to `README.md` and `README_ja.md`.
- Added runtime API key handling for each provider in the Streamlit sidebar.
- Added final translation download as `.txt`.
- Added full run data download as `.json`.
- Added run-event logging with `.json` and `.md` downloads.
- Added partial run-log download support for failed runs.
- Added safer provider authentication error messages that do not expose API key fragments.

### Changed

- Renamed the visible app title to **Agentic AI Translate**.
- Reworked pipeline, spec chat, and memory update calls to use the shared `api.call_model()` interface.
- Updated local API connectivity test to work with the selected provider.
- Updated documentation workflow steps to describe spec proposal, spec locking, and translation execution more explicitly.

### Fixed

- Hardened Streamlit session-state migration for older sessions that only stored a single API key.
- Hardened Streamlit session-state initialization for missing or invalid provider state.
- Made Markdown run reports more readable instead of embedding raw JSON blocks throughout.

### Notes

- The recommended default models as of 2026-05-16 are `claude-sonnet-4-6` for Anthropic and `gpt-5.4-mini` for OpenAI.
- `.env` remains ignored and must not be committed. Use `.env.example` as the public template.
- The app is still a research prototype, not a production translation service.
